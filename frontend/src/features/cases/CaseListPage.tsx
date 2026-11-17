import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useCases, useStartRun, type CaseQuery } from "../../shared/api/queries";
import { useCan } from "../../shared/auth";
import { DateField } from "../../shared/components/DateField";
import { Icon } from "../../shared/components/icons";
import { LoadState, Notice, Section, Table } from "../../shared/components/ui";
import { label } from "../../shared/labels";
import { viDate } from "../reports/explain";

const PAGE_SIZE = 20;
const FILTER_KEYS = ["q", "run_status", "requirement_status", "date_from", "date_to", "sort"] as const;
const REQUIREMENT_ORDER = ["NON_COMPLIANT", "PARTIAL", "INSUFFICIENT", "COMPLIANT"];

/** Latest run status in words a reader understands. */
const RUN_STATE: Record<string, [string, string]> = {
  QUEUED: ["Đang chờ phân tích", "info"],
  RUNNING: ["Đang phân tích", "info"],
  COMPLETED: ["Đã có kết quả", "good"],
  FAILED: ["Không xử lý được", "bad"],
};

/** The tenant's contracts with their latest analysis, filtered server-side via the URL. */
export function CaseListPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const query: CaseQuery = { page, page_size: PAGE_SIZE };
  for (const key of FILTER_KEYS) {
    const value = params.get(key);
    if (value) (query as Record<string, string>)[key] = value;
  }
  const { data, error, isFetching } = useCases(query);
  const navigate = useNavigate();
  const startRun = useStartRun();
  const can = useCan();

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  };

  const run = (caId: string) =>
    startRun.mutate(caId, {
      onSuccess: (accepted) => navigate(`/cases/${caId}/runs/${accepted.context.run_id}`),
    });

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const filtered = FILTER_KEYS.some((key) => params.get(key));
  return (
    <Section
      title="Hợp đồng"
      description={
        <>
          {data ? `${data.total} hợp đồng` : "Các hợp đồng"} đã tải lên và kết quả phân tích gần
          nhất. Bấm <b>Xem báo cáo</b> để đọc kết quả.{" "}
          <Link to="/help">Hướng dẫn sử dụng</Link>
        </>
      }
      actions={
        can("uploader") && (
          <Link className="button primary" to="/upload">
            <Icon name="plus" />
            Tải hợp đồng mới
          </Link>
        )
      }
    >
      <Filters params={params} update={update} />
      {startRun.error && (
        <Notice tone="bad">Không bắt đầu phân tích được. Kiểm tra máy chủ rồi thử lại.</Notice>
      )}
      {!data ? (
        <LoadState error={error} />
      ) : data.items.length === 0 ? (
        <div className="empty-state">
          {filtered ? (
            <p>Không có hợp đồng nào khớp bộ lọc.</p>
          ) : (
            <>
              <p>
                <strong>Chưa có hợp đồng nào.</strong> Tải hợp đồng mua bán căn hộ lên để hệ thống
                kiểm tra.
              </p>
              {can("uploader") && (
                <Link className="button primary" to="/upload">
                  Tải hợp đồng đầu tiên
                </Link>
              )}
            </>
          )}
        </div>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>Tài liệu</th>
              <th>Tình trạng</th>
              <th>Kết quả</th>
              <th>Ngày đánh giá</th>
              <th />
            </tr>
          </thead>
          <tbody className={isFetching ? "loading" : undefined}>
            {data.items.map((item) => {
              const c = item.case;
              const state = item.latest_run_status ? RUN_STATE[item.latest_run_status] : null;
              const runUrl = item.latest_run_id ? `/cases/${c.ca_id}/runs/${item.latest_run_id}` : null;
              return (
                <tr key={c.ca_id}>
                  <td>
                    <div className="doc-name">{item.ten_tai_lieu ?? `Hợp đồng ${c.hop_dong_id}`}</div>
                    <code className="code-ref">{c.ca_id}</code>
                  </td>
                  <td>
                    {state ? (
                      <span className={`badge tone-${state[1]}`}>{state[0]}</span>
                    ) : (
                      <span className="badge tone-neutral">Chưa phân tích</span>
                    )}
                  </td>
                  <td>
                    {item.latest_run_status === "FAILED" && runUrl ? (
                      <Link to={runUrl} className="small">
                        Xem lý do
                      </Link>
                    ) : (
                      <StatusCounts counts={item.requirement_status_counts ?? {}} />
                    )}
                  </td>
                  <td className="small">{viDate(c.assessment_context.ngay_danh_gia)}</td>
                  <td>
                    {/* flex lives on an inner box: a flex <td> stops being a table cell */}
                    <div className="row-actions">
                      {item.latest_report_id ? (
                        <Link className="button primary" to={`/reports/${item.latest_report_id}`}>
                          Xem báo cáo
                        </Link>
                      ) : runUrl && item.latest_run_status !== "FAILED" ? (
                        <Link className="button primary" to={runUrl}>
                          Xem tiến độ
                        </Link>
                      ) : null}
                      <button
                        type="button"
                        className="button ghost"
                        disabled={startRun.isPending}
                        onClick={() => run(c.ca_id)}
                        title="Phân tích lại hợp đồng này với dữ liệu và cấu hình hiện tại"
                      >
                        {item.latest_run_id ? "Chạy lại" : "Phân tích"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      )}
      {pages > 1 && (
        <nav className="pager" aria-label="Phân trang">
          <button
            type="button"
            className="button"
            disabled={page <= 1}
            onClick={() => update({ page: String(page - 1) })}
          >
            Trước
          </button>
          <span>
            Trang {page}/{pages}
          </span>
          <button
            type="button"
            className="button"
            disabled={page >= pages}
            onClick={() => update({ page: String(page + 1) })}
          >
            Sau
          </button>
        </nav>
      )}
    </Section>
  );
}

function Filters({
  params,
  update,
}: {
  params: URLSearchParams;
  update: (changes: Record<string, string | null>) => void;
}) {
  // Debounce free text so typing does not fire a request per keystroke.
  const [text, setText] = useState(params.get("q") ?? "");
  useEffect(() => {
    const timer = setTimeout(() => {
      if (text !== (params.get("q") ?? "")) update({ q: text.trim() || null });
    }, 350);
    return () => clearTimeout(timer);
    // Only the typed text should restart the debounce, not URL changes from other filters.
  }, [text]);

  const select = (key: string, options: [string, string][]) => (
    <select value={params.get(key) ?? ""} onChange={(e) => update({ [key]: e.target.value || null })}>
      {options.map(([value, text]) => (
        <option key={value} value={value}>
          {text}
        </option>
      ))}
    </select>
  );
  const anyFilter = FILTER_KEYS.some((key) => params.get(key));
  const moreActive = ["requirement_status", "date_from", "date_to", "sort"].some((k) => params.get(k));
  return (
    <div className="filter-block" role="search">
      <div className="filters">
        <label className="field grow">
          <span>Tìm hợp đồng</span>
          <input
            type="search"
            value={text}
            placeholder="Tên tài liệu hoặc mã"
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Tình trạng</span>
          {select("run_status", [
            ["", "Tất cả"],
            ["COMPLETED", "Đã có kết quả"],
            ["RUNNING", "Đang phân tích"],
            ["QUEUED", "Đang chờ"],
            ["FAILED", "Không xử lý được"],
            ["NONE", "Chưa phân tích"],
          ])}
        </label>
        {anyFilter && (
          <button
            type="button"
            className="button ghost"
            onClick={() => {
              setText("");
              update(Object.fromEntries(FILTER_KEYS.map((key) => [key, null])));
            }}
          >
            Xóa lọc
          </button>
        )}
      </div>
      <details className="more-filters" open={moreActive || undefined}>
        <summary>Bộ lọc khác</summary>
        <div className="filters">
          <label className="field">
            <span>Có kết luận</span>
            {select("requirement_status", [
              ["", "Bất kỳ"],
              ["NON_COMPLIANT", "Không tuân thủ"],
              ["PARTIAL", "Tuân thủ một phần"],
              ["INSUFFICIENT", "Chưa đủ căn cứ"],
              ["COMPLIANT", "Tuân thủ"],
            ])}
          </label>
          <label className="field">
            <span>Từ ngày</span>
            <DateField
              value={params.get("date_from") ?? ""}
              placeholder="Bất kỳ"
              onChange={(value) => update({ date_from: value || null })}
            />
          </label>
          <label className="field">
            <span>Đến ngày</span>
            <DateField
              value={params.get("date_to") ?? ""}
              placeholder="Bất kỳ"
              onChange={(value) => update({ date_to: value || null })}
            />
          </label>
          <label className="field">
            <span>Sắp xếp</span>
            {select("sort", [
              ["", "Mới hoạt động gần nhất"],
              ["-ngay_danh_gia", "Ngày đánh giá mới nhất"],
              ["ngay_danh_gia", "Ngày đánh giá cũ nhất"],
              ["-latest_run", "Lần chạy mới nhất"],
              ["ca_id", "Theo mã"],
            ])}
          </label>
        </div>
      </details>
    </div>
  );
}

function StatusCounts({ counts }: { counts: Record<string, number> }) {
  const entries = REQUIREMENT_ORDER.filter((code) => counts[code]);
  if (!entries.length) return <span className="muted small">—</span>;
  return (
    <span className="ids">
      {entries.map((code) => {
        const { text, tone } = label("requirement", code);
        return (
          <span key={code} className={`badge tone-${tone}`} title={text}>
            {counts[code]} {text.toLowerCase()}
          </span>
        );
      })}
    </span>
  );
}
