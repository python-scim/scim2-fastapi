"""Commit the changes of each SCIM request in a database session."""

from collections.abc import AsyncIterator
from collections.abc import Callable
from typing import Annotated
from typing import Any

from fastapi import Depends
from fastapi import params


def transaction(get_session: Callable[..., Any]) -> params.Depends:
    """Return a dependency committing the changes of each request in the session of ``get_session``."""

    async def commit_or_rollback(
        session: Annotated[Any, Depends(get_session)],
    ) -> AsyncIterator[None]:
        try:
            yield
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return Depends(commit_or_rollback, scope="function")
