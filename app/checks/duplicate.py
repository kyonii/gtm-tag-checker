from __future__ import annotations
from collections import defaultdict
from app.checks.models import CheckResult, Severity
from app.gtm.models import GTMContainer

def check_duplicate_firing_triggers(container: GTMContainer) -> CheckResult:
    groups: dict[tuple[str, frozenset[str]], list[str]] = defaultdict(list)
    for tag in container.tags:
        if tag.firing_trigger_ids:
            groups[(tag.type, frozenset(tag.firing_trigger_ids))].append(tag.name)
    pairs = [f"{names[i]} <-> {names[j]}" for names in groups.values() if len(names) > 1
             for i in range(len(names)) for j in range(i + 1, len(names))]
    return CheckResult(check_id="DUP-001", title="Tags with duplicate firing triggers", severity=Severity.ERROR,
        passed=not pairs, affected_items=pairs,
        summary=f"{len(pairs)} pair(s) share the same type and triggers." if pairs else "No duplicate firing trigger combinations found.",
        recommendation="Consolidate duplicate tags into one, or verify the duplication is intentional.")

def check_multiple_google_analytics_tags(container: GTMContainer) -> CheckResult:
    ua = [t.name for t in container.tags if t.type == "ua" and not t.paused]
    ga4 = [t.name for t in container.tags if t.type in ("gaawc", "gaawe") and not t.paused]
    has_both = bool(ua) and bool(ga4)
    return CheckResult(check_id="DUP-002", title="Both Universal Analytics and GA4 tags active", severity=Severity.WARNING,
        passed=not has_both, affected_items=(ua + ga4) if has_both else [],
        summary="Both UA and GA4 tags are active - may cause double-counting." if has_both else "No UA + GA4 co-existence issue found.",
        recommendation="If migration to GA4 is complete, remove or pause all Universal Analytics tags.")
