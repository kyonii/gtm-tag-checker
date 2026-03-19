from __future__ import annotations
import httpx

_DATA_BASE = "https://analyticsdata.googleapis.com/v1beta"


class GADataClient:
    def __init__(self, access_token: str) -> None:
        self._token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def get_all_page_urls(self, property_id: str) -> list[str]:
        """GA4プロパティで計測された全ページURLを取得する（ページネーション対応）"""
        numeric_id = property_id.replace("properties/", "")
        url = f"{_DATA_BASE}/properties/{numeric_id}:runReport"
        all_urls: list[str] = []
        offset = 0
        limit = 10000  # GA4 Data APIの最大値

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                body = {
                    "dimensions": [{"name": "pagePath"}],
                    "metrics": [{"name": "sessions"}],
                    "dateRanges": [{"startDate": "90daysAgo", "endDate": "today"}],
                    "limit": limit,
                    "offset": offset,
                    "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
                }
                r = await client.post(url, headers=self._headers, json=body)
                r.raise_for_status()
                data = r.json()

                rows = data.get("rows", [])
                for row in rows:
                    path = row.get("dimensionValues", [{}])[0].get("value", "")
                    if path and path != "(not set)":
                        all_urls.append(path)

                row_count = data.get("rowCount", 0)
                offset += len(rows)
                if offset >= row_count or not rows:
                    break

        return all_urls
