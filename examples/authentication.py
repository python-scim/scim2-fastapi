"""Authenticate the clients of the SCIM endpoints with bearer tokens."""

from typing import Annotated

from fastapi import Depends
from fastapi import FastAPI
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from scim2_models import AuthenticationScheme
from scim2_models import ScimProvider
from scim2_models import ServiceProviderConfig
from scim2_models import UnauthorizedException
from scim2_models import User
from scim2_server.memory import AsyncInMemoryStorage

from scim2_fastapi import ScimServer

TOKENS = {"secret": "bjensen"}


def authenticate(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ],
) -> str | None:
    if request.scope["route"].name == "scim.service_provider_config":
        return None
    if credentials is None or credentials.credentials not in TOKENS:
        raise UnauthorizedException(detail="Missing or invalid token")
    return TOKENS[credentials.credentials]


def create_provider() -> ScimProvider:
    config = ServiceProviderConfig(
        authentication_schemes=[
            AuthenticationScheme(
                type=AuthenticationScheme.Type.oauthbearertoken,
                name="OAuth Bearer Token",
                description="Authentication with an OAuth 2.0 bearer token",
            )
        ]
    )
    return ScimProvider(models=[User], config=config)


def create_app() -> FastAPI:
    app = FastAPI()
    ScimServer(AsyncInMemoryStorage(), create_provider(), app=app, subject=authenticate)
    return app
