from fastapi import APIRouter, HTTPException
from src.api.schemas import UserCreate, UserResponse, LoginRequest
from src.services.api_services import create_user, login_user, get_exercises_for_user, get_sets_for_exercise
from src.services.errors import BadRequestError, ConflictError, NotFoundError

router = APIRouter(tags=["users"])

@router.post("/users", response_model=UserResponse, status_code=201)
def post_user(user: UserCreate):
    try:
        return create_user(user.username, user.password)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    
@router.post("/login", response_model=UserResponse)
def post_login(creds: LoginRequest):
    try:
        return login_user(creds.username, creds.password)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/users/{id}/exercises")
def read_exercises(id: int):
    return get_exercises_for_user(id)

@router.get("/users/{id}/sets")
def read_sets_for_exercise(id: int, exercise: str):
    return get_sets_for_exercise(id, exercise)