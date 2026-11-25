import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { useCases, useHealth, useLogout } from "../shared/api/queries";
import { signedIn, useCan, useCurrentSession } from "../shared/auth";
import { Icon } from "../shared/components/icons";
import { mockEnabled } from "../shared/env";
import { ModeSwitch } from "../shared/viewMode";

const COLLAPSE_KEY = "lc.sidebar.collapsed";

/**
 * App shell: one vertical sidebar (upload, contracts, help, account) and the page beside it.
 * Replaces the old browser-like top tabs, which stacked a second tab row on top of the
 * report's own tabs.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setMenuOpen(false), [location.pathname]);
  const toggle = () => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? "0" : "1");
    setCollapsed(!collapsed);
  };
  // Reading a report beside its PDF needs the room: fold the sidebar to icons meanwhile,
  // without changing the saved preference.
  const splitView = new URLSearchParams(location.search).get("view") === "split";
  const folded = collapsed || splitView;
  const classes = ["app", folded && "collapsed", menuOpen && "menu-open"].filter(Boolean);
  return (
    <div className={classes.join(" ")}>
      <Sidebar
        collapsed={folded}
        onToggle={toggle}
        onMenu={() => setMenuOpen(!menuOpen)}
      />
      <main className="main">
        <div className="view">{children}</div>
      </main>
    </div>
  );
}

function Sidebar({
  collapsed,
  onToggle,
  onMenu,
}: {
  collapsed: boolean;
  onToggle: () => void;
  onMenu: () => void;
}) {
  const can = useCan();
  const cases = useCases({ page_size: 1 }); // only the total, for the count
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "sb-link active" : "sb-link");
  return (
    <aside className="sidebar" aria-label="Điều hướng chính">
      <div className="sb-head">
        <Link to="/" className="logo" aria-label="Legal Checker – về danh sách hợp đồng">
          <span className="logo-mark">
            <i />
          </span>
          <span>Legal Checker</span>
        </Link>
        <button
          type="button"
          className="circle-btn sb-collapse"
          onClick={onToggle}
          aria-label={collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên"}
          title={collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên"}
        >
          <Icon name="panel" />
        </button>
        <button type="button" className="circle-btn sb-menu" onClick={onMenu} aria-label="Tài khoản">
          <Icon name="menu" />
        </button>
      </div>
      {can("uploader") && (
        <Link className="button primary sb-cta" to="/upload" title="Tải hợp đồng mới">
          <Icon name="plus" />
          <span className="sb-label">Tải hợp đồng mới</span>
        </Link>
      )}
      <nav className="sb-nav">
        <NavLink to="/" end className={linkClass} title="Hợp đồng">
          <Icon name="file" />
          <span className="sb-label">Hợp đồng</span>
          {cases.data && <span className="sb-count">{cases.data.total}</span>}
        </NavLink>
        <NavLink to="/help" className={linkClass} title="Hướng dẫn">
          <Icon name="help" />
          <span className="sb-label">Hướng dẫn</span>
        </NavLink>
      </nav>
      <div className="sb-foot">
        <div className="sb-mode">
          <span className="sb-mode-label">Chế độ hiển thị</span>
          <ModeSwitch />
        </div>
        <ServerStatus />
        <UserBox />
      </div>
    </aside>
  );
}

function ServerStatus() {
  const health = useHealth();
  const online = health.data?.status === "ok";
  const text = mockEnabled
    ? "Dữ liệu mẫu (mock)"
    : online
      ? "Máy chủ đang hoạt động"
      : health.isPending
        ? "Đang kết nối máy chủ…"
        : "Không kết nối được máy chủ";
  return (
    <div className="sb-status" title={health.data ? `schema ${health.data.schema_version}` : text}>
      <i className={`status-dot${online ? " ok" : health.isPending ? "" : " down"}`} />
      <span>{text}</span>
    </div>
  );
}

function UserBox() {
  const data = useCurrentSession();
  const logout = useLogout();
  if (!data) return null;
  const initials = data.display_name
    .split(/\s+/)
    .map((word) => word[0])
    .slice(-2)
    .join("")
    .toUpperCase();
  return (
    <div className="sb-user">
      <span className="av" aria-hidden="true">
        {initials}
      </span>
      <span
        className="who"
        title={`${data.actor_id} · ${data.tenant_id} · ${data.roles.join(", ") || "không có quyền"}`}
      >
        <b>{data.display_name}</b>
        <span>{signedIn(data) ? `${data.roles.length} vai trò` : "Chế độ dev · đủ quyền"}</span>
      </span>
      {signedIn(data) && (
        <button
          type="button"
          className="circle-btn solid"
          aria-label="Đăng xuất"
          title="Đăng xuất"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          <Icon name="logout" />
        </button>
      )}
    </div>
  );
}
