from __future__ import annotations
from app.checks.duplicate import check_multiple_google_analytics_tags
from app.checks.firing import check_ga4_missing_measurement_id, check_paused_tags, check_tags_without_triggers
from app.checks.models import AuditReport, Category, CheckResult
from app.checks.naming import analyze_naming_conventions
from app.checks.unused import check_duplicate_ga4_config_tags, check_tags_with_suspicious_names, check_unused_triggers
from app.gtm.models import GTMContainer


def _as(result: CheckResult, category: Category) -> CheckResult:
    return result.model_copy(update={"category": category})


def run_audit(container: GTMContainer) -> AuditReport:
    results = [
        # リスク系
        _as(check_ga4_missing_measurement_id(container), Category.RISK),
        _as(check_duplicate_ga4_config_tags(container), Category.RISK),
        _as(check_multiple_google_analytics_tags(container), Category.RISK),
        # クリーンアップ系
        _as(check_tags_without_triggers(container), Category.CLEANUP),
        _as(check_paused_tags(container), Category.CLEANUP),
        _as(check_unused_triggers(container), Category.CLEANUP),
        _as(check_tags_with_suspicious_names(container), Category.CLEANUP),
    ]
    return AuditReport(
        container_id=container.container_id,
        container_name=container.name,
        results=results,
        naming_conventions=analyze_naming_conventions(container),
    )
