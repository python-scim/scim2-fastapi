import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scim2_client.engines.httpx2 import SyncSCIMClient

from examples.minimal_server import create_app
from examples.minimal_server import create_provider


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def scim_client(app: FastAPI) -> SyncSCIMClient:
    return SyncSCIMClient(
        TestClient(app, base_url="http://testserver/scim/v2"),
        provider=create_provider(),
    )
