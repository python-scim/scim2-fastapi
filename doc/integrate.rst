Integrate with the application
==============================

Use this guide to fit the SCIM endpoints into a FastAPI application: authenticate the clients,
build the storage of each request, commit the changes of each request, choose the URLs, page with
cursors and limit the size of the requests. It assumes a
:class:`~scim2_server.storage.AsyncScimStorage` and a :class:`~scim2_models.ScimProvider`, such
as the ones of the :doc:`overview`.

The guide covers the FastAPI side only. The scim2-server guides cover the rest:

- :doc:`scim2_server:how-to/write-a-storage`, to keep the resources in your own backend;
- :doc:`scim2_server:how-to/authenticate-the-clients`, to limit what each client may do;
- :doc:`scim2_server:how-to/serve-the-me-endpoint`, to serve ``/Me``;
- :doc:`scim2_server:how-to/publish-the-resources-at-other-urls`, to serve the resources at other URLs;
- :doc:`scim2_server:how-to/page-with-cursors`, to page with cursors.

The examples come from the
`examples <https://github.com/python-scim/scim2-fastapi/tree/main/examples>`_ directory, and
reuse the ``create_provider`` function of the overview.

Authenticate the clients
------------------------

Pass a `dependency <https://fastapi.tiangolo.com/tutorial/dependencies/>`_ as the ``subject``
parameter of :class:`~scim2_fastapi.ScimServer`. FastAPI runs it before every SCIM request, and
only before them. It returns the authenticated client, or raises
:class:`~scim2_models.UnauthorizedException` to refuse the request.

Leave ``/ServiceProviderConfig`` open: per :rfc:`RFC 7643 §5 <7643#section-5>`, clients read the
authentication schemes there before they authenticate. The dependency recognizes it by the name
of its route: ``service_provider_config``, prefixed with the ``name`` of the extension.

The extension serves each request with a :class:`~scim2_server.service.ScimService`, which applies
the rules of the protocol. What the dependency returns is the *subject* of the request, that the
extension passes to this service:

.. literalinclude:: ../examples/authentication.py
   :language: python
   :pyobject: authenticate

``HTTPBearer`` reads the token of the :mdn:`Authorization` header, and announces the scheme in the
OpenAPI schema. Replace ``TOKENS`` with the validation of the tokens of your application,
preferably with a library dedicated to authentication, such as
`Authlib <https://docs.authlib.org>`_.

Announce the scheme in the ``authentication_schemes`` of the
:class:`~scim2_models.ServiceProviderConfig`:

.. code-block:: python

   config = ServiceProviderConfig(
       ...,
       authentication_schemes=[
           AuthenticationScheme(
               type=AuthenticationScheme.Type.oauthbearertoken,
               name="OAuth Bearer Token",
               description="Authentication with an OAuth 2.0 bearer token",
           )
       ],
   )

A refused client receives a SCIM error, with a :mdn:`WWW-Authenticate` header built from the
announced schemes:

.. doctest::

   >>> from fastapi.testclient import TestClient
   >>> from examples.authentication import create_app
   >>> client = TestClient(create_app())
   >>> response = client.get("/scim/v2/Users")
   >>> response.status_code, response.headers["WWW-Authenticate"]
   (401, 'Bearer realm="SCIM"')
   >>> client.get("/scim/v2/Users", headers={"Authorization": "Bearer secret"}).status_code
   200
   >>> client.get("/scim/v2/ServiceProviderConfig").status_code
   200

The extension answers with a SCIM error the :class:`~scim2_models.SCIMException` and the
``HTTPException`` of FastAPI raised by any dependency of its routes: the ``subject`` dependency,
and the dependencies of the routers that include its router. An ``HTTPException`` keeps its
headers, such as :mdn:`WWW-Authenticate`.

The service reads the subject in two methods: :meth:`~scim2_server.service.ScimService.authorize`
accepts or refuses each operation, and :meth:`~scim2_server.service.ScimService.me_target` finds
the resource ``/Me`` stands for. To override them, subclass
:class:`~scim2_server.service.ScimService`, and pass an instance to the ``service`` parameter of
:class:`~scim2_fastapi.ScimServer`.

Build the storage of each request
---------------------------------

A storage built once serves every request. A storage that needs something of the request, such as
the database session of the request or the organization of the client, is built for each request
instead. Pass a dependency returning the storage in place of the storage itself:

.. code-block:: python

   def get_storage(session: Annotated[AsyncSession, Depends(get_session)]) -> MyStorage:
       return MyStorage(session)


   scim_server = ScimServer(get_storage, provider, app=app)

The dependency can depend on other dependencies of the application, such as its database session
or its authentication. FastAPI calls a dependency once per request, and gives its result to every
dependency that requests it: the storage and the rest of the application share the session of the
request.

Commit the changes of each request
----------------------------------

The extension never commits. It encloses each SCIM operation in the
:meth:`~scim2_server.storage.AsyncScimStorage.operation` context manager of the storage: the
request itself, or each operation of a bulk request. A SQL storage opens a savepoint there, so that
a failed operation of a bulk request does not undo the others.

