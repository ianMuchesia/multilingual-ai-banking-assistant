"""GET /api/me, GET /api/accounts"""

from fastapi import APIRouter

from bankchat.api.deps import DbDep, UserDep
from bankchat.schemas import AccountOut, MeResponse
from bankchat.services.accounts import list_accounts

router = APIRouter(tags=["accounts"])


@router.get("/me", response_model=MeResponse)
def me(user: UserDep, session: DbDep) -> MeResponse:
    accounts = [AccountOut.model_validate(a) for a in list_accounts(session, user.id)]
    return MeResponse(id=user.id, username=user.username, full_name=user.full_name, accounts=accounts)


@router.get("/accounts", response_model=list[AccountOut])
def accounts(user: UserDep, session: DbDep) -> list[AccountOut]:
    return [AccountOut.model_validate(a) for a in list_accounts(session, user.id)]
