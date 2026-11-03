"""Sign-in, sign-out and the current user. Failed sign-ins are throttled per user and client."""

import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Request, Response
from pydantic import Field

from legal_checker.api.auth import SESSION_COOKIE, ActorDependency, ServicesDependency
from legal_checker.api.errors import ApiProblem
from legal_checker.shared.contracts.common import Model

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

MAX_FAILURES, WINDOW_SECONDS = 10, 300
_failures: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


class LoginRequest(Model):
    user_id: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class SessionInfo(Model):
    actor_id: str
    tenant_id: str
    display_name: str
    roles: list[str]
    auth_mode: str


def _throttled(key: str) -> bool:
    now = time.monotonic()
    with _lock:
        attempts = _failures[key]
        while attempts and now - attempts[0] > WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= MAX_FAILURES


def _record_failure(key: str) -> None:
    with _lock:
        _failures[key].append(time.monotonic())


@router.post("/login", response_model=SessionInfo)
def login(body: LoginRequest, request: Request, response: Response, services: ServicesDependency):
    if services.sessions is None:
        raise ApiProblem("CONFLICT", "Authentication is disabled on this server (AUTH_MODE=off)")
    keys = (f"user:{body.user_id}", f"client:{request.client.host if request.client else '-'}")
    if any(_throttled(key) for key in keys):
        raise ApiProblem("FORBIDDEN", "Too many failed sign-in attempts; try again later")
    user = services.users.authenticate(body.user_id, body.password)
    if user is None:
        for key in keys:
            _record_failure(key)
        raise ApiProblem("UNAUTHENTICATED", "Wrong user ID or password")
    response.set_cookie(
        SESSION_COOKIE,
        services.sessions.issue(user.user_id),
        max_age=services.sessions.ttl_seconds,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/",
    )
    return SessionInfo(
        actor_id=user.user_id,
        tenant_id=user.tenant_id,
        display_name=user.display_name,
        roles=list(user.roles),
        auth_mode="on",
    )


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="strict", httponly=True)


@router.get("/me", response_model=SessionInfo)
def me(actor: ActorDependency, services: ServicesDependency):
    if services.sessions is None:
        return SessionInfo(
            actor_id=actor.actor_id,
            tenant_id=actor.tenant_id,
            display_name="Local development",
            roles=sorted(actor.roles),
            auth_mode="off",
        )
    user = services.users.get(actor.actor_id)
    return SessionInfo(
        actor_id=user.user_id,
        tenant_id=user.tenant_id,
        display_name=user.display_name,
        roles=list(user.roles),
        auth_mode="on",
    )
