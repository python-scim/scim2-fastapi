from typing import Annotated

import pytest
from fastapi import APIRouter
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi.testclient import TestClient
from scim2_models import AuthenticationScheme
from scim2_models import Bulk
from scim2_models import ETag
from scim2_models import Filter
from scim2_models import Pagination
from scim2_models import ResourceType
from scim2_models import ScimProvider
from scim2_models import ServiceProviderConfig
from scim2_models import UnauthorizedException
from scim2_models import User
from scim2_server.memory import AsyncInMemoryStorage
from scim2_server.service import ScimService

from scim2_fastapi import ScimServer

SCIM_JSON = "application/scim+json"
SCIM_HEADERS = {"Content-Type": SCIM_JSON}
USER = {"schemas": [User.__schema__], "userName": "bjensen"}
BULK_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:BulkRequest"


def create_provider(config: ServiceProviderConfig | None = None) -> ScimProvider:
    return ScimProvider(
        models=[User],
        resource_types=[ResourceType.from_resource(User)],
        config=config,
    )


def create_client(**kwargs) -> TestClient:
    app = FastAPI()
    kwargs.setdefault("storage", AsyncInMemoryStorage())
    kwargs.setdefault("provider", create_provider())
    ScimServer(app=app, **kwargs)
    return TestClient(app)


def bulk_payload(size: int) -> dict:
    """Return a bulk request whose JSON body is at least ``size`` bytes long."""
    return {
        "schemas": [BULK_SCHEMA],
        "Operations": [
            {"method": "DELETE", "path": f"/Users/{'x' * size}"},
        ],
    }


def refuse() -> None:
    raise UnauthorizedException(detail="Missing token")


def test_requires_at_least_one_resource_type():
    with pytest.raises(ValueError, match="at least one resource type"):
        ScimServer(AsyncInMemoryStorage(), ScimProvider())


def test_endpoints_are_served_under_the_url_prefix():
    client = create_client(url_prefix="/api/scim/")

    created = client.post("/api/scim/Users", json=USER, headers=SCIM_HEADERS)
    assert created.status_code == 201
    assert created.json()["meta"]["location"] == (
        f"http://testserver/api/scim/Users/{created.json()['id']}"
    )
    assert client.get("/api/scim/Users").json()["totalResults"] == 1


def test_endpoints_can_be_served_at_the_application_root():
    client = create_client(url_prefix="")

    created = client.post("/Users", json=USER, headers=SCIM_HEADERS)
    assert created.json()["meta"]["location"] == (
        f"http://testserver/Users/{created.json()['id']}"
    )
    assert client.get("/").json()["totalResults"] == 1


def test_locations_follow_the_host_and_root_path():
    app = FastAPI()
    ScimServer(AsyncInMemoryStorage(), create_provider(), app=app)
    client = TestClient(app, base_url="https://scim.example.org", root_path="/app")

    created = client.post("/app/scim/v2/Users", json=USER, headers=SCIM_HEADERS)
    assert created.status_code == 201
    assert created.headers["Location"] == (
        f"https://scim.example.org/app/scim/v2/Users/{created.json()['id']}"
    )


def test_router_can_be_included_in_another_router():
    """The router keeps its URLs, and answers the errors of the dependencies of its parents."""
    scim_server = ScimServer(AsyncInMemoryStorage(), create_provider())
    api = APIRouter(prefix="/api")
    api.include_router(scim_server.create_router())
    app = FastAPI()
    app.include_router(api)
    app.include_router(
        scim_server.create_router(), prefix="/protected", dependencies=[Depends(refuse)]
    )
    client = TestClient(app)

    created = client.post("/api/scim/v2/Users", json=USER, headers=SCIM_HEADERS)
    assert created.json()["meta"]["location"] == (
        f"http://testserver/api/scim/v2/Users/{created.json()['id']}"
    )
    response = client.get("/protected/scim/v2/Users")
    assert response.status_code == 401
    assert response.headers["Content-Type"] == SCIM_JSON


def test_several_instances_serve_one_application():
    app = FastAPI()
    ScimServer(
        AsyncInMemoryStorage(),
        create_provider(),
        app=app,
        url_prefix="/a/scim/v2",
        name="tenant_a",
    )
    ScimServer(
        AsyncInMemoryStorage(),
        create_provider(),
        app=app,
        url_prefix="/b/scim/v2",
        name="tenant_b",
    )
    client = TestClient(app)

    created = client.post("/a/scim/v2/Users", json=USER, headers=SCIM_HEADERS)
    assert created.json()["meta"]["location"] == (
        f"http://testserver/a/scim/v2/Users/{created.json()['id']}"
    )
    assert client.get("/a/scim/v2/Users").json()["totalResults"] == 1
    assert client.get("/b/scim/v2/Users").json()["totalResults"] == 0


