import json
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Coroutine
from http import HTTPStatus
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi.routing import APIRoute
from scim2_models import Error
from scim2_models import SCIMException
from scim2_models import ScimProvider
from scim2_server.handler import AsyncScimHandler
from scim2_server.requests import ScimRequest
from scim2_server.responses import ScimResponse
from scim2_server.routing import ROUTES
from scim2_server.service import ScimService
from scim2_server.storage import AsyncScimStorage
from starlette.datastructures import URL
from starlette.exceptions import HTTPException

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


class ScimServer:
    """FastAPI extension exposing a SCIM 2.0 server backed by an :class:`~scim2_server.storage.AsyncScimStorage`.

    The :class:`~scim2_models.ScimProvider` describes the service: the
    resource types it serves, the configuration it announces, and the policy
    the extension applies when it reads and writes payloads.

    Usage::

        storage = MyStorage()
        scim_server = ScimServer(storage, ScimProvider(models=[User]), app=app)

    Or, to include the endpoints in another router::

        scim_server = ScimServer(storage, ScimProvider(models=[User]))
        api_router.include_router(scim_server.create_router())

    :param storage: The storage the extension reads and writes resources in.
    :param provider: The service description. It must declare at least one
        resource type.
    :param app: The application to register on right away, if any.
    :param service: The service serving the requests. By default, the
        extension builds one upon ``provider``, with ``secret``. Pass a
        subclass of :class:`~scim2_server.service.ScimService` to change one of
        its steps, such as the URL of the resources.
    :param secret: The secret of the cursors, which every process of the
        application shares. It is required when the configuration of the
        service announces cursor pagination, and ignored with ``service``.
    :param subject: A FastAPI dependency returning the authenticated subject
        of a request, for :meth:`~scim2_server.service.ScimService.authorize`
        and ``/Me``. It can refuse a request by raising a
        :class:`~scim2_models.SCIMException`.
    :param url_prefix: The URL prefix the SCIM endpoints are served under.
    :param name: The prefix of the names of the routes. Give each instance its
        own name to serve several SCIM servers from one application.
    :raises ValueError: When the configuration of the service announces
        cursor pagination, and no ``secret`` is given.
    """

    def __init__(
        self,
        storage: AsyncScimStorage,
        provider: ScimProvider,
        app: FastAPI | None = None,
        *,
        service: ScimService | None = None,
        secret: str | bytes | None = None,
        subject: Callable[..., Any] | None = None,
        url_prefix: str = "/scim/v2",
        name: str = "scim",
    ) -> None:
        if not provider.resource_types:
            raise ValueError("ScimServer requires at least one resource type")

        self.storage = storage
        self.provider = provider
        self.service = service or self._create_service(secret)
        self.handler = AsyncScimHandler(self.service, storage)
        self.subject = subject
        self.url_prefix = url_prefix.rstrip("/")
        self.name = name

        if app is not None:
            app.include_router(self.create_router())

    def _create_service(self, secret: str | bytes | None) -> ScimService:
        try:
            return ScimService(self.provider, secret=secret)
        except ValueError as exception:
            raise ValueError(
                "Cursor pagination needs the secret parameter of ScimServer."
            ) from exception

    def create_router(self) -> APIRouter:
        """Return the :class:`~fastapi.APIRouter` serving the SCIM endpoints, under ``url_prefix``.

        It has one route per route of :data:`~scim2_server.routing.ROUTES`,
        named after the route and prefixed with ``name``, such as
        ``scim.query``, whose path parameters are ``resource_endpoint`` and
        ``resource_id``. A ``fallback`` route answers the other requests with
        a SCIM error.

        The routes answer the :class:`~scim2_models.SCIMException` and the
        :class:`~starlette.exceptions.HTTPException` raised by their
        dependencies with a SCIM error, including the dependencies of the
        routers that include this one.
        """
        router = APIRouter(prefix=self.url_prefix, route_class=self._route_class())
        for route in ROUTES:
            path = route.pattern.replace("{endpoint}", "{resource_endpoint}")
            router.add_api_route(
                path,
                self._make_view(getattr(self.handler, route.operation.value)),
                methods=[route.method],
                name=f"{self.name}.{route.name}",
            )
        router.add_api_route(
            "/{path:path}",
            self._make_view(self.handler.handle),
            methods=METHODS,
            name=f"{self.name}.fallback",
            include_in_schema=False,
        )
        return router

    def _route_class(self) -> type[APIRoute]:
        scim_server = self

        class ScimRoute(APIRoute):
            def get_route_handler(
                self,
            ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
                route_handler = super().get_route_handler()

                async def handle(request: Request) -> Response:
                    try:
                        return await route_handler(request)
                    except SCIMException as exception:
                        return scim_server._handle_scim_exception(exception)
                    except HTTPException as exception:
                        return scim_server._handle_http_exception(exception)

                return handle

        return ScimRoute

    def _make_view(
        self, method: Callable[[ScimRequest], Awaitable[ScimResponse]]
    ) -> Callable[..., Awaitable[Response]]:
        async def view(
            request: Request,
            subject: Annotated[Any, Depends(self.subject or (lambda: None))],
        ) -> Response:
            scim_request = await self.read_request(request, subject)
            return self._to_response(await method(scim_request))

        return view

    async def read_request(self, request: Request, subject: Any = None) -> ScimRequest:
        """Return the :class:`~scim2_server.requests.ScimRequest` of a FastAPI request."""
        base_url = str(request.url_for(f"{self.name}.search_root")).rstrip("/")
        scim_request = ScimRequest(
            method=request.method,
            base_url=base_url,
            path=request.url.path.removeprefix(URL(base_url).path),
            query=dict(request.query_params),
            headers=list(request.headers.items()),
            subject=subject,
        )
        scim_request.body = await self.read_body(request, scim_request)
        return scim_request

    async def read_body(self, request: Request, scim_request: ScimRequest) -> bytes:
        """Read the body of a request, up to one byte more than the service accepts.

        The service answers a larger body with a 413.
        """
        limit = self.service.max_body_size(scim_request)
        if limit is None:
            return await request.body()
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > limit:
                break
        return body[: limit + 1]

    @staticmethod
    def _to_response(scim_response: ScimResponse) -> Response:
        body = (
            json.dumps(scim_response.body) if scim_response.body is not None else None
        )
        return Response(
            body, status_code=scim_response.status, headers=scim_response.headers
        )

    def _handle_scim_exception(self, exception: SCIMException) -> Response:
        return self._to_response(self.service.error_response(exception))

    def _handle_http_exception(self, exception: HTTPException) -> Response:
        """Turn a Starlette exception, such as one raised by a dependency of the application, into a SCIM error."""
        error = Error(status=exception.status_code, detail=str(exception.detail))
        response = self._to_response(
            ScimResponse(HTTPStatus(exception.status_code), error.model_dump())
        )
        for key, value in (exception.headers or {}).items():
            if key.lower() != "content-type":
                response.headers[key] = value
        return response
