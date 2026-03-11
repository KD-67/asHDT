# Per-request GraphQL context. Injected into every resolver via info.context.
# Both HTTP requests (queries/mutations) and WebSocket connections (subscriptions)
# pass through here — both FastAPI Request and WebSocket expose .app.state.

from __future__ import annotations
from strawberry.fastapi import BaseContext


class AppContext(BaseContext):
    """
    Carries per-request state into every resolver.
    Works for both HTTP (queries/mutations) and WebSocket (subscriptions) —
    both expose .app.state via the same interface.
    """

    @property
    def db_path(self) -> str:
        return self.request.app.state.db_path

    @property
    def rawdata_root(self) -> str:
        return self.request.app.state.rawdata_root

    @property
    def reports_root(self) -> str:
        return self.request.app.state.reports_root

    @property
    def references_root(self) -> str:
        return self.request.app.state.references_root

    @property
    def modules(self) -> dict:
        return self.request.app.state.modules

    @property
    def modules_path(self) -> str:
        return self.request.app.state.modules_path

    @property
    def redis_pool(self):
        """ARQ redis pool for job enqueueing. None if Redis is not available."""
        return getattr(self.request.app.state, "redis_pool", None)


async def get_context() -> AppContext:
    return AppContext()
