"""Deterministic check of "the contract is in Vietnamese" criteria; no AI involved.

Most contracts never say "this contract is written in Vietnamese", so an AI asked to quote the
clause that proves it has nothing to quote. Whether a text is Vietnamese is a measurement, not a
legal judgement: the backend counts the words that carry Vietnamese letters and the common
English function words over the whole document.

Only one outcome is ever produced: SATISFIED, when the document is clearly Vietnamese-only.
A bilingual or foreign-language document, a short text, or a criterion without a selected
contract passage is left to the AI and the reviewer. If the AI already proposed VIOLATED for a
document measured as Vietnamese, the two disagree and the criterion is set to UNKNOWN.

Criteria covered: those whose content is "Ngôn ngữ ... là tiếng Việt" (the plain rule and its
consumer-protection form "trừ trường hợp các bên có thỏa thuận khác"): a Vietnamese text
satisfies it whatever the parties agreed. "Rõ ràng, dễ hiểu" and "if another language version
exists, the more favourable one prevails" need judgement and are not touched.
"""

import re
from dataclasses import dataclass

from legal_checker.modules.compliance.automatic_review import automatic_review
from legal_checker.modules.compliance.decision_rules import load_decision_rule
from legal_checker.modules.compliance.llm_observations import PLACEHOLDER
from legal_checker.modules.compliance.reviewed_observations import build_verified_observation
from legal_checker.modules.compliance.verification import CriterionVerification
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import Evidence
from legal_checker.shared.contracts.reasoning import Gates, Observation, ReasoningRequest

POLICY = "BACKEND_LANGUAGE_CHECK_V1"
MARK = "[BACKEND_LANGUAGE_CHECK]"
LANGUAGE_RULE = re.compile(r"^Ngôn ngữ\b[^.;]*?\blà tiếng Việt\b")
_VIETNAMESE_LETTERS = frozenset(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
)
_ENGLISH_WORDS = frozenset(
    "the and of to shall this agreement party parties with for is be by in or any such "
    "which will".split()
)
MIN_WORDS = 300
MIN_VIETNAMESE_SHARE = 0.6  # Vietnamese contracts measure about 0.85
MAX_ENGLISH_SHARE = 0.005  # Vietnamese contracts measure about 0.0001
_WORD = re.compile(r"[^\W\d_]{2,}")


@dataclass(frozen=True)
class LanguageMeasure:
    words: int
    vietnamese_share: float
    english_share: float

    @property
    def vietnamese_only(self) -> bool:
        return (
            self.words >= MIN_WORDS
            and self.vietnamese_share >= MIN_VIETNAMESE_SHARE
            and self.english_share <= MAX_ENGLISH_SHARE
        )


def measure(texts) -> LanguageMeasure:
    words = _WORD.findall(" ".join(texts).lower())
    if not words:
        return LanguageMeasure(0, 0.0, 0.0)
    vietnamese = sum(1 for word in words if _VIETNAMESE_LETTERS.intersection(word))
    english = sum(1 for word in words if word in _ENGLISH_WORDS)
    return LanguageMeasure(len(words), vietnamese / len(words), english / len(words))


def is_language_criterion(criterion: dict) -> bool:
    return bool(LANGUAGE_RULE.search(str(criterion.get("noi_dung") or "")))


def _evidence_line(chunks) -> Evidence | None:
    """An exact, readable line of a selected passage: a heading or a whole sentence first."""
    lines = []
    for chunk in chunks:
        for match in re.finditer(r"[^\n]+", chunk.noi_dung):
            line = match.group(0).strip()
            words = len(_WORD.findall(line))
            if words < 4 or PLACEHOLDER.search(line):
                continue
            start = match.start() + match.group(0).index(line)
            heading = bool(re.match(r"(?:ĐIỀU|Điều)\s+\d+", line))
            sentence = line[0].isupper() and line.endswith((".", ":", ";"))
            lines.append((not heading, not sentence, -words, chunk, line, start))
    if not lines:
        return None
    *_, chunk, line, start = min(lines, key=lambda row: row[:3])
    return Evidence(
        doan_id=chunk.doan_id, trich_dan=line, ky_tu_bat_dau=start, ky_tu_ket_thuc=start + len(line)
    )


