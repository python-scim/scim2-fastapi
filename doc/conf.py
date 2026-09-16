import datetime
from importlib import metadata

# -- General configuration ------------------------------------------------

extensions = [
    "sphinx.ext.intersphinx",
    "sphinx_issues",
    "myst_parser",
]

templates_path = ["_templates"]
master_doc = "index"
project = "scim2-fastapi"
year = datetime.datetime.now().strftime("%Y")
copyright = f"{year}, Yaal Coop"
author = "Yaal Coop"
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

version = metadata.version("scim2-fastapi")
language = "en"
pygments_style = "sphinx"
toctree_collapse = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "scim2_models": ("https://scim2-models.readthedocs.io/en/latest/", None),
    "scim2_client": ("https://scim2-client.readthedocs.io/en/latest/", None),
    "scim2_tester": ("https://scim2-tester.readthedocs.io/en/latest/", None),
    "scim2_cli": ("https://scim2-cli.readthedocs.io/en/latest/", None),
}

# -- Sibling projects ------------------------------------------------------

# Kept identical in every python-scim documentation, so that any divergence
# shows up in a diff.
NAV_LINKS = [
    {
        "title": "Libraries",
        "children": [
            {
                "title": "scim2-models",
                "url": "https://scim2-models.readthedocs.io",
                "summary": "SCIM resources and messages as Pydantic models",
            },
            {
                "title": "scim2-client",
                "url": "https://scim2-client.readthedocs.io",
                "summary": "Pythonically build SCIM requests and parse SCIM responses",
            },
        ],
    },
    {
        "title": "Tools",
        "children": [
            {
                "title": "scim2-tester",
                "url": "https://scim2-tester.readthedocs.io",
                "summary": "Check a SCIM server for RFC compliance",
            },
            {
                "title": "scim2-cli",
                "url": "https://scim2-cli.readthedocs.io",
                "summary": "Query a SCIM server from the command line",
            },
            {
                "title": "scim2-server",
                "url": "https://github.com/python-scim/scim2-server",
                "summary": "A lightweight SCIM2 server prototype",
            },
            {
                "title": "pytest-scim2-server",
                "url": "https://github.com/pytest-dev/pytest-scim2-server",
                "summary": "A SCIM2 server fixture for pytest",
            },
        ],
    },
    {
        "title": "Integrations",
        "children": [
            {
                "title": "scim2-flask",
                "url": "https://scim2-flask.readthedocs.io",
                "summary": "Painless SCIM integration for Flask",
            },
            {
                "title": "scim2-django",
                "url": "https://scim2-django.readthedocs.io",
                "summary": "Painless SCIM integration for Django",
            },
            {
                "title": "scim2-fastapi",
                "url": "https://scim2-fastapi.readthedocs.io",
                "summary": "Painless SCIM integration for FastAPI",
            },
        ],
    },
]

# -- Options for HTML output ----------------------------------------------

html_theme = "shibuya"
html_baseurl = "https://scim2-fastapi.readthedocs.io"
html_logo = "_static/python-scim.svg"
html_theme_options = {
    "globaltoc_expand_depth": 3,
    "accent_color": "teal",
    "github_url": "https://github.com/python-scim/scim2-fastapi",
    "mastodon_url": "https://toot.aquilenet.fr/@yaal",
    "nav_links": NAV_LINKS,
}
html_context = {
    "source_type": "github",
    "source_user": "python-scim",
    "source_repo": "scim2-fastapi",
    "source_version": "main",
    "source_docs_path": "/doc/",
}

# -- Options for sphinx-issues -------------------------------------

issues_github_path = "python-scim/scim2-fastapi"
