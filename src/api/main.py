from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.repository.db import db_init_db
from src.api.routes import users, sessions, sets

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    db_init_db()
    yield
    # Shutdown logic (none needed for now)

app = FastAPI(title="lift_log API", lifespan=lifespan)

app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(sets.router)