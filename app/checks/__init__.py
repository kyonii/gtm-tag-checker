from __future__ import annotations
from collections.abc import Callable
from app.checks.duplicate import check_multiple_google_analytics_tags
from app.checks.firing import check_ga4_missing_measurement_id, check_paused_tags, check_tags_without_triggers
from app.checks.models import AuditReport, CheckResult
from app.checks.naming import analyze_naming_conventions
from app.checks.unused import check_duplicate_ga4_config_tags, check_tags_with_suspicious_names, check_unused_triggers
from app.gtm.models import GTMContainer

_ALL_CHECKS: list[Callable[[GTMContainer], CheckResult]] = [
    check_tags_without_triggers, check_paused_tags, check_ga4_missing_measurement_id,
    check_unused_triggers, check_duplicate_ga4_config_tags, check_tags_with_suspicious_names,
    check_multiple_google_analytics_tags,
]

def run_audit(container: GTMContainer) -> AuditReport:
    return AuditReport(
        container_id=container.container_id,
        container_name=container.name,
        results=[check(container) for check in _ALL_CHECKS],
        naming_conventions=analyze_naming_conventions(container),
    )
