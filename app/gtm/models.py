from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class GTMTag(BaseModel):
    tag_id: str; name: str; type: str
    firing_trigger_ids: list[str] = Field(default_factory=list)
    blocking_trigger_ids: list[str] = Field(default_factory=list)
    paused: bool = False
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    fingerprint: str = ""

class GTMTrigger(BaseModel):
    trigger_id: str; name: str; type: str

class GTMContainer(BaseModel):
    account_id: str; container_id: str; name: str
    tags: list[GTMTag] = Field(default_factory=list)
    triggers: list[GTMTrigger] = Field(default_factory=list)

class GTMContainerSummary(BaseModel):
    account_id: str
    account_name: str
    container_id: str
    name: str
    public_id: str
