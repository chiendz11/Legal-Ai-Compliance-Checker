import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import {
  apiErrorCode,
  apiErrorMessage,
  type ReportContent,
  type ReportRecord,
  type ReviewAction,
  type TargetReviewState,
} from "../../shared/api/client";
import {
  useAddReview,
  usePublishReport,
  useRebuildReport,
  useReviewState,
} from "../../shared/api/queries";
import { useCan } from "../../shared/auth";
import { Empty, LoadState, Notice, Section, StatusBadge } from "../../shared/components/ui";
import { label, type LabelKind } from "../../shared/labels";
import { useReportNav, type TabId } from "../reports/nav";
import { criterionText, requirementText, riskTitle } from "../reports/reportIndex";

type Field = { name: string; title: string; options?: readonly string[]; labels?: LabelKind };
type Kind = {
  title: string;
  tab: TabId;
  fields: Field[]; // what an OVERRIDE may change; mirrors backend TARGETS
};

const SEVERITY = ["LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"] as const;
const KINDS: Record<string, Kind> = {
  ket_qua_tuan_thu: {
    title: "Kết luận yêu cầu",
    tab: "compliance",
    fields: [
      {
        name: "status",
        title: "Trạng thái",
        options: ["COMPLIANT", "PARTIAL", "NON_COMPLIANT", "INSUFFICIENT"],
        labels: "requirement",
      },
    ],
  },
  ket_qua_tieu_chi: {
    title: "Tiêu chí",
    tab: "compliance",
    fields: [
      {
        name: "finding",
        title: "Kết quả",
        options: ["SATISFIED", "MISSING", "VIOLATED", "UNKNOWN"],
        labels: "criterion",
      },
      { name: "giai_thich", title: "Giải thích" },
    ],
  },
  phat_hien_vien_dan: {
    title: "Viện dẫn",
    tab: "citations",
    fields: [
      {
        name: "status",
        title: "Trạng thái",
        options: ["VALID", "STALE", "INVALID", "UNKNOWN"],
        labels: "citation",
      },
      { name: "ly_do", title: "Lý do" },
    ],
  },
  ket_qua_rui_ro: {
    title: "Rủi ro",
    tab: "risks",
    fields: [
      { name: "severity", title: "Mức độ", options: SEVERITY, labels: "severity" },
      { name: "giai_thich", title: "Giải thích" },
    ],
  },
  khuyen_nghi_danh_gia: {
    title: "Khuyến nghị",
    tab: "recommendations",
    fields: [
      { name: "uu_tien", title: "Ưu tiên", options: SEVERITY, labels: "severity" },
      { name: "noi_dung", title: "Nội dung" },
    ],
  },
};

const ACTIONS: { action: ReviewAction; text: string }[] = [
  { action: "CONFIRM", text: "Xác nhận" },
  { action: "OVERRIDE", text: "Chỉnh sửa" },
  { action: "REQUEST_MORE_EVIDENCE", text: "Yêu cầu bổ sung" },
  { action: "REJECT", text: "Bác bỏ" },
  { action: "COMMENT", text: "Ghi chú" },
];

type Machine = { title: string; values: Record<string, unknown>; focus: string };

/** Machine values of each target, read from the report (which never contains reviewer edits). */
function machineIndex(content: ReportContent) {
  const map = new Map<string, Machine>();
  const put = (kind: string, id: string, machine: Machine) => map.set(`${kind}/${id}`, machine);
  for (const r of content.compliance.requirement_results)
    put("ket_qua_tuan_thu", r.tuan_thu_id, {
      title: requirementText(r),
      values: r,
      focus: r.yeu_cau_ca_id,
    });
  for (const c of content.compliance.criterion_results)
    put("ket_qua_tieu_chi", c.ket_qua_id, {
      title: criterionText(c),
      values: c,
      focus: c.ket_qua_id,
    });
  for (const f of content.citation_validation.findings)
    put("phat_hien_vien_dan", f.finding_id, {
      title: f.vien_dan_id,
      values: f,
      focus: f.finding_id,
    });
  for (const r of [
    ...content.risks.compliance,
    ...content.risks.citation,
    ...content.risks.verification,
  ])
    put("ket_qua_rui_ro", r.ket_qua_rui_ro_id, {
      title: riskTitle(r),
      values: r,
      focus: r.ket_qua_rui_ro_id,
    });
  for (const k of content.recommendations)
    put("khuyen_nghi_danh_gia", k.khuyen_nghi_ca_id, {
      title: k.noi_dung,
      values: k,
      focus: k.khuyen_nghi_ca_id,
    });
  return map;
}

