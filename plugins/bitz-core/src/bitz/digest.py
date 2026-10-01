"""コンテキストのハッシュ値の正規化（`00_共通契約/03_Context-Digest正規化仕様.md`）。

正規JSONへの変換とSHA-256の計算、および`frontmatter`・`bodyText`の正規化を提供する。
`bodyText`の正規化（§3.1.2）は、コンテキスト一式の`documents[].bodyText`とハッシュ値の材料の両方が
共有する同一の値である（`03_操作仕様/01_context.md §4`の例と本書の適合fixtureが同じ文字列を
要求する）。
"""

from __future__ import annotations

import hashlib
import json
import unicodedata

DIGEST_VERSION = "1.0"
RESOLVER_VERSION = "1.0"

#: §3.1.1「relations」の固定の5つのキー（コードポイント辞書順）。
RELATION_KEY_ORDER = ("addresses", "refines", "related", "requires", "supersedes")

#: §4「パスの区切り文字の変換の対象」。
_PATH_LIKE_KEYS = {
    "workspaces[].path",
    "documents[].frontmatter.implements[]",
    "documents[].frontmatter.tests[].path",
    "documents[].frontmatter.changes[]",
    "settings.commands[].cwd",
}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def to_slash(s: str) -> str:
    """§4「3.」: パス型のフィールドだけで、U+005C REVERSE SOLIDUSをU+002F SOLIDUSへ変換する。"""

    return s.replace("\\", "/")


def normalize_body_text(raw: str) -> str:
    """§3.1.2 `bodyText`の正規化。BOMを除き、CRLFとCRをLFへ変換し、行末の空白を除き、先頭と末尾の空行を除き、末尾にLFを付ける。"""

    if raw.startswith("﻿"):
        raw = raw[1:]
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    lines = [ln.rstrip(" \t") for ln in lines]
    start = 0
    while start < len(lines) and lines[start] == "":
        start += 1
    end = len(lines)
    while end > start and lines[end - 1] == "":
        end -= 1
    lines = lines[start:end]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _normalize_value(value):
    """`dict`・`list`・`str`を再帰的にNFC正規化する（§4「1.」）。パスの区切り文字の変換は呼び出し側が個別に行う。

    呼び出し側（`context.py`）は、重複排除と並べ替えの前に、NFCへの正規化とパスの区切り文字の変換を適用済みであるべきである
    （§2「3.正規化を適用する→4.重複排除と並べ替えを正規化後の値へ適用する」の順序）。ここでの再適用は
    その規律を守れなかった値に対する最後の防御のための冪等な処理であり、要素の重複排除や並べ替えの順序を
    やり直すものではない。
    """

    if isinstance(value, str):
        return nfc(value)
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {nfc(k) if isinstance(k, str) else k: _normalize_value(v) for k, v in value.items()}
    return value


def _utf16_key(k: str) -> bytes:
    """§5「オブジェクトのキーはUTF-16のコード単位の昇順に並べる」の比較キー。

    UTF-16BEでエンコードしたバイト列は、コード単位の列を数値として比較した順序と一致する（各コード単位が
    2バイトのビッグエンディアンで、バイト単位の辞書式比較がそのまま16ビット値の大小比較になるため）。附属面文字
    （コードポイント > U+FFFF）はサロゲートペアへ分解されるため、Pythonの文字列の既定（コードポイント）比較
    とは順序が変わりうる（例: U+E000 < U+10000 はコードポイント順だが、U+10000はU+D800前後のサロゲートへ
    分解されるためUTF-16のコード単位順では逆転する）。
    """

    return k.encode("utf-16-be")


def _serialize(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):  # pragma: no cover - digest inputは非整数を持たない
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(v) for v in value) + "]"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: _utf16_key(kv[0]))
        parts = [f"{json.dumps(k, ensure_ascii=False)}:{_serialize(v)}" for k, v in items]
        return "{" + ",".join(parts) + "}"
    raise TypeError(f"digest materialsに含められない型です: {type(value)!r}")


def canonical_bytes(materials: dict) -> bytes:
    """ハッシュ値の材料をRFC 8785準拠の正規JSONへ直列化し、UTF-8のバイト列を返す（§5）。

    オブジェクトのキーの順序は`sorted(..., key=str)`（Pythonのコードポイント順）ではなく、UTF-16のコード単位順
    （:func:`_utf16_key`）で決める。附属面文字を含むキーではコードポイント順と結果が異なる。
    """

    normalized = _normalize_value(materials)
    return _serialize(normalized).encode("utf-8")


def compute_digest(materials: dict) -> str:
    data = canonical_bytes(materials)
    return "sha256:" + hashlib.sha256(data).hexdigest()
