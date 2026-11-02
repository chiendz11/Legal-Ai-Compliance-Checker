import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { apiErrorMessage } from "../../shared/api/client";
import { useCreateCase, useStartRun, useUploadContract } from "../../shared/api/queries";
import { Notice, Section } from "../../shared/components/ui";

const MAX_MB = 100;
const MARKER_TYPES = [
  ["", "Chưa rõ (để hệ thống xác định)"],
  ["NGAY_GIAO_KET", "Ngày giao kết hợp đồng"],
  ["NGAY_HIEU_LUC", "Ngày hợp đồng có hiệu lực"],
  ["NGAY_SU_KIEN", "Ngày phát sinh sự kiện"],
] as const;

const today = () => new Date().toISOString().slice(0, 10);

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
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const busy = step !== null;
  const tooLarge = !!file && file.size > MAX_MB * 1024 * 1024;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || tooLarge) return;
    setError(null);
    try {
      setStep("Đang tải tệp lên…");
      const contract = await upload.mutateAsync({ file, title: title.trim() || undefined });
      setStep("Đang tạo ca đánh giá…");
      const created = await createCase.mutateAsync({
        hop_dong_id: contract.hop_dong_id,
        ngay_danh_gia: assessedOn,
        moc_ap_dung: relevantDate || null,
        loai_moc_ap_dung: markerType || null,
        phien_ban_id: null, // backend selects the allowed deployment release
      });
      const caId = created.case.ca_id;
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
      title="Tải hợp đồng lên"
      description="Chỉ nhận PDF hoặc DOCX gốc. Hệ thống lưu tệp kèm SHA-256 rồi tạo ca đánh giá; phiên bản tri thức và quy tắc do backend chọn."
    >
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span>Tệp hợp đồng (PDF/DOCX, tối đa {MAX_MB} MB)</span>
          <input
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            required
            disabled={busy}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {tooLarge && <small className="uncertain">Tệp vượt quá {MAX_MB} MB.</small>}
        </label>
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
        <div className="field-row">
          <label className="field">
            <span>Ngày đánh giá</span>
            <input
              type="date"
              value={assessedOn}
              required
              disabled={busy}
              onChange={(e) => setAssessedOn(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Mốc áp dụng luật (nếu biết)</span>
            <input
              type="date"
              value={relevantDate}
              disabled={busy}
              onChange={(e) => setRelevantDate(e.target.value)}
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
          Để trống mốc áp dụng nếu chưa chắc: hệ thống không tự lấy ngày hôm nay làm mốc.
        </p>
        <label className="check">
          <input
            type="checkbox"
            checked={runNow}
            disabled={busy}
            onChange={(e) => setRunNow(e.target.checked)}
          />
          Chạy đánh giá ngay sau khi tải lên
        </label>
        {error && <Notice tone="bad">{error}</Notice>}
        <div className="actions">
          <button type="submit" className="button primary" disabled={!file || tooLarge || busy}>
            {step ?? "Tải lên và tạo ca"}
          </button>
        </div>
      </form>
    </Section>
  );
}
