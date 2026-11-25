import { useState, type DragEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { apiErrorMessage } from "../../shared/api/client";
import { useCreateCase, useStartRun, useUploadContract } from "../../shared/api/queries";
import { DateField } from "../../shared/components/DateField";
import { Icon } from "../../shared/components/icons";
import { Notice, Section } from "../../shared/components/ui";
import { useViewMode } from "../../shared/viewMode";

const MAX_MB = 100;
const MARKER_TYPES = [
  ["", "Tự động"],
  ["NGAY_GIAO_KET", "Ngày giao kết hợp đồng"],
  ["TEMPLATE_USE", "Ngày sử dụng mẫu (dự kiến nếu rà soát dự thảo)"],
  ["NGAY_HIEU_LUC", "Ngày hợp đồng có hiệu lực"],
  ["NGAY_SU_KIEN", "Ngày phát sinh sự kiện"],
] as const;

const ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const ACCEPTED = /\.(pdf|docx)$/i;

// Local calendar date (toISOString would give yesterday before 07:00 in Vietnam).
const today = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

const size = (bytes: number) =>
  bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`;

/**
 * C01 intake: upload the original PDF/DOCX, create a case with server-side pins, then
 * optionally start the full assessment. An unknown relevant date is sent as null.
 */
export function UploadPage() {
  const navigate = useNavigate();
  const upload = useUploadContract();
  const createCase = useCreateCase();
  const startRun = useStartRun();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [assessedOn, setAssessedOn] = useState(today());
  const [relevantDate, setRelevantDate] = useState("");
  const [markerType, setMarkerType] = useState("");
  const [runNow, setRunNow] = useState(true);
  const [reviewMode, setReviewMode] = useState<"DRAFT_REVIEW" | "FULL_ASSESSMENT">("DRAFT_REVIEW");
  const [documentSetComplete, setDocumentSetComplete] = useState(true);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  // Steps already done in a submit that later failed: a retry resumes from the failed step
  // instead of uploading the file or creating the case a second time.
  const [done, setDone] = useState<{ file: File; hopDongId: string; caseKey?: string; caId?: string } | null>(
    null,
  );

  const simple = useViewMode() === "simple";
  const busy = step !== null;
  const tooLarge = !!file && file.size > MAX_MB * 1024 * 1024;

  function pick(chosen: File | null | undefined) {
    if (!chosen || busy) return;
    if (!ACCEPTED.test(chosen.name)) {
      setError("Chỉ nhận tệp PDF hoặc DOCX.");
      return;
    }
    setError(null);
    setFile(chosen);
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files[0]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || tooLarge) return;
    setError(null);
    const caseBody = {
      ngay_danh_gia: assessedOn,
      moc_ap_dung: relevantDate || null,
      loai_moc_ap_dung: markerType || null,
      review_mode: reviewMode,
      document_set_complete: documentSetComplete,
      phien_ban_id: null, // backend selects the allowed deployment release
    };
    const caseKey = JSON.stringify(caseBody);
    try {
      let progress = done?.file === file ? done : null;
      if (!progress) {
        setStep("Đang tải tệp lên…");
        const contract = await upload.mutateAsync({ file, title: title.trim() || undefined });
        progress = { file, hopDongId: contract.hop_dong_id };
        setDone(progress);
      }
      let caId = progress.caseKey === caseKey ? progress.caId : undefined;
      if (!caId) {
        setStep("Đang tạo ca đánh giá…");
        const created = await createCase.mutateAsync({ hop_dong_id: progress.hopDongId, ...caseBody });
        caId = created.case.ca_id;
        setDone({ ...progress, caseKey, caId });
      }
      if (!runNow) {
        navigate(`/?q=${encodeURIComponent(caId)}`);
        return;
      }
      setStep("Đang xếp hàng đánh giá…");
      const accepted = await startRun.mutateAsync(caId);
      navigate(`/cases/${caId}/runs/${accepted.context.run_id}`);
    } catch (caught) {
      setError(apiErrorMessage(caught) ?? "Không hoàn tất được. Kiểm tra backend và thử lại.");
      setStep(null);
    }
  }

  return (
    <Section
      title="Tải hợp đồng mới"
      description="Hệ thống kiểm tra hợp đồng mua bán căn hộ chung cư với quy định pháp luật và chỉ ra điểm cần chú ý. Nhận tệp PDF (có chữ hoặc bản scan) và DOCX."
    >
      <ol className="upload-steps" aria-label="Các bước">
        <li>
          <b>1. Tải lên</b>
          <span>Chọn tệp hợp đồng.</span>
        </li>
        <li>
          <b>2. Hệ thống phân tích</b>
          <span>Từ vài chục giây đến vài phút.</span>
        </li>
        <li>
          <b>3. Đọc báo cáo</b>
          <span>Kết luận, lý do và việc cần làm.</span>
        </li>
      </ol>
      <form className="form" onSubmit={submit}>
        <div className="field">
          <span>Tệp hợp đồng</span>
          <label
            className={`dropzone${dragging ? " drag" : ""}${file ? " has-file" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={drop}
          >
            <input
              type="file"
              className="sr-only"
              accept={ACCEPT}
              disabled={busy}
              onChange={(e) => {
                pick(e.target.files?.[0]);
                e.target.value = ""; // picking the same file again after an error still fires
              }}
            />
            <span className="dz-ico">
              <Icon name={file ? "file" : "upload"} />
            </span>
            {file ? (
              <span className="dz-text">
                <b>{file.name}</b>
                <span className="muted small">
                  {size(file.size)} · bấm hoặc kéo tệp khác vào để đổi
                </span>
              </span>
            ) : (
              <span className="dz-text">
                <b>Kéo thả hợp đồng vào đây hoặc bấm để chọn</b>
                <span className="muted small">
                  PDF (có chữ hoặc bản scan) hoặc DOCX, tối đa {MAX_MB} MB
                </span>
              </span>
            )}
          </label>
          {tooLarge && <small className="uncertain">Tệp vượt quá {MAX_MB} MB.</small>}
        </div>
        <label className="field">
          <span>Tên tài liệu (tùy chọn)</span>
          <input
            type="text"
            value={title}
            maxLength={300}
            placeholder={file?.name ?? "Ví dụ: Hợp đồng mua bán căn hộ A1-12"}
            disabled={busy}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        {/* Simple mode keeps the defaults: draft review, automatic dates, analyse at once. */}
        {!simple && (
        <details className="more-filters">
          <summary>Tùy chọn nâng cao (thường không cần đổi)</summary>
          <div className="field-row">
            <label className="field">
              <span>Ngày đánh giá</span>
              <DateField
                value={assessedOn}
                clearable={false}
                disabled={busy}
                onChange={setAssessedOn}
              />
            </label>
            <label className="field">
              <span>Mốc áp dụng luật (nếu biết)</span>
              <DateField
                value={relevantDate}
                placeholder="Chưa rõ"
                disabled={busy}
                onChange={setRelevantDate}
              />
            </label>
            <label className="field">
              <span>Loại mốc</span>
              <select value={markerType} disabled={busy} onChange={(e) => setMarkerType(e.target.value)}>
                {MARKER_TYPES.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="small muted">
            Mốc áp dụng luật: để trống nếu chưa chắc. Hệ thống tự đọc ngày ký trong hợp đồng và không
            lấy ngày hôm nay làm mốc. Mốc chỉ dùng cho đúng loại đã chọn; khi rà soát dự thảo, đây là
            thời điểm dự kiến, không chứng minh hợp đồng đã được ký.
          </p>
          <label className="field">
            <span>Phạm vi đánh giá</span>
            <select
              value={reviewMode}
              disabled={busy}
              onChange={(e) => setReviewMode(e.target.value as typeof reviewMode)}
            >
              <option value="DRAFT_REVIEW">Rà soát dự thảo trước khi ký</option>
              <option value="FULL_ASSESSMENT">Đánh giá cả việc ký kết và thực hiện hợp đồng</option>
            </select>
          </label>
          <p className="small muted">
            Rà soát dự thảo chỉ kiểm tra nội dung các điều khoản. Việc đã ký, thu tiền, bàn giao và
            giấy tờ bên ngoài được ghi là ngoài phạm vi, không được coi là đã đáp ứng.
          </p>
          <label className="check">
            <input
              type="checkbox"
              checked={documentSetComplete}
              disabled={busy}
              onChange={(e) => setDocumentSetComplete(e.target.checked)}
            />
            Tệp tải lên đã gồm đủ thân hợp đồng và các phụ lục cần rà soát
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={runNow}
              disabled={busy}
              onChange={(e) => setRunNow(e.target.checked)}
            />
            Phân tích ngay sau khi tải lên
          </label>
        </details>
        )}
        {error && <Notice tone="bad">{error}</Notice>}
        <div className="actions">
          <button type="submit" className="button primary" disabled={!file || tooLarge || busy}>
            {step ?? (runNow ? "Tải lên và phân tích" : "Tải lên")}
          </button>
        </div>
        <p className="small muted">
          Chỉ đánh giá hợp đồng mua bán căn hộ chung cư; tài liệu loại khác sẽ được báo là không xử
          lý. Nhận PDF (kể cả bản scan) và DOCX.
        </p>
      </form>
    </Section>
  );
}
