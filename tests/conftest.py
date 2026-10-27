import pytest
from fastapi import FastAPI
from scim2_models import Bulk
from scim2_models import ChangePassword
from scim2_models import EnterpriseUser
from scim2_models import ETag
from scim2_models import Filter
from scim2_models import Group
from scim2_models import Patch
from scim2_models import ResourceType
from scim2_models import ScimProvider
from scim2_models import ServiceProviderConfig
from scim2_models import Sort
from scim2_models import User
from scim2_server.memory import AsyncInMemoryStorage

from scim2_fastapi import ScimServer


def create_full_provider() -> ScimProvider:
    """Return a provider announcing every feature the in-memory storage implements."""
    return ScimProvider(
        models=[User, EnterpriseUser, Group],
        resource_types=[
            ResourceType.from_resource(User[EnterpriseUser]),
            ResourceType.from_resource(Group),
        ],
        config=ServiceProviderConfig(
            patch=Patch(supported=True),
            bulk=Bulk(supported=True, max_operations=100, max_payload_size=1_048_576),
            filter=Filter(supported=True, max_results=50),
            change_password=ChangePassword(supported=False),
            sort=Sort(supported=True),
            etag=ETag(supported=True),
            authentication_schemes=[],
        ),
    )


@pytest.fixture
def scim_server() -> ScimServer:
    return ScimServer(AsyncInMemoryStorage(), create_full_provider())


@pytest.fixture
def app(scim_server: ScimServer) -> FastAPI:
    app = FastAPI()
    app.include_router(scim_server.create_router())
    return app
