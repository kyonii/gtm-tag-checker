from __future__ import annotations
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.auth import AuthenticatedUser, _LoginRedirect, get_current_user
from app.auth.oauth import build_authorization_url, exchange_code_for_tokens, fetch_user_info
from app.auth.session import clear_session, get_session, set_session
from app.checks import run_audit
from app.checks.models import Severity
from app.config import settings
from app.ga.checker import check_ga_gtm_alignment, collect_measurement_ids
from app.ga.client import GAClient
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
    response = RedirectResponse(url, status_code=302)
    set_session(response, {"oauth_state": state})
    return response

@app.get("/auth/switch")
async def auth_switch(request: Request, next: str = "/") -> RedirectResponse:
    url, state = build_authorization_url(select_account=True)
    response = RedirectResponse(url, status_code=302)
    next_path = next if next.startswith("/") else "/"
    set_session(response, {"oauth_state": state, "next": next_path})
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
    next_url = session.get("next", "/")
    response = RedirectResponse(next_url, status_code=302)
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
    return templates.TemplateResponse("index.html", {
        "request": request, "user": user,
        "containers": containers, "error": error,
        "current_path": "/",
    })

@app.get("/audit/{account_id}/{container_id}", response_class=HTMLResponse)
async def audit(request: Request, account_id: str, container_id: str,
                user: AuthenticatedUser = Depends(get_current_user)) -> HTMLResponse:
    gtm = GTMClient(access_token=user.access_token)
    try:
        container = await gtm.get_container(account_id=account_id, container_id=container_id)
        report = run_audit(container)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "user": user, "message": str(e)})
    ga = GAClient(access_token=user.access_token)
    try:
        ga_properties = await ga.list_properties()
    except Exception as e:
        print(f"GA ERROR: {type(e).__name__}: {e}")
        ga_properties = []
    # GTMの測定IDを取得
    gtm_ids = collect_measurement_ids(container)  # {mid: [tag_names]}
    # GAプロパティの全ストリームと照合（streamは後でオンデマンド取得）
    return templates.TemplateResponse("report.html", {
        "request": request, "user": user,
        "report": report, "Severity": Severity,
        "account_id": account_id, "container_id": container_id,
        "ga_properties": ga_properties,
        "gtm_measurement_ids": gtm_ids,
        "current_path": f"/audit/{account_id}/{container_id}",
    })

@app.get("/audit/{account_id}/{container_id}/ga-overview")
async def ga_overview(request: Request, account_id: str, container_id: str,
                      user: AuthenticatedUser = Depends(get_current_user)) -> JSONResponse:
    """GTMの測定IDをGAプロパティのストリームと照合して権限あり/なしに分類する"""
    gtm = GTMClient(access_token=user.access_token)
    ga = GAClient(access_token=user.access_token)
    try:
        container = await gtm.get_container(account_id=account_id, container_id=container_id)
        gtm_ids = collect_measurement_ids(container)
        ga_properties = await ga.list_properties()

        # 各プロパティのストリームを取得して測定IDで照合
        matched = []
        matched_mids = set()
        for prop in ga_properties:
            try:
                streams = await ga.list_streams(prop.property_id)
                for stream in streams:
                    mid = stream.measurement_id
                    if mid in gtm_ids:
                        matched.append({
                            "property_id": prop.property_id,
                            "property_name": prop.display_name,
                            "account_name": prop.account_name,
                            "measurement_id": mid,
                            "stream_name": stream.display_name,
                            "default_uri": stream.default_uri,
                            "gtm_tag_names": gtm_ids[mid],
                        })
                        matched_mids.add(mid)
            except Exception:
                continue

        # 権限なし = GTMにあるがGAプロパティと一致しない測定ID
        unmatched = [
            {"measurement_id": mid, "gtm_tag_names": names}
            for mid, names in gtm_ids.items()
            if mid not in matched_mids
        ]

        return JSONResponse({"matched": matched, "unmatched": unmatched})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/audit/{account_id}/{container_id}/ga-check")
async def ga_check(request: Request, account_id: str, container_id: str, property_id: str,
                   user: AuthenticatedUser = Depends(get_current_user)) -> JSONResponse:
    """GAプロパティのURLとGTMタグを詳細照合する"""
    gtm = GTMClient(access_token=user.access_token)
    ga = GAClient(access_token=user.access_token)
    try:
        container = await gtm.get_container(account_id=account_id, container_id=container_id)
        full_property_id = property_id if property_id.startswith("properties/") else f"properties/{property_id}"
        streams = await ga.list_streams(full_property_id)
        from app.ga.client import GAProperty
        prop_data = await ga._get(f"https://analyticsadmin.googleapis.com/v1beta/{full_property_id}")
        prop = GAProperty(
            property_id=full_property_id,
            display_name=prop_data.get("displayName", full_property_id),
            streams=streams,
        )
        result = check_ga_gtm_alignment(container, prop)
        return JSONResponse({
            "property_id": result.property_id,
            "property_name": result.property_name,
            "stream_results": [
                {
                    "measurement_id": r.measurement_id,
                    "stream_name": r.stream_name,
                    "default_uri": r.default_uri,
                    "found_in_gtm": r.found_in_gtm,
                    "gtm_tag_names": r.gtm_tag_names,
                    "issues": r.issues,
                }
                for r in result.stream_results
            ],
            "has_issues": result.has_issues,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
