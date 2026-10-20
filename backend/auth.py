from __future__ import annotations

import datetime as _dt
from typing import Annotated, Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status

from .config import settings
from .db import query

_ALGORITHM = settings.JWT_ALGORITHM


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    expire = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": _dt.datetime.now(_dt.timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def get_user_by_id(user_id: str):
    return query(
        "SELECT id, email, name, created_at FROM docuchat.users WHERE id = %s",
        (user_id,),
        one=True,
    )


def get_user_by_email(email: str):
    return query(
        "SELECT id, email, name, password_hash, created_at FROM docuchat.users WHERE email = %s",
        (email,),
        one=True,
    )


def create_user(email: str, name: str, password: str):
    if get_user_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return query(
        """
        INSERT INTO docuchat.users (email, name, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id, email, name, created_at
        """,
        (email, name, hash_password(password)),
        one=True,
    )


async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = authorization[len("Bearer "):].strip()
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]
