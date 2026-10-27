from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scim2_server.memory import AsyncInMemoryStorage

from examples.minimal_server import create_provider
from examples.transactions import transaction
from scim2_fastapi import ScimServer

USER = {
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
    "userName": "bjensen",
}


class RecordingSession:
    def __init__(self, fail_commit: bool = False) -> None:
        self.calls: list[str] = []
        self.fail_commit = fail_commit

    async def commit(self) -> None:
        self.calls.append("commit")
        if self.fail_commit:
            raise RuntimeError("commit failed")

    async def rollback(self) -> None:
        self.calls.append("rollback")


class SessionStorage(AsyncInMemoryStorage):
    def __init__(self, session: RecordingSession) -> None:
        super().__init__()
        self.session = session


class BrokenStorage(SessionStorage):
    async def search(self, resource_types, search_request, *, position=None):
        raise RuntimeError("database is down")


def create_client(
    storage_class: type[SessionStorage] = SessionStorage, fail_commit: bool = False
) -> tuple[TestClient, list[RecordingSession]]:
    """Return a client, and the list of the sessions its requests open."""
    sessions: list[RecordingSession] = []

    async def get_session() -> AsyncIterator[RecordingSession]:
        session = RecordingSession(fail_commit)
        sessions.append(session)
        yield session

    def get_storage(
        session: Annotated[RecordingSession, Depends(get_session)],
    ) -> SessionStorage:
        return storage_class(session)

    app = FastAPI()
    scim_server = ScimServer(get_storage, create_provider())
    app.include_router(
        scim_server.create_router(), dependencies=[transaction(get_session)]
    )
    return TestClient(app, raise_server_exceptions=False), sessions


def test_successful_request_is_committed():
    """A successful request commits the session."""
    client, sessions = create_client()
    response = client.post("/scim/v2/Users", json=USER)

    assert response.status_code == 201
    assert [session.calls for session in sessions] == [["commit"]]


def test_scim_error_is_committed():
    """A request that gets a SCIM error commits the session too."""
    client, sessions = create_client()
    response = client.get("/scim/v2/Users/unknown")

    assert response.status_code == 404
    assert [session.calls for session in sessions] == [["commit"]]


def test_unexpected_exception_is_rolled_back():
    """An unexpected exception rolls back the session, and gets a 500."""
    client, sessions = create_client(BrokenStorage)
    response = client.get("/scim/v2/Users")

    assert response.status_code == 500
    assert [session.calls for session in sessions] == [["rollback"]]


def test_failed_commit_answers_a_500():
    """A failed commit gives a 500 instead of a success."""
    client, _ = create_client(fail_commit=True)
    response = client.get("/scim/v2/Users")

    assert response.status_code == 500
