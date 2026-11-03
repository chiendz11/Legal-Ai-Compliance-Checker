"""Caller identity for API routes. Routes never trust actor/tenant fields from the client.

AUTH_MODE=on: a signed session (HttpOnly SameSite=Strict cookie, or `Authorization: Bearer`)
identifies a local user; tenant and roles are re-read from the DB on every request.
AUTH_MODE=off: every request acts as the configured local dev identity.
"""

from typing import Annotated

from fastapi import Depends, Request

from legal_checker.api.dependencies import Services, get_services
from legal_checker.api.errors import ApiProblem
from legal_checker.core.config import Settings
from legal_checker.core.security import Actor

ServicesDependency = Annotated[Services, Depends(get_services)]
SESSION_COOKIE = "lc_session"
ALL_ROLES = frozenset({"viewer", "uploader", "reviewer", "publisher"})


def session_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return request.cookies.get(SESSION_COOKIE)


def current_actor(request: Request, services: ServicesDependency) -> Actor:
    if services.sessions is None:
        settings = services.settings or Settings.from_env()
        return Actor(settings.dev_actor_id, settings.dev_tenant_id, ALL_ROLES)
    token = session_token(request)
    user_id = services.sessions.verify(token) if token else None
    user = services.users.get(user_id) if user_id else None
    if user is None or user.disabled:
        raise ApiProblem("UNAUTHENTICATED", "Sign in to continue")
    return user.actor()


ActorDependency = Annotated[Actor, Depends(current_actor)]


def require_role(actor: Actor, role: str, action: str, *alternatives: str) -> None:
    if not any(actor.has(r) for r in (role, *alternatives)):
        allowed = " or ".join((role, *alternatives))
        raise ApiProblem("FORBIDDEN", f"{action} requires the {allowed} role")
