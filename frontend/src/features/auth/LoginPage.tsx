import { useState, type FormEvent } from "react";

import { ApiError, apiErrorMessage } from "../../shared/api/client";
import { useLogin } from "../../shared/api/queries";
import { Notice, Section } from "../../shared/components/ui";

/** AUTH_MODE=on: the server sets an HttpOnly session cookie; the page never stores tokens. */
export function LoginPage() {
  const login = useLogin();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate({ user_id: userId.trim(), password });
  }

  const error = login.error;
  return (
    <div className="login">
      <Section
        title="Đăng nhập"
        description="Tài khoản do quản trị tạo bằng scripts.users. Quyền xem, tải lên, review và phát hành tách riêng theo vai trò."
      >
        <form className="form" onSubmit={submit}>
          <label className="field">
            <span>Mã người dùng</span>
            <input
              autoComplete="username"
              required
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Mật khẩu</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <Notice tone="bad">
              {error instanceof ApiError && error.status === 401
                ? "Sai mã người dùng hoặc mật khẩu."
                : (apiErrorMessage(error) ?? "Không đăng nhập được. Kiểm tra backend.")}
            </Notice>
          )}
          <div className="actions">
            <button type="submit" className="button primary" disabled={login.isPending}>
              {login.isPending ? "Đang đăng nhập…" : "Đăng nhập"}
            </button>
          </div>
        </form>
      </Section>
    </div>
  );
}
