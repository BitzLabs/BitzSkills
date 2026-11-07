"""所有と包含の判定（複合ワークスペース仕様 §5.1の手順4・5、ワークスペース・設定仕様 §6・§9）。

所有と包含は、字句のパスではなく実パスで判定する。

- 実パス（手順4）: 存在する各上位のディレクトリのシンボリックリンクを解決した実パスを得る。存在しない予定のパスは、
  最も近い、存在する上位のディレクトリの実パスへ、検査済みの接尾辞を連結する（:func:`real_path`）。
- 包含（手順5）: 実パスの各上位のディレクトリと所有領域のルートのディレクトリを、ファイルシステム上の同一性
  （デバイスとiノード。:func:`os.path.samestat`）で比べ、パスのセグメント境界で包含を判定する（:func:`within`）。
  大文字と小文字、Unicodeの正規化の扱いはファイルシステムに任せ、文字列の折りたたみ表を持たない。
- 所有領域: ワークスペースのルートの配下から、そのルートの配下にある別のワークスペースのルートの配下を除く。
  ルートワークスペースがメンバーの配下を所有しないための規則である（:func:`owns`）。

判定の呼び出し側（`relations`・`multirelate`・`verify`・`check`）は、文字列の前方一致で包含を判定せず、本モジュールを使う。
"""

from __future__ import annotations

import os
from collections.abc import Iterable


def real_path(path: str) -> str:
    """``path``の実パスを返す（手順4）。存在しない接尾辞は、存在する最も近い上位のディレクトリの実パスへ連結する。"""

    return os.path.realpath(path)


def _stat_or_none(path: str) -> os.stat_result | None:
    try:
        return os.stat(path)
    except (OSError, ValueError):
        return None


def _within_stat(real: str, base_stat: os.stat_result) -> bool:
    """``real``自身または存在する上位のディレクトリのどれかが、``base_stat``と同じ実体か。"""

    current = real
    while True:
        st = _stat_or_none(current)
        if st is not None and os.path.samestat(st, base_stat):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def within(real: str, base_real: str) -> bool:
    """実パス``real``が、実パスのディレクトリ``base_real``自身またはその配下にあるか（手順5）。

    実パスの各上位のディレクトリと``base_real``の同一性（デバイスとiノード）で比べる。``base_real``が存在しなければ偽とする。
    """

    base_stat = _stat_or_none(base_real)
    if base_stat is None:
        return False
    return _within_stat(real, base_stat)


def owns(real: str, area_root_real: str, all_roots_real: Iterable[str] = ()) -> bool:
    """実パス``real``が、ルート``area_root_real``の所有領域にあるか。

    所有領域は``area_root_real``の配下とし、そのルートの配下にある別のワークスペースのルート（``all_roots_real``）の配下は除く
    （ルートワークスペースは、メンバーの配下を所有しない）。メンバーどうしは入れ子にならないため、メンバーの所有領域は
    ルートの配下の全体になる。
    """

    base_stat = _stat_or_none(area_root_real)
    if base_stat is None or not _within_stat(real, base_stat):
        return False
    for other in all_roots_real:
        other_stat = _stat_or_none(other)
        if other_stat is None or os.path.samestat(other_stat, base_stat):
            continue
        if _within_stat(other, base_stat) and _within_stat(real, other_stat):
            return False
    return True
