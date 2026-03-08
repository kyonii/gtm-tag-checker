from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

class Severity(str, Enum):
    ERROR = "error"; WARNING = "warning"; INFO = "info"

class CheckResult(BaseModel):
    check_id: str; title: str; severity: Severity; passed: bool; summary: str
    affected_items: list[str] = Field(default_factory=list); recommendation: str = ""

class AuditReport(BaseModel):
    container_id: str; container_name: str
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def score(self) -> int:
        deductions = sum(10 if r.severity == Severity.ERROR else 3 if r.severity == Severity.WARNING else 1
                         for r in self.results if not r.passed)
        return max(0, 100 - deductions)

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    @property
    def passed_checks(self) -> list[CheckResult]:
        return [r for r in self.results if r.passed]
