from __future__ import annotations
import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin
import httpx

# GTM-XXXXXの存在確認（方式問わず）
_GTM_ID_RE = re.compile(r'(GTM-[A-Z0-9]+)', re.IGNORECASE)


@dataclass
class PageCheckResult:
    url: str
    status: int | None = None
    gtm_container_ids: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def is_ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400

    def check_against(self, expected_container_id: str) -> list[str]:
        issues: list[str] = []
        if self.error:
            issues.append(f"Failed to fetch: {self.error}")
            return issues
        if self.status and self.status >= 400:
            issues.append(f"HTTP {self.status}")
            return issues
        if expected_container_id.upper() not in [i.upper() for i in self.gtm_container_ids]:
            issues.append(f"GTM container {expected_container_id} not found")
        return issues


async def check_page(session: httpx.AsyncClient, url: str) -> PageCheckResult:
    try:
        r = await session.get(url, timeout=10, follow_redirects=True)
        html = r.text
        all_ids = list(set(_GTM_ID_RE.findall(html)))
        return PageCheckResult(url=url, status=r.status_code, gtm_container_ids=all_ids)
    except httpx.TimeoutException:
        return PageCheckResult(url=url, error="Timeout")
    except Exception as e:
        return PageCheckResult(url=url, error=str(e)[:100])
