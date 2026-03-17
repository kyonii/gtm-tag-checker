from __future__ import annotations
import secrets
from urllib.parse import urlencode
import httpx
from app.config import settings

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/analytics.readonly",
])

def build_authorization_url(select_account: bool = False) -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "state": state,
    }
    params["prompt"] = "select_account consent" if select_account else "consent"
    return f"{_AUTH_URL}?{urlencode(params)}", state

async def exchange_code_for_tokens(code: str) -> dict[str, str]:
    async with httpx.AsyncClient() as client:
        r = await client.post(_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.oauth_redirect_uri,
            "grant_type": "authorization_code",
        })
        r.raise_for_status()
        return r.json()

async def fetch_user_info(access_token: str) -> dict[str, str]:
    async with httpx.AsyncClient() as client:
        r = await client.get(_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        r.raise_for_status()
        return r.json()
