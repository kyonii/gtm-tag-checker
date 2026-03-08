from __future__ import annotations
from fastapi import Request
from app.auth.session import get_session

class AuthenticatedUser:
    def __init__(self, email: str, name: str, picture: str, access_token: str) -> None:
        self.email = email; self.name = name; self.picture = picture; self.access_token = access_token

class _LoginRedirect(Exception):
    pass

async def get_current_user(request: Request) -> AuthenticatedUser:
    session = get_session(request)
    if not session.get("email"):
        raise _LoginRedirect()
    return AuthenticatedUser(email=session["email"], name=session.get("name", ""),
                             picture=session.get("picture", ""), access_token=session.get("access_token", ""))
