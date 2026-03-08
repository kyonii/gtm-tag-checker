from __future__ import annotations
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from app.gtm.models import GTMContainer


# GTMタグ種別 -> 人間が読める名前のマッピング
TAG_TYPE_LABELS: dict[str, str] = {
    "gaawc": "GA4 Configuration",
    "gaawe": "GA4 Event",
    "ua": "Universal Analytics",
    "html": "Custom HTML",
    "img": "Custom Image",
    "googtag": "Google Tag",
    "awct": "Google Ads Conversion",
    "sp": "Google Ads Remarketing",
    "flc": "Floodlight Counter",
    "fls": "Floodlight Sales",
    "msft_uet": "Microsoft UET",
    "ljt_gtag": "LinkedIn Insight",
    "baut": "Twitter / X Pixel",
    "gclidw": "Conversion Linker",
}

# 区切り文字パターン
SEP_PATTERNS = [
    (r"^[^_\-|/]+[_][^_\-|/]", "_"),
    (r"^[^_\-|/]+[\-][^_\-|/]", "-"),
    (r"^[^_\-|/]+[|][^_\-|/]", "|"),
    (r"^[^_\-|/]+[/][^_\-|/]", "/"),
    (r"^[^_\-|/ ]+[ ][^_\-|/]", " "),
]


@dataclass
class NamingPattern:
    """一つの命名パターンを表す"""
    prefix: str           # 先頭トークン（例: "GA4 event", "[GA4]"）
    separator: str        # 区切り文字（"_", "-", " ", "|", "/"）
    example: str          # 代表例
    count: int = 0
    members: list[str] = field(default_factory=list)


@dataclass
class NamingConvention:
    """タグ種別ごとの命名規則分析結果"""
    tag_type: str
    tag_type_label: str
    total: int
    recommended_pattern: NamingPattern | None
    outliers: list[str]       # 推奨パターンから外れているタグ名
    all_patterns: list[NamingPattern]
    confidence: float         # 0.0 - 1.0: 推奨パターンへの一致率


def _extract_prefix(name: str) -> tuple[str, str]:
    """名前からプレフィックスと区切り文字を抽出"""
    # ブラケット記法: [GA4] event_name
    m = re.match(r"^(\[[^\]]+\])\s*(.?)", name)
    if m:
        rest = name[m.end(1):].lstrip()
        sep = _detect_sep(rest) if rest else " "
        return m.group(1), sep

    # スペース区切りの先頭2トークン: "GA4 event_name" -> prefix="GA4"
    tokens = re.split(r"([_\-|/ ])", name, maxsplit=2)
    if len(tokens) >= 3:
        return tokens[0], tokens[1]
    return name, ""


def _detect_sep(s: str) -> str:
    for pattern, sep in SEP_PATTERNS:
        if re.match(pattern, s):
            return sep
    return ""


def _normalize_prefix(prefix: str) -> str:
    """プレフィックスを正規化して比較しやすくする"""
    return prefix.strip().lower()


def analyze_naming_conventions(container: GTMContainer) -> list[NamingConvention]:
    """コンテナ内のタグの命名規則を分析する"""
    # タグ種別ごとにグループ化
    by_type: dict[str, list[str]] = defaultdict(list)
    for tag in container.tags:
        by_type[tag.type].append(tag.name)

    results: list[NamingConvention] = []

    for tag_type, names in by_type.items():
        if len(names) < 2:
            # 1件しかないタイプは分析対象外
            continue

        # パターンを集計
        pattern_map: dict[tuple[str, str], NamingPattern] = {}
        for name in names:
            prefix, sep = _extract_prefix(name)
            norm = _normalize_prefix(prefix)
            key = (norm, sep)
            if key not in pattern_map:
                pattern_map[key] = NamingPattern(prefix=prefix, separator=sep, example=name)
            pattern_map[key].count += 1
            pattern_map[key].members.append(name)

        all_patterns = sorted(pattern_map.values(), key=lambda p: p.count, reverse=True)

        if not all_patterns:
            continue

        recommended = all_patterns[0]
        outliers = [
            name for name in names
            if name not in recommended.members
        ]
        confidence = recommended.count / len(names)

        results.append(NamingConvention(
            tag_type=tag_type,
            tag_type_label=TAG_TYPE_LABELS.get(tag_type, tag_type),
            total=len(names),
            recommended_pattern=recommended,
            outliers=outliers,
            all_patterns=all_patterns,
            confidence=confidence,
        ))

    # outlierがあるもの(修正対象あり)を優先、次にconfidenceが低いもの順
    results.sort(key=lambda r: (len(r.outliers) == 0, -len(r.outliers)))
    return results
