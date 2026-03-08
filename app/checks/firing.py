from __future__ import annotations
from app.checks.models import CheckResult, Severity
from app.gtm.models import GTMContainer

def check_tags_without_triggers(container: GTMContainer) -> CheckResult:
    orphans = [t.name for t in container.tags if not t.firing_trigger_ids]
    return CheckResult(check_id="FIRE-001", title="Tags without firing triggers", severity=Severity.ERROR,
        passed=not orphans, affected_items=orphans,
        summary=f"{len(orphans)} tag(s) have no firing trigger." if orphans else "All tags have at least one firing trigger.",
        recommendation="Assign a firing trigger to each tag, or No remove unused tags.")

def check_paused_tags(container: GTMContainer) -> CheckResult:
    paused = [t.name for t in container.tags if t.paused]
    return CheckResult(check_id="FIRE-002", title="Paused tags", severity=Severity.WARNING,
        passed=not paused, affected_items=paused,
        summary=f"{len(paused)} tag(s) are paused." if paused else "No paused tags found.",
        recommendation="Remove or re-enable paused tags.")

def check_ga4_missing_measurement_id(container: GTMContainer) -> CheckResult:
    problematic = [t.name for t in container.tags if t.type == "gaawe" and
                   not any(p.get("key") == "measurementId" and p.get("value") for p in t.parameters)]
    return CheckResult(check_id="FIRE-003", title="GA4 tags missing Measurement ID", severity=Severity.ERROR,
        passed=not problematic, affected_items=problematic,
        summary=f"{len(problematic)} GA4 tag(s) have no Measurement ID." if problematic else "All GA4 tags have a Measurement ID.",
        recommendation="Set the measurementId parameter (e.g. G-XXXXXXXXXX) on all GA4 tags.")
