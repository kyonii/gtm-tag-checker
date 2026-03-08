from __future__ import annotations
from app.checks.duplicate import check_duplicate_firing_triggers, check_multiple_google_analytics_tags
from app.checks.firing import check_ga4_missing_measurement_id, check_paused_tags, check_tags_without_triggers
from app.checks.models import Severity
from app.checks.unused import check_duplicate_ga4_config_tags, check_tags_with_suspicious_names, check_unused_triggers
from app.gtm.models import GTMContainer, GTMTag, GTMTrigger

def _c(**kw): return GTMContainer(account_id="a1", container_id="GTM-TEST", name="Test", **kw)
def _t(name, tag_type="html", tids=None, paused=False, params=None):
    return GTMTag(tag_id=f"t-{name}", name=name, type=tag_type, firing_trigger_ids=tids or [], paused=paused, parameters=params or [])
def _tr(name, tid="tr1"): return GTMTrigger(trigger_id=tid, name=name, type="pageview")

def test_no_trigger_fail(): assert not check_tags_without_triggers(_c(tags=[_t("X")])).passed
def test_no_trigger_pass(): assert check_tags_without_triggers(_c(tags=[_t("X", tids=["tr1"])])).passed
def test_paused_fail(): assert not check_paused_tags(_c(tags=[_t("X", paused=True)])).passed
def test_paused_pass(): assert check_paused_tags(_c(tags=[_t("X")])).passed
def test_ga4_no_id_fail(): assert not check_ga4_missing_measurement_id(_c(tags=[_t("X", "gaawe", ["tr1"])])).passed
def test_ga4_with_id_pass(): assert check_ga4_missing_measurement_id(_c(tags=[_t("X", "gaawe", ["tr1"], params=[{"key":"measurementId","value":"G-X"}])])).passed
def test_unused_trigger_fail(): assert not check_unused_triggers(_c(triggers=[_tr("X", "tr99")])).passed
def test_used_trigger_pass(): assert check_unused_triggers(_c(tags=[_t("X", tids=["tr1"])], triggers=[_tr("X", "tr1")])).passed
def test_dup_ga4_config_fail(): assert not check_duplicate_ga4_config_tags(_c(tags=[_t("A","gaawc"),_t("B","gaawc")])).passed
def test_suspicious_fail(): assert not check_tags_with_suspicious_names(_c(tags=[_t("GA4 test")])).passed
def test_suspicious_pass(): assert check_tags_with_suspicious_names(_c(tags=[_t("Tag - GA4 - PV")])).passed
def test_dup_firing_fail(): assert not check_duplicate_firing_triggers(_c(tags=[_t("A","gaawe",["tr1"]),_t("B","gaawe",["tr1"])])).passed
def test_dup_firing_pass(): assert check_duplicate_firing_triggers(_c(tags=[_t("A","gaawe",["tr1"]),_t("B","gaawe",["tr2"])])).passed
def test_ua_ga4_fail(): assert not check_multiple_google_analytics_tags(_c(tags=[_t("UA","ua",["tr1"]),_t("GA4","gaawc",["tr1"])])).passed
def test_only_ga4_pass(): assert check_multiple_google_analytics_tags(_c(tags=[_t("GA4","gaawc",["tr1"])])).passed
