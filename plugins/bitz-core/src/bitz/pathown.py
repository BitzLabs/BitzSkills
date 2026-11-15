"""パスの存在の検査と、所有・包含の判定（安全な入出力・互換性 §6、複合ワークスペース仕様 §5.1、ADR-071）。

Coreは、Gitがシンボリックリンクを辿らずにリンクそのものを記録するのと同じく、パスのシンボリックリンクを辿らない。
パスは文字列で厳密に比べ、実パス（`realpath`）とファイルシステム上の同一性（デバイスとiノード）は使わない。

- **字句のパス**（:func:`segments`・:func:`lexical_path`）: パスを、Unicode NFCへ正規化したセグメントの列にしたもの。
  比較と包含の判定は文字列だけで行い、ファイルシステムを読まない。セグメントごとにコードポイントの完全一致とし、
  大文字と小文字を区別する（:func:`within`・:func:`owns`）。
- **存在の検査**（:class:`PathResolver`）: 基準のルートから各セグメントを順に、親のディレクトリの項目名（NFC）と完全一致させる。
  0件は不在、2件以上はNFCの衝突、1件ならリンクを辿らない`lstat`で調べる。途中のリンクは拒否、末端のリンクは不在
  （メンバーのパスの診断のため、本実装は :data:`LINK` として区別して返す）、種別の不一致は不在とする。
  ディレクトリの列挙は :class:`PathResolver` の寿命（1回の実行）の中でキャッシュする。
- **所有領域**: ワークスペースのルートの配下から、そのルートの配下にある別のワークスペースのルートの配下を除く。
  ルートワークスペースがメンバーの配下を所有しないための規則である（:func:`owns`）。

判定の呼び出し側（`relations`・`multirelate`・`verify`・`check`・`doctor`・`multiws`）は、文字列の前方一致で包含を判定せず、
本モジュールを使う。
"""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterable
from typing import NamedTuple

# --- 字句のパス ----------------------------------------------------------------------------------


def nfc(text: str) -> str:
    """``text``をUnicode NFCへ正規化する。"""

    return unicodedata.normalize("NFC", text)


def segments(path: str) -> tuple[str, ...]:
    """``path``（絶対または相対）の、NFCにしたセグメントの列を返す（字句のパス。ファイルシステムは読まない）。

    ``.``と空のセグメントだけを字句の上で畳む（:func:`os.path.normpath`）。シンボリックリンクは辿らないので、``..``の畳み込みも字句の操作である。
    """

    return tuple(nfc(seg) for seg in os.path.normpath(path).split(os.sep) if seg)


def lexical_path(path: str) -> str:
    """``path``を字句のパス（NFCのセグメントを``/``で連結した文字列。絶対パスは先頭に``/``を付ける）にして返す。"""

    joined = "/".join(segments(path))
    return "/" + joined if os.path.isabs(path) else joined


def within(path: str, base: str) -> bool:
    """``path``が、``base``自身またはその配下にあるか。NFCにしたセグメントの境界とコードポイントの完全一致で判定する。"""

    return _within_segments(segments(path), segments(base))


def _within_segments(path: tuple[str, ...], base: tuple[str, ...]) -> bool:
    return path[: len(base)] == base


def relative_to(path: str, base: str) -> str | None:
    """``path``の、``base``からの相対パス（``/``区切り）を返す。``base``の配下になければ``None``。

    包含はNFCのセグメントで判定し、返す相対パスは``path``の綴り（宣言したとおりの綴り）のセグメントを使う。
    """

    base_segments = segments(base)
    path_segments = segments(path)
    if not _within_segments(path_segments, base_segments):
        return None
    raw_segments = [seg for seg in os.path.normpath(path).split(os.sep) if seg]
    return "/".join(raw_segments[len(base_segments) :]) or "."


def owns(path: str, area_root: str, all_roots: Iterable[str] = ()) -> bool:
    """``path``が、ルート``area_root``の所有領域にあるか（字句のパスのセグメント単位の包含）。

    所有領域は``area_root``の配下とし、そのルートの配下にある別のワークスペースのルート（``all_roots``）の配下は除く
    （ルートワークスペースは、メンバーの配下を所有しない）。メンバーどうしは入れ子にならないため、メンバーの所有領域は
    ルートの配下の全体になる。
    """

    area = segments(area_root)
    target = segments(path)
    if not _within_segments(target, area):
        return False
    for other_path in all_roots:
        other = segments(other_path)
        if other == area:
            continue
        if _within_segments(other, area) and _within_segments(target, other):
            return False
    return True