def test_routes_are_named_after_the_scim_routes():
    app = FastAPI()
    ScimServer(AsyncInMemoryStorage(), create_provider(), app=app)

    assert (
        app.url_path_for("scim.query", resource_endpoint="Users", resource_id="42")
        == "/scim/v2/Users/42"
    )
    assert app.url_path_for("scim.service_provider_config") == (
        "/scim/v2/ServiceProviderConfig"
    )


def test_openapi_schema_lists_the_scim_routes():
    app = FastAPI()
    ScimServer(AsyncInMemoryStorage(), create_provider(), app=app)

    paths = app.openapi()["paths"]
    assert "/scim/v2/{resource_endpoint}/{resource_id}" in paths
    assert "/scim/v2/{path}" not in paths


def test_unknown_path_answers_a_scim_404():
    response = create_client().get("/scim/v2/Users/42/unknown")

    assert response.status_code == 404
    assert response.headers["Content-Type"] == SCIM_JSON
    assert response.json()["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("PUT", "/scim/v2/Users", "GET, POST"),
        ("DELETE", "/scim/v2/", "GET"),
    ],
)
def test_unsupported_method_answers_a_scim_405(method, path, allowed):
    response = create_client().request(method, path)

    assert response.status_code == 405
    assert response.headers["Allow"] == allowed
    assert response.headers["Content-Type"] == SCIM_JSON


def test_responses_keep_the_status_headers_and_body_of_the_service():
    client = create_client(
        provider=create_provider(ServiceProviderConfig(etag=ETag(supported=True)))
    )

    created = client.post("/scim/v2/Users", json=USER, headers=SCIM_HEADERS)
    assert created.status_code == 201
    assert type(created.status_code) is int
    assert created.headers["Content-Type"] == SCIM_JSON
    assert created.headers["ETag"] == created.json()["meta"]["version"]
    location = created.headers["Location"]

    not_modified = client.get(
        location, headers={"If-None-Match": created.headers["ETag"]}
    )
    assert not_modified.status_code == 304

    deleted = client.delete(location)
    assert deleted.status_code == 204
    assert deleted.content == b""


def test_query_string_is_passed_to_the_service():
    config = ServiceProviderConfig(filter=Filter(supported=True, max_results=10))
    client = create_client(provider=create_provider(config))
    client.post("/scim/v2/Users", json=USER, headers=SCIM_HEADERS)
    client.post(
        "/scim/v2/Users", json={**USER, "userName": "jsmith"}, headers=SCIM_HEADERS
    )

    response = client.get("/scim/v2/Users", params={"filter": 'userName eq "jsmith"'})
    assert [user["userName"] for user in response.json()["Resources"]] == ["jsmith"]


def test_bulk_body_beyond_max_payload_size_is_refused():
    config = ServiceProviderConfig(
        bulk=Bulk(supported=True, max_operations=10, max_payload_size=100)
    )
    client = create_client(provider=create_provider(config))

    response = client.post(
        "/scim/v2/Bulk", json=bulk_payload(200), headers=SCIM_HEADERS
    )
    assert response.status_code == 413
    assert response.headers["Content-Type"] == SCIM_JSON


def test_unsupported_bulk_is_refused_whatever_its_max_payload_size():
    config = ServiceProviderConfig(
        bulk=Bulk(supported=False, max_operations=0, max_payload_size=0)
    )
    client = create_client(provider=create_provider(config))

    response = client.post("/scim/v2/Bulk", json=bulk_payload(10), headers=SCIM_HEADERS)
    assert response.status_code == 501


def test_max_payload_size_only_limits_bulk_requests():
    config = ServiceProviderConfig(
        bulk=Bulk(supported=True, max_operations=10, max_payload_size=10)
    )
    client = create_client(provider=create_provider(config))

    response = client.post("/scim/v2/Users", json=USER, headers=SCIM_HEADERS)
    assert response.status_code == 201


def test_scim_exception_raised_by_a_dependency_answers_a_scim_error():
    """A dependency refusing a request gets the challenges of the announced schemes.

    RFC7644 §2: "a SCIM service provider SHALL indicate supported HTTP
    authentication schemes via the "WWW-Authenticate" header."
    """
    config = ServiceProviderConfig(
        authentication_schemes=[
            AuthenticationScheme(
                type="oauthbearertoken",
                name="OAuth Bearer Token",
                description="Authentication with an OAuth bearer token",
            )
        ]
    )
    client = create_client(provider=create_provider(config), subject=refuse)

    response = client.get("/scim/v2/Users")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer")
    assert response.headers["Content-Type"] == SCIM_JSON
    assert response.json()["detail"] == "Missing token"


def test_http_exception_raised_by_a_dependency_keeps_its_headers():
    def refuse_with_http_exception() -> None:
        raise HTTPException(
            401,
            detail="Missing or invalid token",
            headers={"WWW-Authenticate": "Bearer", "Content-Type": "text/plain"},
        )

    client = create_client(subject=refuse_with_http_exception)

    response = client.get("/scim/v2/Users")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["Content-Type"] == SCIM_JSON
    assert response.json()["detail"] == "Missing or invalid token"


