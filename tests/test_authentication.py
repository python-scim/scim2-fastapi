from fastapi.testclient import TestClient

from examples.authentication import create_app


def test_missing_token_is_refused_with_the_announced_scheme():
    """A request without a token gets a 401 with the Bearer challenge."""
    response = TestClient(create_app()).get("/scim/v2/Users")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Bearer realm="SCIM"'


def test_valid_token_is_accepted():
    """A request with a known token is served."""
    response = TestClient(create_app()).get(
        "/scim/v2/Users", headers={"Authorization": "Bearer secret"}
    )

    assert response.status_code == 200


def test_service_provider_config_is_open():
    """/ServiceProviderConfig is served without a token."""
    response = TestClient(create_app()).get("/scim/v2/ServiceProviderConfig")

    assert response.status_code == 200
