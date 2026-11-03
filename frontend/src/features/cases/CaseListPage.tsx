import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useCases, useStartRun, type CaseQuery } from "../../shared/api/queries";
import { useCan } from "../../shared/auth";
import { DateField } from "../../shared/components/DateField";
import { Icon } from "../../shared/components/icons";
import { Empty, LoadState, Notice, Section, StatusBadge, Table } from "../../shared/components/ui";
import { label } from "../../shared/labels";

const PAGE_SIZE = 20;
const FILTER_KEYS = ["q", "run_status", "requirement_status", "date_from", "date_to", "sort"] as const;
const REQUIREMENT_ORDER = ["NON_COMPLIANT", "PARTIAL", "INSUFFICIENT", "COMPLIANT"];

/** History: the tenant's cases with their latest run/report, filtered server-side via the URL. */
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
  const can = useCan();
  return (
    <Section
      title="Lịch sử đánh giá"
      description={`${data ? `${data.total} ca` : "…"} của tổ chức bạn. Xem lại báo cáo không chạy lại đánh giá.`}
      actions={
        can("uploader") && (
          <Link className="button primary" to="/upload">
            <Icon name="upload" />
            Tải hợp đồng mới
          </Link>
        )
      }
    >
      <Filters params={params} update={update} />
      {startRun.error && (
        <Notice tone="bad">Không khởi chạy được đánh giá. Kiểm tra backend và thử lại.</Notice>
      )}
      {!data ? (
        <LoadState error={error} />
      ) : data.items.length === 0 ? (
        <Empty>Không có ca nào khớp bộ lọc.</Empty>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>Ca / Tài liệu</th>
              <th>Ngày đánh giá</th>
              <th>Mốc áp dụng</th>
              <th>Run gần nhất</th>
              <th>Kết quả yêu cầu</th>
              <th />
            </tr>
          </thead>
          <tbody className={isFetching ? "loading" : undefined}>
            {data.items.map((item) => {
              const c = item.case;
              return (
                <tr key={c.ca_id}>
                  <td>
                    <code>{c.ca_id}</code>
                    <div className="small muted">{item.ten_tai_lieu ?? c.hop_dong_id}</div>
                  </td>
                  <td>{c.assessment_context.ngay_danh_gia}</td>
                  <td>{c.assessment_context.moc_ap_dung ?? <span className="null">chưa rõ</span>}</td>
                  <td>
                    {item.latest_run_id ? (
                      <Link to={`/cases/${c.ca_id}/runs/${item.latest_run_id}`}>
                        <StatusBadge kind="runStatus" code={item.latest_run_status} />
                      </Link>
                    ) : (
                      <span className="muted">chưa chạy</span>
                    )}
                  </td>
                  <td>
                    <StatusCounts counts={item.requirement_status_counts ?? {}} />
                  </td>
                  <td>
                    {/* flex lives on an inner box: a flex <td> stops being a table cell */}
                    <div className="row-actions">
                      {item.latest_report_id && (
                        <Link className="button" to={`/reports/${item.latest_report_id}`}>
                          Báo cáo
                        </Link>
                      )}
                      <button
                        type="button"
                        className="button"
                        disabled={startRun.isPending}
                        onClick={() => run(c.ca_id)}
                      >
                        {item.latest_run_id ? "Chạy lại" : "Chạy đánh giá"}
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
  return (
    <div className="filters" role="search">
      <label className="field grow">
        <span>Tìm</span>
        <input
          type="search"
          value={text}
          placeholder="Mã ca, mã hợp đồng hoặc tên tài liệu"
          onChange={(e) => setText(e.target.value)}
        />
      </label>
      <label className="field">
        <span>Trạng thái run</span>
        {select("run_status", [
          ["", "Tất cả"],
          ["COMPLETED", "Hoàn tất"],
          ["RUNNING", "Đang chạy"],
          ["QUEUED", "Đang chờ"],
          ["FAILED", "Lỗi"],
          ["NONE", "Chưa chạy"],
        ])}
      </label>
      <label className="field">
        <span>Có yêu cầu</span>
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
          ["", "Mã ca"],
          ["-latest_run", "Run mới nhất"],
          ["-ngay_danh_gia", "Ngày đánh giá mới nhất"],
          ["ngay_danh_gia", "Ngày đánh giá cũ nhất"],
        ])}
      </label>
      {anyFilter && (
        <button
          type="button"
          className="button"
          onClick={() => {
            setText("");
            update(Object.fromEntries(FILTER_KEYS.map((key) => [key, null])));
          }}
        >
          Xóa lọc
        </button>
      )}
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
