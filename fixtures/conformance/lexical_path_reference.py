"""字句のパスの参照計算（Coreにも`pathown`にも依存しない。ADR-049、ADR-071）。

正本は[安全な入出力・互換性 §6](../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#6-正規パス)である。
この参照計算は、準備手順の後の作業ツリーから、パスの扱いを次の規則だけで導く。

- パスは、基準のルートから数えたセグメントの列にして、各セグメントをUnicode NFCへ正規化する（字句のパス）。
- 比較と包含は、NFCにしたセグメントのコードポイントの完全一致だけで行い、大文字と小文字を区別する。`realpath`、`resolve`、`samestat`、
  ファイルシステム上の同一性（デバイスとiノード）は使わない。
- 存在の検査（`lookup`）は、基準のルートから各セグメントを順に、親のディレクトリの項目名（NFCにしたもの）と照合する。
  項目が0件なら存在しない（`missing`）、2件以上ならNFCの衝突（`collision`）、1件なら`lstat`で調べ、途中のセグメントがシンボリックリンクなら
  拒否し（`link`）、ディレクトリでなければ存在しない。末端がシンボリックリンクなら通常のファイルにもディレクトリにも扱わない（`link`）。
  求める種別でなければ存在しない（`missing`）。
- 所有（`owner`）は、字句のパスのセグメント単位の包含で行う。ルートの配下から、配下にある別のワークスペースの配下を除く（最も深いルートが所有する）。
"""
import os
from pathlib import Path
import unicodedata


def nfc(text):
    return unicodedata.normalize("NFC", text)


def segments(path):
    """宣言したパス（`/`区切り）の字句のパス。空のセグメント（末尾の`/`の後、`.`だけのパス）は含めない。"""
    return tuple(nfc(part) for part in path.split("/") if part not in ("", "."))


def within(path, base):
    """字句のパス`path`が、字句のパス`base`のセグメントの境界での配下（自身を含む）にあるか。どちらも文字列でよい。"""
    own, root = segments(path), segments(base)
    return own[:len(root)] == root


def owner(path, roots):
    """字句のパス`path`（複合ワークスペースのルートからの相対）を所有するワークスペースのID。最も深いルートが所有する。どれでもなければ`None`。"""
    owners = [(len(segments(root)), identifier) for identifier, root in roots.items() if within(path, root)]
    return max(owners)[1] if owners else None


def lookup(base, declared, want):
    """基準のルート`base`（`Path`）からの宣言したパスの存在の検査。`want`は`file`または`directory`。

    戻り値は`ok`、`missing`（不在、別の綴り、求める種別でない）、`link`（途中または末端がシンボリックリンク）、`collision`（NFCで同じ名前になる項目が複数ある）のどれか。
    """
    names = segments(declared)
    current = Path(base)
    for index, name in enumerate(names):
        try:
            with os.scandir(current) as entries:
                matches = [entry.name for entry in entries if nfc(entry.name) == name]
        except (FileNotFoundError, NotADirectoryError):
            return "missing"
        if not matches:
            return "missing"
        if len(matches) > 1:
            return "collision"
        current = current / matches[0]
        last = index == len(names) - 1
        if os.path.islink(current):
            return "link"
        if last:
            return "ok" if (current.is_file() if want == "file" else current.is_dir()) else "missing"
        if not current.is_dir():
            return "missing"
    return "ok" if want == "directory" else "missing"
