from fastapi import APIRouter, HTTPException
from src.services.errors import BadRequestError, ConflictError, NotFoundError
from src.api.schemas import SetCreateRequest
from src.services.api_services import add_sets_to_active_session

router = APIRouter(tags=["sets"])

@router.post("/users/{user_id}/sets", status_code=201)
def post_sets(user_id: int, payload: SetCreateRequest):
    # keep or move this rule later; for Hour 4, it's fine here if you prefer
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

