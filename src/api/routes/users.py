from fastapi import APIRouter, Depends, HTTPException
from src.api.schemas import UserCreate, UserResponse, AuthResponse, LoginRequest
from src.api.auth import current_user_id
from src.services.api_services import (
    create_user,
    login_user,
    get_user,
    get_exercises_for_user,
    get_sets_for_exercise,
)
from src.services.errors import BadRequestError, ConflictError, NotFoundError

router = APIRouter(tags=["users"])

# Public routes — these are how a caller obtains a token.

@router.post("/users", response_model=AuthResponse, status_code=201)
def post_user(user: UserCreate):
    try:
        return create_user(user.username, user.password)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/login", response_model=AuthResponse)
def post_login(creds: LoginRequest):
    try:
        return login_user(creds.username, creds.password)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=401, detail=str(e))

# Protected routes — the caller is whoever the token says they are.

@router.get("/me", response_model=UserResponse)
def read_me(user_id: int = Depends(current_user_id)):
    try:
        return get_user(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me/exercises")
def read_exercises(user_id: int = Depends(current_user_id)):
    return get_exercises_for_user(user_id)

@router.get("/me/sets")
def read_sets_for_exercise(exercise: str, user_id: int = Depends(current_user_id)):
    return get_sets_for_exercise(user_id, exercise)
