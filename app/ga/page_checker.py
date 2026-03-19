from __future__ import annotations
import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin
import httpx

# GTM-XXXXXの存在確認（方式問わず）
_GTM_ID_RE = re.compile(r'(GTM-[A-Z0-9]+)', re.IGNORECASE)

# 推奨実装: gtm.js スクリプト形式
_GTM_SCRIPT_RE = re.compile(r'googletagmanager\.com/gtm\.js\?id=(GTM-[A-Z0-9]+)', re.IGNORECASE)
# 推奨実装: noscript形式
_GTM_NOSCRIPT_RE = re.compile(r'googletagmanager\.com/ns\.html\?id=(GTM-[A-Z0-9]+)', re.IGNORECASE)


@dataclass
class PageCheckResult:
    url: str
    status: int | None = None
    gtm_container_ids: list[str] = field(default_factory=list)   # 全GTM ID（方式問わず）
    recommended_script: bool = False   # 推奨スクリプト形式で実装されているか
    recommended_noscript: bool = False # 推奨noscript形式で実装されているか
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

        # GTM IDが全く存在しない
        if expected_container_id not in self.gtm_container_ids:
            issues.append(f"GTM container {expected_container_id} not found")
            return issues

        # GTM IDは存在するが推奨形式かチェック
        if not self.recommended_script:
            issues.append(f"GTM tag found but not using recommended script format (gtm.js)")
        if not self.recommended_noscript:
            issues.append(f"GTM noscript tag missing or not using recommended format (ns.html)")

        return issues


async def check_page(session: httpx.AsyncClient, url: str) -> PageCheckResult:
    try:
        r = await session.get(url, timeout=10, follow_redirects=True)
        html = r.text

        # 全GTM IDを取得（方式問わず）
        all_ids = _GTM_ID_RE.findall(html)
        all_ids = [i.upper() for i in all_ids]

        # 推奨形式のチェック
        script_ids = _GTM_SCRIPT_RE.findall(html)
        noscript_ids = _GTM_NOSCRIPT_RE.findall(html)

        return PageCheckResult(
            url=url,
            status=r.status_code,
            gtm_container_ids=list(set(all_ids)),
            recommended_script=bool(script_ids),
            recommended_noscript=bool(noscript_ids),
        )
    except httpx.TimeoutException:
        return PageCheckResult(url=url, error="Timeout")
    except Exception as e:
        return PageCheckResult(url=url, error=str(e)[:100])
