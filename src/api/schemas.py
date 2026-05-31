from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

# USER SCHEMAS

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)

class UserResponse(BaseModel):
    user_id: int
    username: str
    created_at: Optional[datetime] = None

# SESSION SCHEMAS
class SessionCreate(BaseModel):
    performed_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    session_name: Optional[str] = Field(None, max_length=100)

class SessionResponse(BaseModel):
    session_id: int
    user_id: int
    performed_at: datetime
    notes: Optional[str] = None
    ended_at: Optional[datetime] = None
    session_name: Optional[str] = None

# SET SCHEMAS
class SetCreate(BaseModel):
    exercise: str = Field(..., min_length=1, max_length=100)
    weight: float = Field(..., ge=0)
    reps: int = Field(..., ge=1)
    is_1rm: bool = False

# CONVENIENCE SCHEMAS
class SetCreateRequest(BaseModel):
    sets: List[SetCreate] = Field(..., min_length=1)
