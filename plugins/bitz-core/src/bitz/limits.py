"""上限の設定（`bitz.yaml`の`limits`。安全な入出力・互換性 §4.1、ADR-076）。

`limits`の各キーは、対応する上限の値を、1以上、絶対上限以下の整数で小さくする。省略したキーは絶対上限を使う。
本モジュールは、キーと絶対上限の表、設定の検査、実際に使う上限の値（:class:`Limits`）の決定を1箇所に集める。

適用範囲（§4.1）:

- 単一ワークスペースでは、作業ワークスペースの設定の`limits`を使う。複合ワークスペースのスナップショット全体の次元のキーは使わない。
- 複合ワークスペースでは、ルートワークスペースの設定の`limits`を、スナップショット全体の次元、すべてのワークスペースの
  ファイル単位の上限、展開した後の引数列の上限へ使う。メンバーの設定は`limits`を持てない（複合ワークスペース仕様 §10）。
- `check --base`は、現在版の設定から決めた上限を、基準版と現在版の両方へ適用する。

`limits`はコンテキストのハッシュ値の材料に含めない（コンテキストのハッシュ値の正規化仕様 §3）。
"""

from __future__ import annotations

from dataclasses import dataclass, fields

#: `limits`のキーと絶対上限。順序は安全な入出力・互換性 §4.1の表の順（`doctor`の結果の`limits`もこの順に並べる）。
ABSOLUTE_LIMITS: dict[str, int] = {
    "specBytes": 1_048_576,
    "frontmatterBytes": 32_768,
    "specFileCount": 10_000,
    "documentStatementCount": 1_000,
    "documentArrayItemCount": 1_000,
    "inputBytes": 268_435_456,
    "statementCount": 100_000,
    "relationEdgeCount": 1_000_000,
    "traceEntryCount": 1_000_000,
    "commandDefinitionCount": 10_000,
    "verifyBindingCount": 10_000,
    "excludeCount": 100,
    "expandedArgvCount": 10_000,
    "expandedArgvElementBytes": 32_768,
    "expandedArgvBytes": 1_048_576,
    #: 承認済み要求の保護で読む途中のコミットの数（文書・フロントマター・状態仕様 §8.1、ADR-078）。
    "historyCommitCount": 10_000,
}

LIMIT_KEYS: tuple[str, ...] = tuple(ABSOLUTE_LIMITS)


@dataclass(frozen=True)
class Limits:
    """実際に使う上限の値。フィールドの名前は`limits`のキーと同じ。既定値は絶対上限。"""

    specBytes: int = ABSOLUTE_LIMITS["specBytes"]
    frontmatterBytes: int = ABSOLUTE_LIMITS["frontmatterBytes"]
    specFileCount: int = ABSOLUTE_LIMITS["specFileCount"]
    documentStatementCount: int = ABSOLUTE_LIMITS["documentStatementCount"]
    documentArrayItemCount: int = ABSOLUTE_LIMITS["documentArrayItemCount"]
    inputBytes: int = ABSOLUTE_LIMITS["inputBytes"]
    statementCount: int = ABSOLUTE_LIMITS["statementCount"]
    relationEdgeCount: int = ABSOLUTE_LIMITS["relationEdgeCount"]
    traceEntryCount: int = ABSOLUTE_LIMITS["traceEntryCount"]
    commandDefinitionCount: int = ABSOLUTE_LIMITS["commandDefinitionCount"]
    verifyBindingCount: int = ABSOLUTE_LIMITS["verifyBindingCount"]
    excludeCount: int = ABSOLUTE_LIMITS["excludeCount"]
    expandedArgvCount: int = ABSOLUTE_LIMITS["expandedArgvCount"]
    expandedArgvElementBytes: int = ABSOLUTE_LIMITS["expandedArgvElementBytes"]
    expandedArgvBytes: int = ABSOLUTE_LIMITS["expandedArgvBytes"]
    historyCommitCount: int = ABSOLUTE_LIMITS["historyCommitCount"]

    def value(self, key: str) -> int:
        """キーの名前で値を返す（複合ワークスペースの次元の名前は`limits`のキーと同じ）。"""

        return getattr(self, key)

    def is_absolute(self, key: str) -> bool:
        """``key``の値が絶対上限と同じか（絶対上限を使うときは診断の文言を変えない。§4.1）。"""

        return self.value(key) == ABSOLUTE_LIMITS[key]

    def as_result(self) -> dict[str, int]:
        """`doctor`の結果の`limits`（§4.1の表の順のすべてのキー）。"""

        return {key: self.value(key) for key in LIMIT_KEYS}


#: 絶対上限（`limits`を宣言しない設定、または`limits`のすべてのキーを省略した設定）。
ABSOLUTE = Limits()

assert tuple(f.name for f in fields(Limits)) == LIMIT_KEYS


def is_valid_value(key: str, value: object) -> bool:
    """``value``が``key``の値として妥当か（1以上、絶対上限以下の整数。真偽値は整数としない。ワークスペース・設定仕様 §5）。"""

    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= ABSOLUTE_LIMITS[key]


def declares(config: dict | None) -> bool:
    """設定が`limits`を宣言しているか。宣言はキーの有無で判定する（空のマッピングも宣言。`doctor` §7）。"""

    return isinstance(config, dict) and "limits" in config


def from_config(config: dict | None) -> Limits:
    """設定（スキーマの検査を通過したもの）から実際に使う上限の値を決める。

    ``config``が``None``、`limits`を宣言しない、`limits`がマッピングでない場合は絶対上限とする。
    スキーマの検査（:mod:`bitz.config`）は不正な値を持つ設定を停止させるので、通常は不正な値を受け取らない。
    検査を経ない値（例: 基準版の設定）を渡されたときに備え、妥当でない値と未知のキーは無視して絶対上限を使う。
    """

    if not isinstance(config, dict):
        return ABSOLUTE
    raw = config.get("limits")
    if not isinstance(raw, dict):
        return ABSOLUTE
    values = {key: raw[key] for key in LIMIT_KEYS if key in raw and is_valid_value(key, raw[key])}
    if not values:
        return ABSOLUTE
    return Limits(**values)


def for_workspace(config: dict | None, multi_root_config: dict | None = None, *, multi_active: bool = False) -> Limits:
    """操作が使う上限の値を決める（§4.1の適用範囲）。

    複合ワークスペースの処理（``multi_active``）ではルートワークスペースの設定（``multi_root_config``）、
    そうでなければ作業ワークスペースの設定（``config``）から決める。
    """

    return from_config(multi_root_config if multi_active else config)


def doctor_result(config: dict | None, schema_valid: bool) -> dict[str, int] | None:
    """`doctor`の結果の最上位の`limits`（`doctor` §7）。返さないときは``None``。

    設定（複合ワークスペースではルートワークスペースの設定）を読めて、スキーマ（型と値の範囲）に適合し（``schema_valid``）、
    `limits`を宣言している場合だけ、§4.1の表のすべてのキーを実際に使う値で返す。
    """

    if not schema_valid or not declares(config):
        return None
    return from_config(config).as_result()


def format_count(value: int) -> str:
    """件数・次元の上限の値の表記（3桁区切りの整数）。"""

    return f"{value:,}"


def format_bytes(limits: Limits, key: str, absolute_label: str) -> str:
    """単位を付けた上限の表記。絶対上限なら``absolute_label``（例: ``1 MiB``）のまま、小さい値なら3桁区切りの整数に`バイト`を付ける（§4.1）。"""

    if limits.is_absolute(key):
        return absolute_label
    return f"{limits.value(key):,}バイト"
