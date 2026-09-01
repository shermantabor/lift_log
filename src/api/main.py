from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.repository.db import db_init_db
from src.api.routes import users, sessions, sets, friends
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    db_init_db()
    yield
    # Shutdown logic (none needed for now)

app = FastAPI(title="lift_log API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://liftlog7.netlify.app",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://0.0.0.0:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(sets.router)
app.include_router(friends.router)