def apply_language_check(request: ReasoningRequest, knowledge, observations):
    """Return observations with the language criteria decided by measurement where safe."""
    request = ReasoningRequest.model_validate(request.model_dump())
    by_id = {o.tieu_chi_id: o for o in observations}
    targets = [
        (criterion, requirement)
        for requirement in request.payload.requirements
        if requirement.confirmed and requirement.requirement_version_id
        for criterion in knowledge.criteria_for(requirement.requirement_version_id)
        if is_language_criterion(criterion) and criterion["tieu_chi_id"] in by_id
    ]
    if not targets:
        return observations
    found = measure(chunk.noi_dung for chunk in request.payload.chunks)
    if not found.vietnamese_only:
        return observations
    chunks = {chunk.doan_id: chunk for chunk in request.payload.chunks}
    context = Context.model_validate(request.model_dump(include=set(Context.model_fields)))
    for criterion, requirement in targets:
        criterion_id = criterion["tieu_chi_id"]
        current = by_id[criterion_id]
        if current.proposed_finding == "VIOLATED":
            by_id[criterion_id] = Observation(
                tieu_chi_id=criterion_id,
                giai_thich=(
                    f"{MARK} AI đề xuất vi phạm nhưng toàn văn đo được là tiếng Việt "
                    f"({found.vietnamese_share:.0%} số từ); hai kết quả không thống nhất nên "
                    "cần chuyên viên xem."
                ),
                model_version=POLICY,
            )
            continue
        selected = [
            chunks[row.doan_id]
            for row in request.payload.retrieval
            if row.yeu_cau_ca_id == requirement.yeu_cau_ca_id
            and row.tieu_chi_id == criterion_id
            and row.duoc_chon
            and row.giai_doan == "FINAL"
            and row.doan_id in chunks
        ]
        evidence = _evidence_line(selected)
        rule, _, issues = load_decision_rule(criterion_id, "SATISFIED", knowledge)
        if evidence is None or issues or rule.get("human_verified") is not True:
            continue
        proposal = Observation(
            tieu_chi_id=criterion_id,
            proposed_finding="SATISFIED",
            giai_thich=(
                f"{MARK} Hợp đồng được lập bằng tiếng Việt: {found.vietnamese_share:.0%} trong "
                f"{found.words} từ của toàn văn mang chữ tiếng Việt, không có đoạn tiếng nước "
                "ngoài đáng kể. Đoạn trích dưới đây là một câu của chính hợp đồng."
            ),
            evidence=[evidence],
            model_version=POLICY,
            prompt_version="NOT_USED",
        )
        verification = CriterionVerification(
            **context.model_dump(),
            hop_dong_id=request.payload.hop_dong_id,
            yeu_cau_ca_id=requirement.yeu_cau_ca_id,
            tieu_chi_id=criterion_id,
            verification_reference=f"{POLICY}:{context.knowledge_snapshot_sha256}",
            # A Vietnamese text satisfies the rule whether or not the parties agreed on
            # another language, so the consumer-contract exception cannot change the result.
            gates=Gates(exceptions_resolved=True),
            local_applicability="MATCH",
            facts={
                "evaluation_target": "CONTRACT_CONTENT",
                "requirement_applicability": "CONFIRMED",
                "condition_triggered": True,
                "contract_language": "vi",
            },
            facts_verified=True,
        )
        review = automatic_review(proposal, request, knowledge, verification=verification)
        # automatic_review admits only plain contract-content types; for this measured
        # predicate the same gates apply, whatever the criterion's type.
        review = review.model_copy(
            update={
                "verification_reference": f"{POLICY}:{context.knowledge_snapshot_sha256}",
                "predicate_verified": bool(
                    review.gates.reliable() and review.local_applicability == "MATCH"
                ),
            }
        )
        by_id[criterion_id] = build_verified_observation(proposal, review, request, knowledge)
    return [by_id[o.tieu_chi_id] for o in observations]
