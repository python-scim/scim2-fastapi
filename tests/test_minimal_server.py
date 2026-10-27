def test_example_server_creates_and_reads_a_user(client):
    """Create a user with the enterprise extension on the example server, and read it back."""
    headers = {"Content-Type": "application/scim+json"}
    user_payload = {
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ],
        "userName": "bjensen",
        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
            "employeeNumber": "42"
        },
    }

    response = client.post("/scim/v2/Users", json=user_payload, headers=headers)
    assert response.status_code == 201
    user = response.json()
    assert user["userName"] == "bjensen"
    assert user["urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"] == {
        "employeeNumber": "42"
    }
    assert user["meta"]["resourceType"] == "User"
    assert user["meta"]["location"].endswith(f"/scim/v2/Users/{user['id']}")

    response = client.get(user["meta"]["location"])
    assert response.status_code == 200
    assert response.json() == user
