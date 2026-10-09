"""GET /api/health (no auth)"""

from fastapi import APIRouter

from bankchat.api.deps import ChatContextDep
from bankchat.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(ctx: ChatContextDep) -> HealthResponse:
    return HealthResponse(router_mode=ctx.router.mode)
