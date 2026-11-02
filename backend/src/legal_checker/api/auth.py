"""Caller identity for API routes. Routes never trust actor/tenant fields from the client."""

from typing import Annotated

from fastapi import Depends, Request

from legal_checker.api.dependencies import Services, get_services
from legal_checker.core.security import Actor

ServicesDependency = Annotated[Services, Depends(get_services)]


def current_actor(request: Request, services: ServicesDependency) -> Actor:
    settings = services.settings
    return Actor(
        actor_id=settings.dev_actor_id,
        tenant_id=settings.dev_tenant_id,
        roles=frozenset({"viewer", "uploader", "reviewer", "publisher"}),
    )


ActorDependency = Annotated[Actor, Depends(current_actor)]
