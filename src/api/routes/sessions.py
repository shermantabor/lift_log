from fastapi import APIRouter, HTTPException
from src.api.schemas import SessionCreate, SessionResponse
from src.services.api_services import create_session, end_active_session
from src.services.errors import BadRequestError, ConflictError, NotFoundError

router = APIRouter(tags=["sessions"])

@router.post("/users/{user_id}/sessions", response_model=SessionResponse, status_code=201)
def post_session(user_id: int, session: SessionCreate):
    performed_at = session.performed_at.isoformat(timespec="seconds") if session.performed_at else None
    try:
        return create_session(user_id, performed_at, session.notes)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/users/{user_id}/sessions/end")
def end_session(user_id: int):
    try:
        return end_active_session(user_id)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))