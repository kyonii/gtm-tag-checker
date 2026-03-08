from __future__ import annotations
from app.checks.models import CheckResult, Severity
from app.gtm.models import GTMContainer

def check_unused_triggers(container: GTMContainer) -> CheckResult:
    used_ids = {tid for tag in container.tags for tid in tag.firing_trigger_ids}
    unused = [t.name for t in container.triggers if t.trigger_id not in used_ids]
    return CheckResult(check_id="UNUSED-001", title="Unused triggers", severity=Severity.WARNING,
        passed=not unused, affected_items=unused,
        summary=f"{len(unused)} trigger(s) are not referenced by any tag." if unused else "All triggers are in use.",
        recommendation="Remove unused triggers to keep the container clean.")

def check_duplicate_ga4_config_tags(container: GTMContainer) -> CheckResult:
    configs = [t.name for t in container.tags if t.type == "gaawc"]
    ok = len(configs) <= 1
    return CheckResult(check_id="UNUSED-002", title="Multiple GA4 Configuration tags", severity=Severity.ERROR,
        passed=ok, affected_items=configs if not ok else [],
        summary=f"{len(configs)} GA4 Config tags found – likely causes duplicate events." if not ok else "Only one GA4 Configuration tag found.",
        recommendation="Keep exactly one GA4 Configuration tag. Remove the extras.")

def check_tags_with_suspicious_names(container: GTMContainer) -> CheckResult:
    _SUSPECT = {"test", "temp", "old", "copy", "bak", "draft", "debug", "tmp", "backup"}
    suspicious = [t.name for t in container.tags if any(kw in t.name.lower() for kw in _SUSPECT)]
    return CheckResult(check_id="UNUSED-003", title="Tags with suspicious names", severity=Severity.WARNING,
        passed=not suspicious, affected_items=suspicious,
        summary=f"{len(suspicious)} tag(s) may be temporary or abandoned." if suspicious else "No suspicious tag names found.",
        recommendation="Review and remove tags created for testing or temporary use.")
