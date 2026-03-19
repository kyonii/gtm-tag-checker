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


def _collect_measurement_ids(container: GTMContainer) -> dict[str, list[str]]:
    """GTMコンテナから測定IDを収集する。
    対象:
    - googtag (Google タグ): tagId パラメータ
    - gaawc (GA4 設定タグ): measurementId パラメータ
    - gaawe (GA4 イベントタグ): measurementId パラメータ（直接指定のみ）
    変数参照 ({{...}}) は除外する。
    """
    result: dict[str, list[str]] = {}

    for tag in container.tags:
        if tag.paused:
            continue

        candidate_ids: list[str] = []

        if tag.type == "googtag":
            # Google タグ: tagId パラメータに測定IDが入る
            for p in tag.parameters:
                if p.get("key") == "tagId":
                    val = p.get("value", "")
                    if val and not val.startswith("{{"):
                        candidate_ids.append(val)

        elif tag.type in ("gaawc", "gaawe"):
            # GA4 設定タグ・イベントタグ: measurementId パラメータ
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


def check_ga_gtm_alignment(container: GTMContainer, property: GAProperty) -> GACheckReport:
    gtm_measurement_ids = _collect_measurement_ids(container)

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

    # GTM側にあってGAに対応するストリームがないIDも検出
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
