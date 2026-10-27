"""Validate the example server against the official SCIM conformance tester.

https://github.com/python-scim/scim2-tester
"""

import pytest
from scim2_tester import Status
from scim2_tester import check_server

SUPPORTED_TAGS = [
    "discovery",
    "resource-types",
    "schemas",
    "service-provider-config",
    "crud:create",
    "crud:read",
    "crud:read:attributes",
    "crud:update",
    "crud:delete",
    "patch:add",
    "patch:remove",
    "patch:replace",
    "misc",
]


@pytest.mark.parametrize("tag", SUPPORTED_TAGS)
@pytest.mark.parametrize("resource_type", [None, "User", "Group"])
def test_individual_filters(scim_client, tag, resource_type):
    """Test that all SCIM server tests pass or are skipped for each tag and resource type combination."""
    results = check_server(
        scim_client,
        raise_exceptions=True,
        include_tags={tag},
        resource_types=resource_type,
    )

    for result in results:
        assert result.status in (Status.SKIPPED, Status.SUCCESS)
