scim2-fastapi
=============

scim2-fastapi is a `FastAPI <https://fastapi.tiangolo.com/>`_ extension serving a SCIM 2.0
server, as :rfc:`RFC 7643 <7643>` and :rfc:`RFC 7644 <7644>` define it. It exposes the
resource, search, bulk and discovery endpoints in an :class:`~fastapi.APIRouter`. It is built
upon :doc:`scim2-server <scim2_server:index>` and :doc:`scim2-models <scim2_models:index>`.

The extension serves the SCIM protocol. The FastAPI application that includes it provides the
rest:

- a :class:`~scim2_server.storage.AsyncScimStorage`, which reads and writes the resources;
- a :class:`~scim2_models.ScimProvider`, which declares the resource types the server serves and
  the features it supports;
- authentication and authorization, since the extension leaves every endpoint open.

This documentation addresses Python developers who build a SCIM server with FastAPI. It assumes
familiarity with FastAPI applications and their dependencies. It covers what is specific to
FastAPI: the storage, the service and the protocol rules are described in the
:doc:`scim2-server documentation <scim2_server:index>`.

.. code-block:: shell

   pip install scim2-fastapi

Choose a path
-------------

:doc:`Overview <overview>` introduces the parts of a SCIM server built with FastAPI, in the order
an application meets them.

:doc:`Integrate with the application <integrate>` shows how to authenticate the clients, commit
the changes of each request, choose the URLs and limit the size of the requests.

:doc:`Reference <reference>` lists the complete public API.

.. toctree::
    :maxdepth: 2
    :hidden:

    Overview <overview>
    Integrate with the application <integrate>
    Reference <reference>
    Contributing <contributing>
    Changelog <changelog>
