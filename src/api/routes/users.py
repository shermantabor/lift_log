from fastapi import APIRouter, HTTPException
from src.api.schemas import UserCreate, UserResponse
from src.services.api_services import create_user
from src.services.errors import BadRequestError, ConflictError, NotFoundError

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserResponse, status_code=201)
def post_user(user: UserCreate):
    try:
        return create_user(user.username)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))