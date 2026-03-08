from __future__ import annotations
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.auth import AuthenticatedUser, _LoginRedirect, get_current_user
from app.auth.oauth import build_authorization_url, exchange_code_for_tokens, fetch_user_info
from app.auth.session import clear_session, get_session, set_session
from app.checks import run_audit
from app.checks.models import Severity
from app.config import settings
from app.gtm.client import GTMClient

app = FastAPI(title="GTM Tag Checker", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.exception_handler(_LoginRedirect)
async def login_redirect_handler(request: Request, exc: _LoginRedirect) -> RedirectResponse:
    return RedirectResponse("/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/auth/start")
async def auth_start(request: Request) -> RedirectResponse:
    url, state = build_authorization_url()
    # stateをセッションCookieに保存（redirect前にCookieをセット）
    response = RedirectResponse(url, status_code=302)
    set_session(response, {"oauth_state": state})
    return response

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    if error:
        return RedirectResponse(f"/login?error={error}", status_code=302)
    session = get_session(request)
    saved_state = session.get("oauth_state", "")
    if not saved_state or state != saved_state:
        return RedirectResponse("/login?error=invalid_state", status_code=302)
    tokens = await exchange_code_for_tokens(code)
    user_info = await fetch_user_info(tokens["access_token"])
    allowed = settings.allowed_email_set
    if allowed and user_info.get("email") not in allowed:
        return RedirectResponse("/login?error=unauthorized", status_code=302)
    response = RedirectResponse("/", status_code=302)
    set_session(response, {
        "email": user_info.get("email", ""),
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
    })
    return response

@app.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=302)
    clear_session(response)
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> HTMLResponse:
    gtm = GTMClient(access_token=user.access_token)
    try:
        containers = await gtm.list_containers()
        error = ""
    except Exception as e:
        containers = []; error = str(e)
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "containers": containers, "error": error})

@app.get("/audit/{account_id}/{container_id}", response_class=HTMLResponse)
async def audit(request: Request, account_id: str, container_id: str,
                user: AuthenticatedUser = Depends(get_current_user)) -> HTMLResponse:
    gtm = GTMClient(access_token=user.access_token)
    try:
        container = await gtm.get_container(account_id=account_id, container_id=container_id)
        report = run_audit(container)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "user": user, "message": str(e)})
    return templates.TemplateResponse("report.html", {"request": request, "user": user, "report": report, "Severity": Severity})
