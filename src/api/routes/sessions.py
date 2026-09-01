from fastapi import APIRouter, Depends, HTTPException
from src.api.schemas import SessionCreate, SessionResponse, SessionEnd
from src.api.auth import current_user_id
from src.services.api_services import (
    create_session,
    end_active_session,
    get_active_session,
    get_sessions_for_user
)
from src.services.errors import BadRequestError, ConflictError, NotFoundError

router = APIRouter(tags=["sessions"])

@router.post("/me/sessions", response_model=SessionResponse, status_code=201)
def post_session(session: SessionCreate, user_id: int = Depends(current_user_id)):
    performed_at = session.performed_at.isoformat(timespec="seconds") if session.performed_at else None
    try:
        return create_session(user_id, session.session_name, performed_at, session.notes)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/me/sessions/end")
def end_session(body: SessionEnd = SessionEnd(), user_id: int = Depends(current_user_id)):
    try:
        return end_active_session(user_id, body.session_name)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me/sessions/active")
def read_active_session(user_id: int = Depends(current_user_id)):
    try:
        return get_active_session(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me/sessions")
def read_sessions(user_id: int = Depends(current_user_id)):
    return get_sessions_for_user(user_id)
