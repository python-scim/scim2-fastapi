"""Validate the example server against the official SCIM conformance tester.

https://github.com/python-scim/scim2-tester
"""

from scim2_tester.testing import ScimServerContract


class TestExampleServer(ScimServerContract):
    """The example server passes the checks of scim2-tester."""
