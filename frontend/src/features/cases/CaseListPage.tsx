import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useCases, useStartRun } from "../../shared/api/queries";
import { Empty, LoadState, Notice, Section, StatusBadge, Table } from "../../shared/components/ui";

const PAGE_SIZE = 20;

export function CaseListPage() {
  const [page, setPage] = useState(1);
  const { data, error } = useCases(page);
  const navigate = useNavigate();
  const startRun = useStartRun();
  if (!data) return <LoadState error={error} />;
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  const run = (caId: string) =>
    startRun.mutate(caId, {
      onSuccess: (accepted) => navigate(`/cases/${caId}/runs/${accepted.context.run_id}`),
    });

  return (
    <Section title="Ca đánh giá" description={`${data.total} ca bạn có quyền xem.`}>
      {startRun.error && (
        <Notice tone="bad">Không khởi chạy được đánh giá. Kiểm tra backend và thử lại.</Notice>
      )}
      {data.items.length === 0 ? (
        <Empty>Chưa có ca nào.</Empty>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>Ca</th>
              <th>Hợp đồng</th>
              <th>Ngày đánh giá</th>
              <th>Mốc áp dụng</th>
              <th>Run gần nhất</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.items.map(({ case: c, latest_run_id, latest_run_status }) => (
              <tr key={c.ca_id}>
                <td>
                  <code>{c.ca_id}</code>
                </td>
                <td>{c.hop_dong_id}</td>
                <td>{c.assessment_context.ngay_danh_gia}</td>
                <td>{c.assessment_context.moc_ap_dung ?? "chưa rõ"}</td>
                <td>
                  {latest_run_id ? (
                    <Link to={`/cases/${c.ca_id}/runs/${latest_run_id}`}>
                      <StatusBadge kind="runStatus" code={latest_run_status} />
                    </Link>
                  ) : (
                    <span className="muted">chưa chạy</span>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="button"
                    disabled={startRun.isPending}
                    onClick={() => run(c.ca_id)}
                  >
                    Chạy đánh giá
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {pages > 1 && (
        <nav className="pager" aria-label="Phân trang">
          <button type="button" className="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Trước
          </button>
          <span>
            Trang {page}/{pages}
          </span>
          <button
            type="button"
            className="button"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >
            Sau
          </button>
        </nav>
      )}
    </Section>
  );
}
