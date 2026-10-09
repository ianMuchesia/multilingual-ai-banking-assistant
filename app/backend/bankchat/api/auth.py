"""POST /api/auth/login"""

from fastapi import APIRouter, HTTPException, status

from bankchat.api.deps import DbDep, SettingsDep
from bankchat.schemas import LoginRequest, LoginResponse, UserOut
from bankchat.services.auth import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, session: DbDep, settings: SettingsDep) -> LoginResponse:
    user = authenticate(session, body.username, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
    return LoginResponse(access_token=create_access_token(user.id, settings), user=UserOut.model_validate(user))
