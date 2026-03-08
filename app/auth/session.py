from __future__ import annotations
from typing import Any
from itsdangerous import BadSignature, URLSafeSerializer
from starlette.requests import Request
from starlette.responses import Response
from app.config import settings

_COOKIE_NAME = "session"
_signer = URLSafeSerializer(settings.session_secret_key, salt="session")

def get_session(request: Request) -> dict[str, Any]:
    raw = request.cookies.get(_COOKIE_NAME, "")
    if not raw:
        return {}
    try:
        return _signer.loads(raw)  # type: ignore[no-any-return]
    except BadSignature:
        return {}

def set_session(response: Response, data: dict[str, Any]) -> None:
    response.set_cookie(_COOKIE_NAME, _signer.dumps(data), max_age=60*60*8, httponly=True, samesite="lax")

def clear_session(response: Response) -> None:
    response.delete_cookie(_COOKIE_NAME)
