"""POST /api/actions/{id}/confirm (the ONLY endpoint that moves money), POST /api/actions/{id}/cancel"""

from fastapi import APIRouter

from bankchat.api.deps import ChatContextDep, DbDep, SettingsDep, UserDep
from bankchat.schemas import CancelResponse, ConfirmRequest, ConfirmResponse
from bankchat.services.actions import cancel_action, confirm_action

router = APIRouter(prefix="/actions", tags=["actions"])


@router.post("/{action_id}/confirm", response_model=ConfirmResponse)
def confirm(
    action_id: str, body: ConfirmRequest, user: UserDep, session: DbDep, settings: SettingsDep, ctx: ChatContextDep
) -> ConfirmResponse:
    return confirm_action(session, settings, ctx.bank, user, action_id, body.slots)


@router.post("/{action_id}/cancel", response_model=CancelResponse)
def cancel(action_id: str, user: UserDep, session: DbDep) -> CancelResponse:
    return cancel_action(session, user, action_id)