const keyOf = (t: { doi_tuong_loai: string; doi_tuong_id: string }) =>
  `${t.doi_tuong_loai}/${t.doi_tuong_id}`;

type Filter = "all" | "open" | "blocking";
const PAGE = 50;

/**
 * Reviewer workbench (C12): each machine finding gets a decision with a reason. Edits are an
 * effective layer on top of the AI output, and every review quotes the hash it saw so two
 * reviewers cannot silently overwrite each other. Publication needs a rebuilt version.
 */
export function ReviewWorkbench({ record }: { record: ReportRecord }) {
  const caId = record.report.ca_id;
  const state = useReviewState(caId, record.run_id);
  const machine = useMemo(() => machineIndex(record.report.report_json), [record]);
  const [filter, setFilter] = useState<Filter>("all");
  // A run can have hundreds of findings; render them a page at a time.
  const [limit, setLimit] = useState(PAGE);
  if (!state.data) return <LoadState error={state.error} />;
  const { targets, blockers, review_revision: revision } = state.data;
  const blocking = new Set(blockers.map((b) => `${b.doi_tuong_loai}/${b.doi_tuong_id}`));
  const shown = targets.filter((t) =>
    filter === "open"
      ? t.latest_decision == null
      : filter === "blocking"
        ? blocking.has(keyOf(t))
        : true,
  );
  const reviewed = targets.filter((t) => t.latest_decision != null).length;

  return (
    <Section
      title="Rà soát của chuyên viên"
      description="Quyết định của người review được lưu thành lịch sử không sửa được (C12). Kết quả máy giữ nguyên; giá trị chỉnh sửa là lớp hiệu lực nằm trên."
    >
      <PublishPanel
        record={record}
        revision={revision}
        blockers={blockers.length}
        reviewed={reviewed}
        total={targets.length}
      />
      <div className="filters" role="group" aria-label="Lọc mục review">
        {(
          [
            ["all", `Tất cả (${targets.length})`],
            ["open", `Chưa review (${targets.length - reviewed})`],
            ["blocking", `Chặn phát hành (${blockers.length})`],
          ] as const
        ).map(([id, text]) => (
          <button
            key={id}
            type="button"
            className="button"
            aria-pressed={filter === id}
            onClick={() => {
              setFilter(id);
              setLimit(PAGE);
            }}
          >
            {text}
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <Empty>Không có mục nào trong bộ lọc này.</Empty>
      ) : (
        <div className="stack">
          {shown.slice(0, limit).map((target) => (
            <TargetCard
              key={keyOf(target)}
              caId={caId}
              runId={record.run_id}
              target={target}
              machine={machine.get(keyOf(target))}
              blocking={blocking.has(keyOf(target))}
              locked={record.report.report_status === "PUBLISHED"}
            />
          ))}
          {shown.length > limit && (
            <div className="actions">
              <button type="button" className="button" onClick={() => setLimit(limit + PAGE)}>
                Xem thêm {Math.min(PAGE, shown.length - limit)} mục ({limit}/{shown.length})
              </button>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function PublishPanel({
  record,
  revision,
  blockers,
  reviewed,
  total,
}: {
  record: ReportRecord;
  revision: string;
  blockers: number;
  reviewed: number;
  total: number;
}) {
  const navigate = useNavigate();
  const can = useCan();
  const rebuild = useRebuildReport(record.report.ca_id, record.run_id);
  const publish = usePublishReport();
  const published = record.report.report_status === "PUBLISHED";
  const current = record.review_revision === revision;
  const ready = current && revision !== "none" && blockers === 0 && !published;
  const open = (id: string) => navigate(`/reports/${encodeURIComponent(id)}?tab=review`);
  const error = rebuild.error ?? publish.error;

  return (
    <div className="card-flat review-panel">
      <p>
        Đã review <strong>{reviewed}</strong>/{total} mục · revision hiện tại{" "}
        <code>{revision}</code> · phiên bản đang xem dựa trên <code>{record.review_revision}</code>
      </p>
      {published ? (
        <Notice tone="info">Phiên bản này đã phát hành và không thay đổi được nữa.</Notice>
      ) : !current ? (
        <Notice tone="warn">
          Có review mới hơn phiên bản báo cáo đang xem. Tạo phiên bản mới để đưa các review vào
          báo cáo trước khi phát hành.
        </Notice>
      ) : blockers > 0 ? (
        <Notice tone="warn">
          Còn {blockers} mục chặn phát hành: kết luận không tuân thủ / tuân thủ một phần, rủi ro
          cao chưa xác nhận, hoặc đang yêu cầu bổ sung / bị bác bỏ.
        </Notice>
      ) : revision === "none" ? (
        <Notice tone="info">Cần ít nhất một review trước khi phát hành.</Notice>
      ) : null}
      {error && (
        <Notice tone="bad">{apiErrorMessage(error) ?? "Không thực hiện được thao tác."}</Notice>
      )}
      <div className="actions">
        {!published && !current && (can("reviewer") || can("uploader")) && (
          <button
            type="button"
            className="button primary"
            disabled={rebuild.isPending}
            onClick={() =>
              rebuild.mutate(undefined, { onSuccess: (next) => open(next.report.bao_cao_id) })
            }
          >
            {rebuild.isPending ? "Đang tạo…" : "Tạo phiên bản báo cáo từ review"}
          </button>
        )}
        {!published && can("publisher") && (
          <button
            type="button"
            className="button primary"
            disabled={!ready || publish.isPending}
            title={ready ? undefined : "Chưa đủ điều kiện phát hành"}
            onClick={() =>
              publish.mutate(
                { baoCaoId: record.report.bao_cao_id, revision },
                { onSuccess: (next) => open(next.report.bao_cao_id) },
              )
            }
          >
            {publish.isPending ? "Đang phát hành…" : "Phát hành báo cáo"}
          </button>
        )}
      </div>
    </div>
  );
}

function TargetCard({
  caId,
  runId,
  target,
  machine,
  blocking,
  locked,
}: {
  caId: string;
  runId: string;
  target: TargetReviewState;
  machine: Machine | undefined;
  blocking: boolean;
  locked: boolean;
}) {
  const kind = KINDS[target.doi_tuong_loai];
  const { go } = useReportNav();
  const can = useCan();
  const [editing, setEditing] = useState(false);
  const overrides = target.overrides ?? {};
  return (
    <article className={`card-flat review-target${blocking ? " blocking" : ""}`}>
      <div className="criterion-head">
        <span className="badge tone-neutral">{kind?.title ?? target.doi_tuong_loai}</span>
        <strong className="card-title">{machine?.title ?? target.doi_tuong_id}</strong>
        {target.latest_decision ? (
          <StatusBadge kind="reviewAction" code={target.latest_decision} />
        ) : (
          <span className="badge tone-unknown">Chưa review</span>
        )}
        {blocking && <span className="badge tone-bad">Chặn phát hành</span>}
      </div>
      <dl className="fields compact">
        {kind?.fields.map((field) => {
          const before = machine?.values[field.name];
          const after = overrides[field.name];
          return (
            <div key={field.name}>
              <dt>{field.title}</dt>
              <dd>
                <FieldValue field={field} value={before} />
                {after !== undefined && (
                  <>
                    {" → "}
                    <ins>
                      <FieldValue field={field} value={after} />
                    </ins>{" "}
                    <span className="muted small">(chuyên viên chỉnh)</span>
                  </>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="small muted">
        <code>{target.doi_tuong_id}</code> · {target.review_count} review ·{" "}
        {machine && kind && (
          <button type="button" className="link" onClick={() => go(kind.tab, machine.focus)}>
            Xem trong báo cáo
          </button>
        )}
      </p>
      {!locked &&
        can("reviewer") &&
        (editing ? (
          <ReviewForm
            caId={caId}
            runId={runId}
            target={target}
            kind={kind}
            current={{ ...machine?.values, ...overrides }}
            onDone={() => setEditing(false)}
          />
        ) : (
          <button type="button" className="button" onClick={() => setEditing(true)}>
            Review mục này
          </button>
        ))}
    </article>
  );
}

function FieldValue({ field, value }: { field: Field; value: unknown }) {
  if (value == null || value === "") return <span className="muted">—</span>;
  if (field.labels) return <>{label(field.labels, String(value)).text}</>;
  return <>{String(value)}</>;
}

function ReviewForm({
  caId,
  runId,
  target,
  kind,
  current,
  onDone,
}: {
  caId: string;
  runId: string;
  target: TargetReviewState;
  kind: Kind | undefined;
  current: Record<string, unknown>;
  onDone: () => void;
}) {
  const add = useAddReview(caId, runId);
  const [action, setAction] = useState<ReviewAction>("CONFIRM");
  const [reason, setReason] = useState("");
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries((kind?.fields ?? []).map((f) => [f.name, String(current[f.name] ?? "")])),
  );
  // Only fields the reviewer actually changed are sent; the server rejects no-op overrides.
  const changed = Object.fromEntries(
    Object.entries(values).filter(([name, value]) => value !== String(current[name] ?? "")),
  );
  const overrideEmpty = action === "OVERRIDE" && Object.keys(changed).length === 0;

  function submit(event: FormEvent) {
    event.preventDefault();
    add.mutate(
      {
        target: { doi_tuong_loai: target.doi_tuong_loai, doi_tuong_id: target.doi_tuong_id },
        action,
        after: action === "OVERRIDE" ? changed : {},
        reason: reason.trim(),
        expected_target_sha256: target.target_sha256,
      },
      { onSuccess: onDone },
    );
  }

  const stale = apiErrorCode(add.error) === "STALE_REVIEW";
  return (
    <form className="form review-form" onSubmit={submit}>
      <div className="segmented" role="radiogroup" aria-label="Quyết định">
        {ACTIONS.map((a) => (
          <label key={a.action} className="check">
            <input
              type="radio"
              value={a.action}
              name={`action-${target.doi_tuong_id}`}
              checked={action === a.action}
              onChange={() => setAction(a.action)}
            />
            {a.text}
          </label>
        ))}
      </div>
      {action === "OVERRIDE" &&
        kind?.fields.map((field) => (
          <label key={field.name} className="field">
            <span>{field.title}</span>
            {field.options ? (
              <select
                value={values[field.name]}
                onChange={(e) => setValues({ ...values, [field.name]: e.target.value })}
              >
                {field.options.map((option) => (
                  <option key={option} value={option}>
                    {field.labels ? label(field.labels, option).text : option}
                  </option>
                ))}
              </select>
            ) : (
              <textarea
                rows={3}
                value={values[field.name]}
                onChange={(e) => setValues({ ...values, [field.name]: e.target.value })}
              />
            )}
          </label>
        ))}
      <label className="field">
        <span>Lý do (bắt buộc, lưu vào nhật ký review)</span>
        <textarea
          rows={2}
          required
          maxLength={4000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      {stale ? (
        <Notice tone="warn">
          Mục này vừa được người khác review; trạng thái mới đã được tải lại. Kiểm tra rồi gửi
          lại.
        </Notice>
      ) : (
        add.error && (
          <Notice tone="bad">{apiErrorMessage(add.error) ?? "Không lưu được review."}</Notice>
        )
      )}
      <div className="actions">
        <button
          type="submit"
          className="button primary"
          disabled={add.isPending || !reason.trim() || overrideEmpty}
        >
          {add.isPending ? "Đang lưu…" : "Lưu review"}
        </button>
        <button type="button" className="button" onClick={onDone}>
          Hủy
        </button>
      </div>
    </form>
  );
}
