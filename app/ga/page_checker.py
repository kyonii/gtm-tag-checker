from __future__ import annotations
import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin
import httpx


@dataclass
class PageCheckResult:
    url: str
    status: int | None = None
    gtm_container_ids: list[str] = field(default_factory=list)
    has_noscript: bool = False
    error: str | None = None

    @property
    def is_ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400

    def check_against(self, expected_container_id: str) -> list[str]:
        """期待するGTMコンテナIDに対してチェックを行い、問題点を返す"""
        issues: list[str] = []
        if self.error:
            issues.append(f"Failed to fetch: {self.error}")
            return issues
        if self.status and self.status >= 400:
            issues.append(f"HTTP {self.status}")
            return issues
        if expected_container_id not in self.gtm_container_ids:
            issues.append(f"GTM container {expected_container_id} not found")
        if self.gtm_container_ids.count(expected_container_id) > 1:
            issues.append(f"GTM container {expected_container_id} appears {self.gtm_container_ids.count(expected_container_id)} times (duplicate)")
        if expected_container_id in self.gtm_container_ids and not self.has_noscript:
            issues.append(f"GTM noscript tag missing (required for non-JS environments)")
        return issues


_GTM_SCRIPT_RE = re.compile(r'googletagmanager\.com/gtm\.js\?id=(GTM-[A-Z0-9]+)', re.IGNORECASE)
_GTM_NOSCRIPT_RE = re.compile(r'googletagmanager\.com/ns\.html\?id=(GTM-[A-Z0-9]+)', re.IGNORECASE)


async def check_page(session: httpx.AsyncClient, url: str) -> PageCheckResult:
    """1ページのGTMタグを確認する"""
    try:
        r = await session.get(url, timeout=10, follow_redirects=True)
        html = r.text
        script_ids = _GTM_SCRIPT_RE.findall(html)
        noscript_ids = _GTM_NOSCRIPT_RE.findall(html)
        return PageCheckResult(
            url=url,
            status=r.status_code,
            gtm_container_ids=script_ids,
            has_noscript=bool(noscript_ids),
        )
    except httpx.TimeoutException:
        return PageCheckResult(url=url, error="Timeout")
    except Exception as e:
        return PageCheckResult(url=url, error=str(e)[:100])


async def check_pages_parallel(
    base_url: str,
    page_paths: list[str],
    gtm_container_id: str,
    concurrency: int = 10,
) -> list[tuple[PageCheckResult, list[str]]]:
    """全ページを並列fetchしてGTMチェックを行う"""
    semaphore = asyncio.Semaphore(concurrency)

    async def check_with_sem(session: httpx.AsyncClient, path: str):
        async with semaphore:
            full_url = urljoin(base_url, path)
            result = await check_page(session, full_url)
            issues = result.check_against(gtm_container_id)
            return result, issues

    headers = {
        "User-Agent": "GTM-Tag-Checker/1.0 (audit tool)",
        "Accept": "text/html",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as session:
        tasks = [check_with_sem(session, path) for path in page_paths]
        return await asyncio.gather(*tasks)