def test_validation_error_raised_by_a_dependency_answers_a_scim_400():
    def header_subject(x_user: Annotated[str, Header()]) -> str:
        return x_user

    client = create_client(subject=header_subject)

    response = client.get("/scim/v2/Users")
    assert response.status_code == 400
    assert response.headers["Content-Type"] == SCIM_JSON
    assert response.json()["scimType"] == "invalidValue"
    assert response.json()["detail"] == "header.x-user: Field required"
    assert (
        client.get("/scim/v2/Users", headers={"X-User": "bjensen"}).status_code == 200
    )


def test_subject_is_passed_to_the_service():
    def header_subject(request: Request) -> str | None:
        return request.headers.get("X-User")

    class MeService(ScimService):
        def me_target(self, request):
            return self.get_resource_type("User"), request.subject

    provider = create_provider()
    client = create_client(
        provider=provider, service=MeService(provider), subject=header_subject
    )
    created = client.post("/scim/v2/Users", json=USER, headers=SCIM_HEADERS)

    response = client.get("/scim/v2/Me", headers={"X-User": created.json()["id"]})
    assert response.status_code == 200
    assert response.json()["userName"] == "bjensen"
    assert response.headers["Location"] == created.headers["Location"]


def test_storage_can_be_given_by_a_dependency():
    storages = {"a": AsyncInMemoryStorage(), "b": AsyncInMemoryStorage()}

    def tenant_storage(request: Request) -> AsyncInMemoryStorage:
        return storages[request.headers["X-Tenant"]]

    client = create_client(storage=tenant_storage)

    created = client.post(
        "/scim/v2/Users", json=USER, headers={**SCIM_HEADERS, "X-Tenant": "a"}
    )
    assert created.status_code == 201
    users_of = {
        tenant: client.get("/scim/v2/Users", headers={"X-Tenant": tenant}).json()
        for tenant in storages
    }
    assert users_of["a"]["totalResults"] == 1
    assert users_of["b"]["totalResults"] == 0


def test_steps_of_the_service_can_be_overridden():
    class PublicService(ScimService):
        def resource_location(self, base_url, resource_type, resource_id):
            return f"https://scim.example.org/v2/Users/{resource_id}"

    provider = create_provider()
    client = create_client(provider=provider, service=PublicService(provider))

    created = client.post("/scim/v2/Users", json=USER, headers=SCIM_HEADERS)
    assert created.json()["meta"]["location"] == (
        f"https://scim.example.org/v2/Users/{created.json()['id']}"
    )


def create_cursor_client(
    storage: AsyncInMemoryStorage, secret: str | None
) -> TestClient:
    config = ServiceProviderConfig(pagination=Pagination(cursor=True, index=True))
    app = FastAPI()
    ScimServer(storage, create_provider(config), app=app, secret=secret)
    return TestClient(app)


def test_cursors_are_sealed_with_the_secret():
    """A cursor from one process is accepted by another one with the same secret."""
    storage = AsyncInMemoryStorage()
    first = create_cursor_client(storage, "secret")
    second = create_cursor_client(storage, "secret")
    for user_name in ("bjensen", "jsmith"):
        first.post(
            "/scim/v2/Users", json={**USER, "userName": user_name}, headers=SCIM_HEADERS
        )

    page = first.get("/scim/v2/Users?cursor&count=1")
    next_page = second.get(
        "/scim/v2/Users", params={"cursor": page.json()["nextCursor"], "count": 1}
    )

    assert next_page.status_code == 200
    user_names = {page.json()["Resources"][0]["userName"]}
    user_names.add(next_page.json()["Resources"][0]["userName"])
    assert user_names == {"bjensen", "jsmith"}


def test_cursors_need_a_secret():
    with pytest.raises(ValueError, match="secret"):
        create_cursor_client(AsyncInMemoryStorage(), None)


def test_storage_without_the_announced_cursors_is_refused():
    class CursorlessStorage(AsyncInMemoryStorage):
        supports_cursors = False

    config = ServiceProviderConfig(pagination=Pagination(cursor=True, index=True))
    with pytest.raises(TypeError, match="cursor pagination"):
        ScimServer(CursorlessStorage(), create_provider(config), secret="secret")


def test_given_service_keeps_its_own_secret():
    config = ServiceProviderConfig(pagination=Pagination(cursor=True, index=True))
    provider = create_provider(config)
    client = create_client(provider=provider, service=ScimService(provider, secret="s"))

    response = client.get("/scim/v2/Users?cursor&count=1")
    assert response.status_code == 200


def test_unexpected_exceptions_reach_fastapi():
    class BrokenStorage(AsyncInMemoryStorage):
        async def search(self, resource_types, search_request, *, position=None):
            raise RuntimeError("database is down")

    app = FastAPI()
    ScimServer(BrokenStorage(), create_provider(), app=app)

    with pytest.raises(RuntimeError, match="database is down"):
        TestClient(app).get("/scim/v2/Users")
