from __future__ import annotations
from typing import Any
import httpx
from app.gtm.models import GTMContainer, GTMContainerSummary, GTMTag, GTMTrigger

_BASE = "https://www.googleapis.com/tagmanager/v2"

class GTMClient:
    def __init__(self, access_token: str, http: httpx.AsyncClient | None = None) -> None:
        self._token = access_token; self._http = http

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _get(self, path: str) -> dict[str, Any]:
        if self._http:
            r = await self._http.get(f"{_BASE}/{path}", headers=self._headers)
        else:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{_BASE}/{path}", headers=self._headers)
        r.raise_for_status()
        return r.json()

    async def list_containers(self) -> list[GTMContainerSummary]:
        data = await self._get("accounts")
        summaries: list[GTMContainerSummary] = []
        for account in data.get("account", []):
            aid = account["accountId"]
            aname = account.get("name", aid)
            for c in (await self._get(f"accounts/{aid}/containers")).get("container", []):
                summaries.append(GTMContainerSummary(
                    account_id=aid,
                    account_name=aname,
                    container_id=c["containerId"],
                    name=c["name"],
                    public_id=c.get("publicId", ""),
                ))
        return summaries

    async def get_container(self, account_id: str, container_id: str) -> GTMContainer:
        wp = await self._get_latest_workspace_path(account_id, container_id)
        tags_data = await self._get(f"{wp}/tags")
        triggers_data = await self._get(f"{wp}/triggers")
        info = await self._get(f"accounts/{account_id}/containers/{container_id}")
        tags = [GTMTag(tag_id=t["tagId"], name=t["name"], type=t["type"],
                       firing_trigger_ids=t.get("firingTriggerId", []),
                       blocking_trigger_ids=t.get("blockingTriggerId", []),
                       paused=t.get("paused", False), parameters=t.get("parameter", []),
                       fingerprint=t.get("fingerprint", "")) for t in tags_data.get("tag", [])]
        triggers = [GTMTrigger(trigger_id=tr["triggerId"], name=tr["name"], type=tr["type"])
                    for tr in triggers_data.get("trigger", [])]
        return GTMContainer(account_id=account_id, container_id=container_id,
                            name=info.get("name", container_id), tags=tags, triggers=triggers)

    async def _get_latest_workspace_path(self, account_id: str, container_id: str) -> str:
        data = await self._get(f"accounts/{account_id}/containers/{container_id}/workspaces")
        workspaces = data.get("workspace", [])
        if not workspaces:
            raise ValueError(f"No workspaces found for container {container_id}")
        return sorted(workspaces, key=lambda w: w.get("fingerprint", ""), reverse=True)[0]["path"]
