/**
 * Recommendations come from a template that strings labelled parts together ("Hồ sơ cần: …
 * Thông tin cần làm rõ: <engine trace in English> … Dự thảo gợi ý: …"). Readers need one line
 * saying what to do, with the rest on demand; the engine trace and the repeated reference
 * text are dropped from display (the stored report is unchanged).
 */
// The report presentation replaces a draft whose slots have no observed value with this line
// (naming the missing slots by their engine names); the draft is withheld, never filled in.
const UNBOUND_DRAFT = "Chưa tạo câu sửa gợi ý";

const LABELS = [
  "Yêu cầu hồ sơ để làm rõ đúng tiêu chí",
  "Yêu cầu bổ sung thông tin còn thiếu",
  "Các nội dung cần đối chiếu/bổ sung",
  "Hồ sơ cần",
  "Hồ sơ liên quan",
  "Thông tin cần làm rõ",
  "Nội dung tham chiếu để đối chiếu khi áp dụng",
  "Dự thảo gợi ý",
  UNBOUND_DRAFT,
  "Bằng chứng cần lưu",
  "Kiểm tra sau khắc phục",
];

/** Parts shown under "Xem gợi ý đầy đủ", with friendlier titles. */
const DETAIL_TITLES: Record<string, string> = {
  "Dự thảo gợi ý": "Gợi ý xử lý",
  [UNBOUND_DRAFT]: "Gợi ý xử lý",
  "Bằng chứng cần lưu": "Bằng chứng cần lưu",
  "Kiểm tra sau khắc phục": "Kiểm tra lại sau khi sửa",
};

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
const SPLIT = new RegExp(`(${LABELS.map(escape).join("|")}):`, "g");
// Sentences written for engineers ("Unresolved gate: …", "Provider uncertainty: …").
const ENGINE_TRACE = /\b(?:Unresolved gate|Provider uncertainty|Criterion\b|Requirement applicability|TC_[A-Z0-9_]+|[a-z]+_[a-z_]+=)/;

function firstSentence(text: string): string {
  const clean = text.replace(/\s+/g, " ").trim();
  const end = clean.search(/\.(?:\s|$)/);
  return (end > 0 ? clean.slice(0, end) : clean).replace(/[.\s]+$/, "") + ".";
}

function readable(text: string): string {
  return text
    .split(/(?<=\.)\s+/)
    .filter((sentence) => !ENGINE_TRACE.test(sentence))
    .join(" ")
    .replace(/\.\./g, ".")
    .trim();
}

/**
 * For actions that change the contract (add, amend) the template already opens with the
 * instruction ("Bổ sung vào hợp đồng điều khoản …"); that sentence is the thing to do.
 */
export function directAction(text: string): string {
  return firstSentence(readable(text) || text);
}

export type RecommendationView = { action: string; details: { title: string; text: string }[] };

export function readRecommendation(text: string): RecommendationView {
  const parts: { label: string | null; body: string }[] = [];
  let last = 0;
  let label: string | null = null;
  for (const match of text.matchAll(SPLIT)) {
    parts.push({ label, body: text.slice(last, match.index) });
    label = match[1] ?? null;
    last = (match.index ?? 0) + match[0].length;
  }
  parts.push({ label, body: text.slice(last) });
  const part = (name: string) => parts.find((p) => p.label === name)?.body.trim();
  const related =
    part("Hồ sơ liên quan") ??
    part("Các nội dung cần đối chiếu/bổ sung") ??
    part("Yêu cầu bổ sung thông tin còn thiếu");
  // Without a list of related clauses, the asked-for content itself says what to look for.
  const asked = (part("Hồ sơ cần") ?? part("Yêu cầu hồ sơ để làm rõ đúng tiêu chí"))?.replace(
    /^Chỉ kiểm tra\s+/i,
    "",
  );
  const lower = (s: string) => firstSentence(s).replace(/^./, (c) => c.toLowerCase());
  const action = related
    ? `Kiểm tra trong hợp đồng: ${lower(related)}`
    : asked
      ? `Kiểm tra hợp đồng có nội dung: ${lower(asked)}`
      : firstSentence(readable(text) || text);
  const details = parts
    .filter((p) => p.label && DETAIL_TITLES[p.label])
    .map((p) => ({
      title: DETAIL_TITLES[p.label!]!,
      text:
        p.label === UNBOUND_DRAFT
          ? "Chưa soạn được câu sửa vì thiếu dữ kiện từ hợp đồng; chuyên viên soạn trực tiếp."
          : readable(p.body),
    }))
    .filter((d) => d.text);
  return { action, details };
}