def build_nfc_path_index(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    """``(パス, 値)``の列から、NFCにしたパスで引く索引を作る。NFCで同じになるパスが2つ以上あれば、そのパスは索引へ入れない。

    CLIで明示した仕様文書のパスの照合に使う（NFCで2つ以上の仕様文書のパスに一致するパスは、一致しないパスと同じに扱う）。
    """

    index: dict[str, str] = {}
    ambiguous: set[str] = set()
    for path, value in pairs:
        key = nfc(path)
        if key in ambiguous:
            continue
        if key in index and index[key] != value:
            del index[key]
            ambiguous.add(key)
            continue
        index[key] = value
    return index


# --- 存在の検査 ----------------------------------------------------------------------------------

#: 検査の結果。
EXISTS = "exists"
#: 不在（0件、別の綴り、途中のセグメントがディレクトリでない、末端の種別の不一致）。
ABSENT = "absent"
#: NFCで同じ名前になる項目が2件以上ある（NFCの衝突）。パスを拒否する。
COLLISION = "collision"
#: 途中または末端のセグメントがシンボリックリンクである。パスを拒否する（`implements`・`tests[].path`・`cwd`では不在と同じに扱う）。
LINK = "link"

FILE = "file"
DIRECTORY = "dir"


class Resolution(NamedTuple):
    """:meth:`PathResolver.resolve`の結果。``actual``は、``EXISTS``のときの、ファイルシステム上の綴りのセグメントの列。"""

    status: str
    actual: tuple[str, ...] = ()

    @property
    def exists(self) -> bool:
        return self.status == EXISTS


class PathResolver:
    """基準のルートからのパスの存在の検査（安全な入出力・互換性 §6.2）。ディレクトリの列挙をこのインスタンスの中でキャッシュする。

    インスタンスは1回の実行の中で使う。ファイルシステムの変更は、インスタンスの寿命の中では反映しない。
    """

    def __init__(self, root: str) -> None:
        self.root = root
        # 実体の綴りのディレクトリ（基準のルートからのセグメントの列）→ NFCの名前 → 項目の列。読めないディレクトリは``None``。
        self._listings: dict[tuple[str, ...], dict[str, list[os.DirEntry[str]]] | None] = {}

    def _listing(self, parent: tuple[str, ...]) -> dict[str, list[os.DirEntry[str]]] | None:
        if parent in self._listings:
            return self._listings[parent]
        listing: dict[str, list[os.DirEntry[str]]] | None
        try:
            listing = {}
            with os.scandir(os.path.join(self.root, *parent)) as it:
                for entry in it:
                    listing.setdefault(nfc(entry.name), []).append(entry)
        except (OSError, ValueError):
            listing = None
        self._listings[parent] = listing
        return listing

    def resolve(self, rel_path: str, want: str) -> Resolution:
        """``rel_path``（基準のルート相対、``/``区切り）の存在を検査する。``want``は :data:`FILE`（通常のファイル）か :data:`DIRECTORY`。

        ``.``と空のパスは基準のルート自身（ディレクトリ）を指す。字句の検査（絶対パス・``..``・空のセグメントの拒否）は呼び出し側が済ませている前提で、
        ``..``または空のセグメントを含むパスは不在とする。
        """

        if rel_path in ("", "."):
            return Resolution(EXISTS) if want == DIRECTORY and os.path.isdir(self.root) else Resolution(ABSENT)
        parts = rel_path.split("/")
        if any(part in ("", ".", "..") for part in parts):
            return Resolution(ABSENT)
        actual: list[str] = []
        last = len(parts) - 1
        for position, part in enumerate(parts):
            listing = self._listing(tuple(actual))
            if listing is None:
                return Resolution(ABSENT)
            matches = listing.get(nfc(part), [])
            if not matches:
                return Resolution(ABSENT)
            if len(matches) >= 2:
                return Resolution(COLLISION)
            entry = matches[0]
            try:
                is_link = entry.is_symlink()
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                return Resolution(ABSENT)
            if is_link:
                return Resolution(LINK)
            actual.append(entry.name)
            if position < last:
                if not is_dir:
                    return Resolution(ABSENT)
            elif (want == DIRECTORY and not is_dir) or (want == FILE and not is_file):
                return Resolution(ABSENT)
        return Resolution(EXISTS, tuple(actual))
