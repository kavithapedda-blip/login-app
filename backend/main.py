"""Minimal FastAPI login service (practice app, in-memory users, no database)."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from pydantic import BaseModel, Field

# --- config from environment ---
SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]


# --- password hashing (bcrypt has a 72-byte input limit) ---
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


# --- JWT issuance ---
def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    # raises jose.JWTError (or a subclass) on bad signature / expired token
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# --- in-memory user store (resets on restart); default login: admin / secret ---
USERS: dict[str, str] = {"admin": hash_password("secret")}

# Pre-computed hash used to keep bcrypt timing constant when a username is
# unknown, so login response time can't be used to enumerate valid usernames.
_DUMMY_HASH = hash_password("unused-constant-time-placeholder")


# --- schemas ---
class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- app ---
app = FastAPI(title="Practice Login App", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # must stay False while allow_origins can be ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "practice-login-app", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: Credentials):
    if body.username in USERS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
    USERS[body.username] = hash_password(body.password)
    return {"message": "registered", "username": body.username}


@app.post("/login", response_model=TokenResponse)
def login(body: Credentials):
    # Always run exactly one bcrypt verify (against a dummy hash for unknown
    # users) so timing doesn't reveal whether the username exists.
    hashed = USERS.get(body.username, _DUMMY_HASH)
    password_ok = verify_password(body.password, hashed)
    if body.username not in USERS or not password_ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(body.username))
