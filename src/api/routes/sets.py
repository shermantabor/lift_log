from fastapi import APIRouter, Depends, HTTPException
from src.services.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from src.api.schemas import SetCreateRequest
from src.api.auth import current_user_id
from src.services.api_services import add_sets_to_active_session, get_sets_for_session

router = APIRouter(tags=["sets"])

@router.post("/me/sets", status_code=201)
def post_sets(payload: SetCreateRequest, user_id: int = Depends(current_user_id)):
    first_ex = payload.sets[0].exercise
    for s in payload.sets:
        if s.exercise != first_ex:
            raise HTTPException(status_code=400, detail="All sets in one request must use the same exercise")

    rows = [(s.weight, s.reps, 1 if s.is_1rm else 0) for s in payload.sets]

    try:
        return add_sets_to_active_session(user_id, first_ex, rows)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/sessions/{session_id}/sets")
def read_sets(session_id: int, user_id: int = Depends(current_user_id)):
    try:
        return get_sets_for_session(user_id, session_id)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
