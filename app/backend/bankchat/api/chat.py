"""POST /api/chat. Never moves money: action intents only create a pending action."""

from fastapi import APIRouter

from bankchat.api.deps import ChatContextDep, DbDep, UserDep
from bankchat.schemas import ChatRequest, ChatResponse
from bankchat.services.chat import handle_chat

router = APIRouter(tags=["chat"])


# Sync on purpose: FastAPI runs it in a worker thread, so the CPU-bound model call
# doesn't block the event loop.
@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: UserDep, session: DbDep, ctx: ChatContextDep) -> ChatResponse:
    return handle_chat(session, ctx, user, body.message)
