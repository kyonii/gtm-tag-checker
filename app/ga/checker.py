from __future__ import annotations
from dataclasses import dataclass, field
from app.ga.client import GAProperty
from app.gtm.models import GTMContainer


@dataclass
class StreamCheckResult:
    measurement_id: str
    stream_name: str
    default_uri: str
    found_in_gtm: bool
    gtm_tag_names: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class GACheckReport:
    property_id: str
    property_name: str
    stream_results: list[StreamCheckResult] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return any(r.issues for r in self.stream_results)

    @property
    def missing_streams(self) -> list[StreamCheckResult]:
        return [r for r in self.stream_results if not r.found_in_gtm]

    @property
    def ok_streams(self) -> list[StreamCheckResult]:
        return [r for r in self.stream_results if r.found_in_gtm and not r.issues]


@dataclass
class GAMatchedProperty:
    """GTMの測定IDと一致したGAプロパティ"""
    property_id: str
    property_name: str
    account_name: str
    measurement_id: str
    gtm_tag_name: str


@dataclass
class GAOverview:
    """GTMコンテナとGAプロパティの照合概要"""
    matched: list[GAMatchedProperty]       # 権限あり・GTMに設定あり
    unmatched_ids: list[tuple[str, str]]   # 権限なし (measurement_id, gtm_tag_name)


def collect_measurement_ids(container: GTMContainer) -> dict[str, list[str]]:
    """GTMコンテナから全測定IDを収集する (measurement_id -> [tag_name])"""
    result: dict[str, list[str]] = {}
    for tag in container.tags:
        if tag.paused:
            continue
        candidate_ids: list[str] = []
        if tag.type == "googtag":
            for p in tag.parameters:
                if p.get("key") == "tagId":
                    val = p.get("value", "")
                    if val and not val.startswith("{{"):
                        candidate_ids.append(val)
        elif tag.type in ("gaawc", "gaawe"):
            for p in tag.parameters:
                if p.get("key") == "measurementId":
                    val = p.get("value", "")
                    if val and not val.startswith("{{"):
                        candidate_ids.append(val)
        for mid in candidate_ids:
            if mid not in result:
                result[mid] = []
            result[mid].append(tag.name)
    return result


def build_ga_overview(container: GTMContainer, ga_properties: list[GAProperty]) -> GAOverview:
    """GTMの測定IDをGAプロパティと照合して権限あり/なしに分類する"""
    gtm_ids = collect_measurement_ids(container)

    # GAプロパティの測定ID一覧（property_id -> GAProperty）
    # accountSummaries から取得したプロパティにはstreamsがないので
    # property_idだけで照合する
    ga_id_map: dict[str, GAProperty] = {}
    for prop in ga_properties:
        # property IDから数値部分を取得 (properties/123456 -> 123456)
        numeric_id = prop.property_id.replace("properties/", "")
        ga_id_map[prop.property_id] = prop
        ga_id_map[numeric_id] = prop

    matched: list[GAMatchedProperty] = []
    unmatched_ids: list[tuple[str, str]] = []

    # GAプロパティの測定IDはstreamsから取れるが、list_properties時点では取得していない
    # 代わりにGTMの測定IDを全部拾い、GAプロパティ名と照合する別アプローチが必要
    # → GAプロパティ一覧の各測定IDを取得してマッチングするのは重いので
    #   まずGTMの全測定IDをunmatchedに入れ、GAプロパティと照合済みのものをmatchedに移す

    # 簡略化: ga_propertiesにaccount_summaries由来の情報しかないため
    # 測定IDとプロパティIDの直接紐付けはできない
    # → GTM測定IDを全てunmatchedとして返し、
    #   フロントエンドでRun Checkを押した際にstream照合を行う
    for mid, tag_names in gtm_ids.items():
        unmatched_ids.append((mid, tag_names[0] if tag_names else ""))

    return GAOverview(matched=matched, unmatched_ids=unmatched_ids)


def check_ga_gtm_alignment(container: GTMContainer, property: GAProperty) -> GACheckReport:
    gtm_measurement_ids = collect_measurement_ids(container)

    stream_results: list[StreamCheckResult] = []
    for stream in property.streams:
        mid = stream.measurement_id
        gtm_tags = gtm_measurement_ids.get(mid, [])
        found = bool(gtm_tags)
        issues: list[str] = []
        if not found:
            issues.append(f"Measurement ID {mid} not found in any GTM tag")
        elif len(gtm_tags) > 1:
            issues.append(f"Measurement ID {mid} appears in {len(gtm_tags)} tags (possible duplicate)")
        stream_results.append(StreamCheckResult(
            measurement_id=mid,
            stream_name=stream.display_name,
            default_uri=stream.default_uri,
            found_in_gtm=found,
            gtm_tag_names=gtm_tags,
            issues=issues,
        ))

    ga_ids = {s.measurement_id for s in property.streams}
    for mid, tag_names in gtm_measurement_ids.items():
        if mid not in ga_ids:
            stream_results.append(StreamCheckResult(
                measurement_id=mid,
                stream_name="(unknown stream)",
                default_uri="",
                found_in_gtm=True,
                gtm_tag_names=tag_names,
                issues=[f"{mid} exists in GTM but not found in this GA property's streams"],
            ))

    return GACheckReport(
        property_id=property.property_id,
        property_name=property.display_name,
        stream_results=stream_results,
    )