Commit once per request, in a dependency with ``yield`` that FastAPI runs around every SCIM
request. The code after ``yield`` runs once the response is ready: the SCIM errors are responses,
and commit as well, so that the successful operations of a bulk request are kept. An unexpected
exception reaches the dependency, which rolls back:

.. literalinclude:: ../examples/transactions.py
   :language: python
   :pyobject: transaction

Pass the dependency giving the database session of the request, and include the router of the
extension with the transaction:

.. code-block:: python

   async def get_session() -> AsyncIterator[AsyncSession]:
       async with async_sessionmaker(engine)() as session:
           yield session


   def get_storage(session: Annotated[AsyncSession, Depends(get_session)]) -> MyStorage:
       return MyStorage(session)


   scim_server = ScimServer(get_storage, provider)
   app.include_router(
       scim_server.create_router(), dependencies=[transaction(get_session)]
   )

The ``scope="function"`` of the dependency makes FastAPI commit before it sends the response. A
commit that fails raises an exception in the dependency, and the client receives a 500 rather than
a success.

Choose the URLs
---------------

The extension serves the endpoints under ``/scim/v2`` by default. To serve them under another
path, pass it as ``url_prefix``:

.. doctest::

   >>> from fastapi import FastAPI
   >>> from scim2_server.memory import AsyncInMemoryStorage
   >>> from examples.minimal_server import create_provider
   >>> from scim2_fastapi import ScimServer
   >>> app = FastAPI()
   >>> scim_server = ScimServer(AsyncInMemoryStorage(), create_provider(), app=app, url_prefix="/api/scim")
   >>> TestClient(app).get("/api/scim/Users").status_code
   200

Without ``app``, :meth:`~scim2_fastapi.ScimServer.create_router` returns the router, to include in
the application or in another router, with the parameters of ``include_router``:

.. doctest::

   >>> from fastapi import APIRouter
   >>> scim_server = ScimServer(AsyncInMemoryStorage(), create_provider())
   >>> api_router = APIRouter(prefix="/api")
   >>> api_router.include_router(scim_server.create_router(), tags=["SCIM"])
   >>> app = FastAPI()
   >>> app.include_router(api_router)
   >>> TestClient(app).get("/api/scim/v2/Users").status_code
   200

To serve several SCIM servers from one application, such as one per tenant, give each instance
its own prefix and its own ``name``:

.. doctest::

   >>> app = FastAPI()
   >>> tenant_a = ScimServer(AsyncInMemoryStorage(), create_provider(), app=app, url_prefix="/a/scim/v2", name="tenant_a")
   >>> tenant_b = ScimServer(AsyncInMemoryStorage(), create_provider(), app=app, url_prefix="/b/scim/v2", name="tenant_b")

The router has one route per SCIM route. scim2-server lists these routes in
:data:`~scim2_server.routing.ROUTES`, and each FastAPI route takes the name of its route, prefixed
with the ``name`` of the extension, such as ``tenant_a.query`` for
``GET /{endpoint}/{resource_id}``. Build their URLs with ``url_path_for``. The path of a resource
type, such as ``Users``, is the ``resource_endpoint`` parameter:

.. doctest::

   >>> app.url_path_for("tenant_a.query", resource_endpoint="Users", resource_id="2819c223")
   '/a/scim/v2/Users/2819c223'

The extension builds the URL of each resource from the host the request reached, the
``root_path`` of the application and the ``url_prefix``. Behind a reverse proxy, run Uvicorn with
``--proxy-headers`` and ``--forwarded-allow-ips``, so that these URLs use the host and scheme the
proxy received, as the `FastAPI documentation <https://fastapi.tiangolo.com/advanced/behind-a-proxy/>`_
describes.

Page with cursors
-----------------

The server encrypts the cursors with a secret. Pass it as the ``secret`` parameter of
:class:`~scim2_fastapi.ScimServer`. Every process of the application needs the same one. When the
:class:`~scim2_models.ServiceProviderConfig` announces cursor pagination and no ``secret`` is
given, :class:`~scim2_fastapi.ScimServer` raises a :exc:`ValueError`.

A :class:`~scim2_server.service.ScimService` passed as ``service`` keeps its own secret.

Limit the size of the requests
------------------------------

The :class:`~scim2_models.ServiceProviderConfig` announces ``maxPayloadSize``, the largest body
of a bulk request. The extension reads at most one byte more of a bulk request body, and the
server answers ``413`` beyond it. The extension reads the bodies of the other requests it serves
in full.

FastAPI does not limit the size of the request bodies. To protect the memory of the server, limit
it in the reverse proxy, such as with the ``client_max_body_size`` directive of nginx. Keep this
limit above ``maxPayloadSize``: a bulk request within ``maxPayloadSize`` but beyond the limit of
the proxy gets the error of the proxy, rather than a SCIM error.
