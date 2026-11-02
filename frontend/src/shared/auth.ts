import { ApiError, type SessionInfo } from "./api/client";
import { useSession } from "./api/queries";

export type Role = "viewer" | "uploader" | "reviewer" | "publisher";

/**
 * Role check for hiding actions the server would refuse anyway (403). The backend stays the
 * authority; with AUTH_MODE=off the dev actor holds every role.
 */
export function useCan() {
  const session = useCurrentSession();
  return (role: Role) => !!session?.roles.includes(role);
}

/** The signed-in session, or undefined once the server answered 401 (stale data is ignored). */
export function useCurrentSession(): SessionInfo | undefined {
  const { data, error } = useSession();
  return isUnauthenticated(error) ? undefined : data;
}

export function isUnauthenticated(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}

export function signedIn(session: SessionInfo | undefined) {
  return session?.auth_mode === "on";
}
