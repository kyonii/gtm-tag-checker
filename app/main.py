from __future__ import annotations
import asyncio
import json
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.auth import AuthenticatedUser, _LoginRedirect, get_current_user
from app.auth.oauth import build_authorization_url, exchange_code_for_tokens, fetch_user_info
from app.auth.session import clear_session, get_session, set_session
from app.checks import run_audit
from app.checks.models import Severity
from app.config import settings
from app.ga.checker import collect_measurement_ids
from app.ga.client import GAClient
from app.ga.data_client import GADataClient
from app.ga.page_checker import check_page
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
        response = RedirectResponse("/login?error=invalid_state", status_code=302)
        clear_session(response)
        return response
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
    gtm_ids = collect_measurement_ids(container)
    return templates.TemplateResponse("report.html", {
        "request": request, "user": user,
        "report": report, "Severity": Severity,
        "account_id": account_id, "container_id": container_id,
        "ga_properties": ga_properties,
        "gtm_measurement_ids": gtm_ids,
        "current_path": f"/audit/{account_id}/{container_id}",
        "gtm_public_id": container.public_id if hasattr(container, 'public_id') else container_id,
    })

@app.get("/audit/{account_id}/{container_id}/ga-overview")
async def ga_overview_sse(request: Request, account_id: str, container_id: str,
                          user: AuthenticatedUser = Depends(get_current_user)) -> StreamingResponse:
    """プロパティを1件ずつ処理してSSEで進捗を返す"""

    async def event_stream():
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        gtm = GTMClient(access_token=user.access_token)
        ga = GAClient(access_token=user.access_token)

        try:
            container = await gtm.get_container(account_id=account_id, container_id=container_id)
            gtm_ids = collect_measurement_ids(container)
            ga_properties = await ga.list_properties()
            total = len(ga_properties)

            yield sse({"type": "total", "total": total})

            matched = []
            matched_mids = set()

            for i, prop in enumerate(ga_properties):
                yield sse({
                    "type": "progress",
                    "current": i + 1,
                    "total": total,
                    "percent": round((i + 1) / total * 100),
                    "property_name": prop.display_name,
                })
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
                    pass

            unmatched = [
                {"measurement_id": mid, "gtm_tag_names": names}
                for mid, names in gtm_ids.items()
                if mid not in matched_mids
            ]

            yield sse({"type": "done", "matched": matched, "unmatched": unmatched})

        except Exception as e:
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/audit/{account_id}/{container_id}/ga-page-check")
async def ga_page_check(
    request: Request,
    account_id: str,
    container_id: str,
    property_id: str,
    gtm_container_id: str,
    base_url: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> StreamingResponse:
    """GA4の全URLをfetchしてGTMタグをチェック。SSEでリアルタイム進捗を返す。"""

    async def event_stream():
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            yield sse({"type": "status", "message": "Fetching page URLs from GA4..."})
            data_client = GADataClient(access_token=user.access_token)
            full_property_id = property_id if property_id.startswith("properties/") else f"properties/{property_id}"

            try:
                page_paths = await data_client.get_all_page_urls(full_property_id)
            except Exception as e:
                yield sse({"type": "error", "message": f"GA4 Data API error: {e}"})
                return

            total = len(page_paths)
            yield sse({"type": "status", "message": f"Found {total} pages. Checking GTM tags...", "total": total})

            if total == 0:
                yield sse({"type": "done", "results": [], "summary": {"total": 0, "ok": 0, "issues": 0, "errors": 0}})
                return

            import httpx
            from urllib.parse import urljoin

            semaphore = asyncio.Semaphore(10)
            headers = {"User-Agent": "GTM-Tag-Checker/1.0 (audit tool)", "Accept": "text/html"}

            done_results = []
            batch_size = 20

            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=10) as session:
                for i in range(0, len(page_paths), batch_size):
                    batch = page_paths[i:i+batch_size]
                    base = base_url if base_url.endswith('/') else base_url + '/'

                    async def check_one(path):
                        async with semaphore:
                            full_url = urljoin(base, path.lstrip('/'))
                            result = await check_page(session, full_url)
                            issues = result.check_against(gtm_container_id)
                            return result, issues

                    batch_results = await asyncio.gather(*[check_one(p) for p in batch])
                    done_results.extend(batch_results)

                    yield sse({
                        "type": "progress",
                        "completed": len(done_results),
                        "total": total,
                        "percent": round(len(done_results) / total * 100),
                    })

            ok_count = sum(1 for r, issues in done_results if not issues and r.is_ok)
            issue_count = sum(1 for r, issues in done_results if issues and r.is_ok)
            error_count = sum(1 for r, issues in done_results if not r.is_ok)

            final_results = [
                {
                    "url": r.url,
                    "status": r.status,
                    "gtm_ids": r.gtm_container_ids,
                    "has_noscript": r.has_noscript,
                    "issues": issues,
                    "error": r.error,
                }
                for r, issues in done_results
                if issues or r.error
            ]

            yield sse({
                "type": "done",
                "results": final_results,
                "summary": {"total": total, "ok": ok_count, "issues": issue_count, "errors": error_count},
            })

        except Exception as e:
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
