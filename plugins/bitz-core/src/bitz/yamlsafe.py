"""`workspace・設定仕様 §8` が定めるYAML 1.2部分集合の安全な読取り。

ruamel.yamlのevent列（``YAML(typ="safe").parse()``）を使い、Core自身が値を組み立てる。
anchor、alias、custom tag、merge key、複雑key、複数document、重複mapping keyは
値の解釈前に拒否する。scalarの解決（null／文字列／真偽値／10進整数／有限10進number）も
libraryの既定挙動に頼らずCoreが行う。
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from ruamel.yaml import YAML
from ruamel.yaml.events import (
    AliasEvent,
    DocumentStartEvent,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
    StreamEndEvent,
    StreamStartEvent,
)
from ruamel.yaml.error import YAMLError


class YamlSyntaxError(Exception):
    """設定YAMLの構文自体が不正（`CONFIG-YAML-SYNTAX`相当）。

    ``line``は構文破綻の発端になったevent位置（0始まり行番号）のbest-effort値。
    呼び出し側（Frontmatter）はこれを使って直前の直下keyを推定できる。判定できない場合はNone。
    """

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(message)
        self.line = line


@dataclass
class YamlForbiddenError(Exception):
    """禁止構文を検出した（`CONFIG-YAML-FORBIDDEN`相当）。"""

    summary: str
    key: str | None

    def __str__(self) -> str:  # pragma: no cover - デバッグ用途
        return self.summary


_INT_RE = re.compile(r"^[+-]?[0-9]+$")
_FLOAT_RE = re.compile(
    r"^[+-]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
    r"|^[+-]?[0-9]+[eE][+-]?[0-9]+$"
)


def _join_key(path: list[str]) -> str | None:
    return ".".join(path) if path else None


def _resolve_scalar(ev: ScalarEvent, path: list[str], label: str) -> object:
    if ev.anchor is not None:
        raise YamlForbiddenError(f"{label}のanchorは禁止です", _join_key(path))
    if ev.tag is not None:
        raise YamlForbiddenError(f"{label}のcustom tagは禁止です", _join_key(path))
    value = ev.value
    # style: None/'' はplain、"'"/'"'/'|'/'>' は明示引用・block scalar。
    style = getattr(ev, "style", None)
    if style not in (None, ""):
        return value
    if value in ("", "~", "null"):
        return None
    if value in ("true", "false"):
        return value == "true"
    if _INT_RE.match(value):
        return int(value, 10)
    if _FLOAT_RE.match(value):
        try:
            f = float(value)
        except ValueError:
            return value
        if f == f and f not in (float("inf"), float("-inf")):
            return f
        return value
    return value


def _build(events: list, idx: int, path: list[str], label: str) -> tuple[object, int]:
    ev = events[idx]
    if isinstance(ev, AliasEvent):
        raise YamlForbiddenError(f"{label}のaliasは禁止です", _join_key(path))
    if isinstance(ev, ScalarEvent):
        return _resolve_scalar(ev, path, label), idx + 1
    if isinstance(ev, SequenceStartEvent):
        if ev.anchor is not None:
            raise YamlForbiddenError(f"{label}のanchorは禁止です", _join_key(path))
        if ev.tag is not None:
            raise YamlForbiddenError(f"{label}のcustom tagは禁止です", _join_key(path))
        idx += 1
        items: list[object] = []
        i = 0
        while not isinstance(events[idx], SequenceEndEvent):
            value, idx = _build(events, idx, path + [str(i)], label)
            items.append(value)
            i += 1
        return items, idx + 1
    if isinstance(ev, MappingStartEvent):
        if ev.anchor is not None:
            raise YamlForbiddenError(f"{label}のanchorは禁止です", _join_key(path))
        if ev.tag is not None:
            raise YamlForbiddenError(f"{label}のcustom tagは禁止です", _join_key(path))
        idx += 1
        result: dict[str, object] = {}
        while not isinstance(events[idx], MappingEndEvent):
            key_ev = events[idx]
            if not isinstance(key_ev, ScalarEvent):
                raise YamlForbiddenError(f"{label}の複雑keyは禁止です", _join_key(path))
            if key_ev.anchor is not None or key_ev.tag is not None:
                raise YamlForbiddenError(f"{label}のanchorは禁止です", _join_key(path))
            key = _resolve_scalar(key_ev, path, label)
            if not isinstance(key, str):
                raise YamlForbiddenError(
                    f"{label}のmapping keyは文字列だけを許可します", _join_key(path)
                )
            if key == "<<":
                raise YamlForbiddenError(f"{label}のmerge keyは禁止です", _join_key(path + [key]))
            idx += 1
            value, idx = _build(events, idx, path + [key], label)
            if key in result:
                raise YamlForbiddenError(
                    f"{label}の重複mapping keyは禁止です", _join_key(path + [key])
                )
            result[key] = value
        return result, idx + 1
    raise AssertionError(f"予期しないevent: {ev!r}")


def parse_yaml_subset(text: str, *, label: str = "設定YAML") -> object:
    """YAML 1.2部分集合として解析し、Pythonの値（str/int/float/bool/None/list/dict）を返す。

    構文不正は :class:`YamlSyntaxError`、禁止構文は :class:`YamlForbiddenError` を送出する。
    空document（内容が空）はNoneを返す。``label``は禁止構文Diagnosticの文面に使う対象名
    （既定は設定fileの「設定YAML」、Frontmatterは呼び出し側が別labelを渡す）。
    """

    yaml = YAML(typ="safe")
    try:
        events = list(yaml.parse(io.StringIO(text)))
    except YAMLError as exc:
        mark = getattr(exc, "context_mark", None) or getattr(exc, "problem_mark", None)
        line = mark.line if mark is not None else None
        raise YamlSyntaxError(str(exc), line=line) from exc

    if not events or not isinstance(events[0], StreamStartEvent):
        raise YamlSyntaxError(f"{label}の構文が不正です")

    doc_starts = [i for i, e in enumerate(events) if isinstance(e, DocumentStartEvent)]
    if len(doc_starts) > 1:
        raise YamlForbiddenError(f"{label}の複数documentは禁止です", None)

    idx = 0
    n = len(events)
    while idx < n and not isinstance(events[idx], DocumentStartEvent):
        idx += 1
    if idx >= n:
        return None
    idx += 1  # DocumentStartEventを消費
    if idx < n and isinstance(events[idx], StreamEndEvent):
        return None

    value, idx = _build(events, idx, [], label)
    return value
