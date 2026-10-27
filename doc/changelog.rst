Changelog
=========

[0.1.0] - 2026-10-27
--------------------

Added
^^^^^
- :class:`~scim2_fastapi.ScimServer`, a FastAPI extension serving the endpoints of
  :rfc:`RFC 7644 <7644>` over a :class:`~scim2_server.storage.AsyncScimStorage`, or over the
  storage a dependency builds for each request. The SCIM protocol is handled by
  :doc:`scim2-server <scim2_server:index>`.
