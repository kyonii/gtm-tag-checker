from __future__ import annotations
from dataclasses import dataclass, field
import httpx

_ADMIN_BASE = "https://analyticsadmin.googleapis.com/v1beta"


@dataclass
class GAStream:
    stream_id: str
    display_name: str
    measurement_id: str
    default_uri: str


@dataclass
class GAProperty:
    property_id: str
    display_name: str
    account_id: str = ""
    account_name: str = ""
    streams: list[GAStream] = field(default_factory=list)


class GAClient:
    def __init__(self, access_token: str) -> None:
        self._token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _get(self, url: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def list_properties(self) -> list[GAProperty]:
        data = await self._get(f"{_ADMIN_BASE}/accountSummaries?pageSize=200")
        properties: list[GAProperty] = []
        for account in data.get("accountSummaries", []):
            account_id = account.get("account", "")
            account_name = account.get("displayName", account_id)
            for prop in account.get("propertySummaries", []):
                prop_id = prop.get("property", "")
                properties.append(GAProperty(
                    property_id=prop_id,
                    display_name=prop.get("displayName", prop_id),
                    account_id=account_id,
                    account_name=account_name,
                ))
        return properties

    async def list_streams(self, property_id: str) -> list[GAStream]:
        data = await self._get(f"{_ADMIN_BASE}/{property_id}/dataStreams?pageSize=50")
        streams: list[GAStream] = []
        for s in data.get("dataStreams", []):
            web = s.get("webStreamData", {})
            measurement_id = web.get("measurementId", "")
            if not measurement_id:
                continue
            streams.append(GAStream(
                stream_id=s.get("name", ""),
                display_name=s.get("displayName", ""),
                measurement_id=measurement_id,
                default_uri=web.get("defaultUri", ""),
            ))
        return streams

    async def get_property_with_streams(self, property_id: str) -> GAProperty:
        data = await self._get(f"{_ADMIN_BASE}/{property_id}")
        prop = GAProperty(
            property_id=property_id,
            display_name=data.get("displayName", property_id),
        )
        prop.streams = await self.list_streams(property_id)
        return prop
