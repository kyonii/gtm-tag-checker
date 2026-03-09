from __future__ import annotations
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from app.gtm.models import GTMContainer

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


@dataclass
class NamingRule:
    """帰納された命名規則"""
    prefix: str            # 推奨プレフィックス（例: "GA4 event"）
    separator: str         # 区切り文字（"_", "-", " ", "|", "/"）
    description: str       # 人間が読める説明（例: "GA4 event_イベント名"）
    count: int             # この規則に一致するタグ数
    members: list[str] = field(default_factory=list)


@dataclass
class NamingConvention:
    """タグ種別ごとの命名規則分析結果"""
    tag_type: str
    tag_type_label: str
    total: int
    rule: NamingRule | None          # 帰納された規則（Noneなら規則性なし）
    conforming: list[str]            # 規則に従っているタグ
    outliers: list[str]              # 規則に外れているタグ
    confidence: float                # 規則の信頼度（一致率）
    all_patterns: list[NamingRule]   # 全パターン一覧（件数順）


def _tokenize(name: str) -> tuple[str, str, str]:
    """
    名前をプレフィックス・区切り文字・残りに分解する。
    例: "GA4 event_partner_click" -> ("GA4 event", "_", "partner_click")
    例: "[GA4] event_name"        -> ("[GA4]", " ", "event_name")
    例: "GA4-event-name"          -> ("GA4", "-", "event-name")
    """
    # ブラケット記法: [PREFIX] rest
    m = re.match(r"^(\[[^\]]+\])\s*(.*)", name)
    if m:
        rest = m.group(2)
        sep = _first_sep(rest) if rest else " "
        return m.group(1), " ", rest

    # 「プレフィックス1 プレフィックス2_rest」のような複合プレフィックスを検出
    # まず全区切り文字の位置を調べて一番多く使われている区切り文字を主区切りとする
    seps_found = re.findall(r"[_\-|/]", name)
    spaces_found = re.findall(r" ", name)

    # スペースが最も多い場合はスペース区切り
    # それ以外はスペース以外の最初の区切り文字を主区切りとする
    if not seps_found and not spaces_found:
        return name, "", ""

    # スペース区切りの場合: 最初のスペースまでをプレフィックスとする
    if not seps_found:
        parts = name.split(" ", 1)
        return parts[0], " ", parts[1] if len(parts) > 1 else ""

    # スペース以外の区切りが主の場合
    main_sep = Counter(seps_found).most_common(1)[0][0]

    # ただしスペースが最初に来る場合は複合プレフィックスを形成している可能性
    # 例: "GA4 event_foo" -> prefix="GA4 event", sep="_"
    first_space = name.find(" ")
    first_main_sep = name.find(main_sep)

    if first_space != -1 and first_space < first_main_sep:
        # スペースが先に来る -> スペースまでを第1トークン、その後main_sepまでを第2トークン
        # "GA4 event_foo" のようなケース
        before_sep = name[:first_main_sep]  # "GA4 event"
        after_sep = name[first_main_sep + 1:]  # "foo"
        return before_sep, main_sep, after_sep
    else:
        parts = name.split(main_sep, 1)
        return parts[0], main_sep, parts[1] if len(parts) > 1 else ""


def _first_sep(s: str) -> str:
    m = re.search(r"[_\-|/ ]", s)
    return m.group(0) if m else ""


def _normalize(prefix: str) -> str:
    return prefix.strip().lower()


def analyze_naming_conventions(container: GTMContainer) -> list[NamingConvention]:
    """コンテナ内のタグの命名規則を種別ごとに帰納して返す"""
    by_type: dict[str, list[str]] = defaultdict(list)
    for tag in container.tags:
        by_type[tag.type].append(tag.name)

    results: list[NamingConvention] = []

    for tag_type, names in by_type.items():
        if len(names) < 2:
            continue

        # 各タグをトークン化してパターン集計
        pattern_map: dict[tuple[str, str], NamingRule] = {}
        for name in names:
            prefix, sep, rest = _tokenize(name)
            key = (_normalize(prefix), sep)
            if key not in pattern_map:
                sep_display = {"_": "_", "-": "-", " ": " ", "|": "|", "/": "/", "": "(なし)"}.get(sep, sep)
                description = f"{prefix}{sep}..." if sep else prefix
                pattern_map[key] = NamingRule(
                    prefix=prefix,
                    separator=sep,
                    description=description,
                    count=0,
                )
            pattern_map[key].count += 1
            pattern_map[key].members.append(name)

        all_patterns = sorted(pattern_map.values(), key=lambda p: p.count, reverse=True)
        if not all_patterns:
            continue

        # 最多パターンを推奨規則とする
        # ただし信頼度が低い（50%未満）場合は「規則性なし」とする
        top = all_patterns[0]
        confidence = top.count / len(names)

        if confidence >= 0.5:
            rule = top
            conforming = list(top.members)
            outliers = [n for n in names if n not in conforming]
        else:
            # 過半数を占めるパターンがない -> 規則性なし
            rule = None
            conforming = []
            outliers = []

        results.append(NamingConvention(
            tag_type=tag_type,
            tag_type_label=TAG_TYPE_LABELS.get(tag_type, tag_type),
            total=len(names),
            rule=rule,
            conforming=conforming,
            outliers=outliers,
            confidence=confidence,
            all_patterns=all_patterns,
        ))

    # outlierがあるもの優先、次にconfidenceが低いもの
    results.sort(key=lambda r: (len(r.outliers) == 0, -len(r.outliers)))
    return results
