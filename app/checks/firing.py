from __future__ import annotations
from app.checks.models import CheckResult, Severity
from app.gtm.models import GTMContainer


def check_tags_without_triggers(container: GTMContainer) -> CheckResult:
    orphans = [t.name for t in container.tags if not t.firing_trigger_ids]
    return CheckResult(check_id="FIRE-001", title="Tags without firing triggers", severity=Severity.ERROR,
        passed=not orphans, affected_items=orphans,
        summary=f"{len(orphans)} tag(s) have no firing trigger." if orphans else "All tags have at least one firing trigger.",
        recommendation="Assign a firing trigger to each tag, or remove unused tags.")


def check_paused_tags(container: GTMContainer) -> CheckResult:
    paused = [t.name for t in container.tags if t.paused]
    return CheckResult(check_id="FIRE-002", title="Paused tags", severity=Severity.WARNING,
        passed=not paused, affected_items=paused,
        summary=f"{len(paused)} tag(s) are paused." if paused else "No paused tags found.",
        recommendation="Remove or re-enable paused tags.")


def check_ga4_missing_measurement_id(container: GTMContainer) -> CheckResult:
    # Google Tag (googtag) や GA4 Config (gaawc) タグのIDを収集
    config_tag_ids = {
        t.tag_id for t in container.tags
        if t.type in ("gaawc", "googtag")
    }

    problematic = []
    for t in container.tags:
        if t.type != "gaawe":
            continue

        # 直接 measurementId パラメータがある場合はOK
        has_direct_id = any(
            p.get("key") == "measurementId" and p.get("value")
            for p in t.parameters
        )
        if has_direct_id:
            continue

        # 設定タグへの参照がある場合はOK
        has_config_ref = any(
            p.get("key") in ("tagReference", "gaSettings", "measurementIdOverride")
            and p.get("value")
            for p in t.parameters
        )
        if has_config_ref:
            continue

        # measurementId が {{変数}} 形式の場合はOK
        has_variable_ref = any(
            p.get("key") == "measurementId"
            and isinstance(p.get("value"), str)
            and p["value"].startswith("{{")
            for p in t.parameters
        )
        if has_variable_ref:
            continue

        problematic.append(t.name)

    return CheckResult(
        check_id="FIRE-003",
        title="GA4 tags missing Measurement ID",
        severity=Severity.ERROR,
        passed=not problematic,
        affected_items=problematic,
        summary=(
            f"{len(problematic)} GA4 tag(s) have no Measurement ID and no linked configuration tag."
            if problematic
            else "All GA4 tags have a Measurement ID or linked configuration tag."
        ),
        recommendation="Set the measurementId parameter (e.g. G-XXXXXXXXXX), or link a GA4 Configuration tag.",
    )
