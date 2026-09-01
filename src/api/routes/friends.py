from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List

from src.api.schemas import (
    FriendRequestCreate,
    FriendRequestRespond,
    FriendResponse,
    FriendRequestList,
    UserSearchResult,
)
from src.api.auth import current_user_id
from src.services.api_services import (
    search_users,
    send_friend_request,
    respond_to_friend_request,
    cancel_friend_request,
    remove_friend,
    get_friends,
    get_friend_requests,
    get_friend_exercises,
    get_friend_sets_for_exercise,
)
from src.services.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError

router = APIRouter(tags=["friends"])

def _handle(fn, *args, **kwargs):
    '''map service errors onto status codes the same way across every route'''
    try:
        return fn(*args, **kwargs)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("/me/search", response_model=List[UserSearchResult])
def search_for_users(q: str = Query(..., min_length=1), user_id: int = Depends(current_user_id)):
    return _handle(search_users, user_id, q)

@router.get("/me/friends", response_model=List[FriendResponse])
def read_friends(user_id: int = Depends(current_user_id)):
    return _handle(get_friends, user_id)

@router.delete("/me/friends/{friend_id}")
def delete_friend(friend_id: int, user_id: int = Depends(current_user_id)):
    return _handle(remove_friend, user_id, friend_id)

@router.get("/me/friend-requests", response_model=FriendRequestList)
def read_friend_requests(user_id: int = Depends(current_user_id)):
    return _handle(get_friend_requests, user_id)

@router.post("/me/friend-requests", status_code=201)
def post_friend_request(body: FriendRequestCreate, user_id: int = Depends(current_user_id)):
    return _handle(send_friend_request, user_id, body.username)

@router.post("/me/friend-requests/{friendship_id}/respond")
def respond_friend_request(friendship_id: int, body: FriendRequestRespond,
                           user_id: int = Depends(current_user_id)):
    return _handle(respond_to_friend_request, user_id, friendship_id, body.accept)

@router.delete("/me/friend-requests/{friendship_id}")
def delete_friend_request(friendship_id: int, user_id: int = Depends(current_user_id)):
    return _handle(cancel_friend_request, user_id, friendship_id)

# Friend lift data — used by the Social tab's comparison table. The service
# layer rejects these unless an accepted friendship exists.

@router.get("/me/friends/{friend_id}/exercises")
def read_friend_exercises(friend_id: int, user_id: int = Depends(current_user_id)):
    return _handle(get_friend_exercises, user_id, friend_id)

@router.get("/me/friends/{friend_id}/sets")
def read_friend_sets(friend_id: int, exercise: str, user_id: int = Depends(current_user_id)):
    return _handle(get_friend_sets_for_exercise, user_id, friend_id, exercise)
