"""失敗診断に載せてよい入力だけを通す sanitizer（FLW-FR-013 / FLW-DSN-015）。

診断へ含めてよいのは**引数名・リポジトリ相対の安全表現・長さ・digest・許容候補**だけである。
絶対 path、URL の userinfo、token pattern、制御文字は通さない。

`result.escape_line` との責務の違い:

- `escape_line` は「1項目1行を保つための**表示層**」。すでに載せると決めた値を整形する。
- 本モジュールは「そもそも載せてよいか」を決める**入力層**。

遮断した事実は必ず可視化する。黙って落とすと、呼出側は診断が不完全であることに気づけない。
遮断した値は長さと digest だけを残すので、同じ値かどうかの照合は後からでもできる。

なお `data.target` が repo 外を指すときに canonical absolute path を返すのは
`references/output-contract.md` が定める**別経路**であり、本モジュールの対象外である。
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from . import result as R

KIND_ABSOLUTE_PATH = "absolute-path"
KIND_URL_USERINFO = "url-userinfo"
KIND_TOKEN = "token"
KIND_CONTROL_CHAR = "control-char"
KIND_OUTSIDE_REPO = "outside-repo"
REDACTION_KINDS = (
    KIND_ABSOLUTE_PATH,
    KIND_URL_USERINFO,
    KIND_TOKEN,
    KIND_CONTROL_CHAR,
    KIND_OUTSIDE_REPO,
)

#: 改行・復帰・tab も含めて遮断する。表示層（escape_line）は「載せると決めた値」を整形するだけで、
#: 診断入力としての改行混入は 1項目1行の契約とログの可読性を壊すため入口で止める。
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_URL_USERINFO = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s@]+@")
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_PATH = re.compile(r"^\\\\")

#: 既知の credential 前置き。網羅ではなく、汎用の長い不透明文字列検査と併用する。
_TOKEN_PREFIXES = (
    "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_",
    "sk-", "xoxb-", "xoxp-", "AKIA", "ASIA", "AIza", "glpat-",
)
#: 20 文字以上の不透明な英数字列は credential の疑いとして扱う。
_OPAQUE_RUN = re.compile(r"(?<![A-Za-z0-9_\-])[A-Za-z0-9_\-]{20,}(?![A-Za-z0-9_\-])")
#: digest は許可する（`sha256:<64hex>`）。
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclasses.dataclass(frozen=True)
class Redaction:
    """遮断した事実の可視化。値そのものは持たない。"""

    field: str
    kind: str
    length: int
    digest: str

    def as_line(self) -> str:
        return f"REDACTED field={self.field} kind={self.kind} length={self.length} digest={self.digest}"


@dataclasses.dataclass(frozen=True)
class SafeDiagnostic:
    values: dict[str, str]
    redactions: tuple[Redaction, ...]

    @property
    def clean(self) -> bool:
        return not self.redactions


def _redaction(field: str, value: str, kind: str) -> Redaction:
    return Redaction(
        field=field,
        kind=kind,
        length=len(value),
        digest=R.sha256_of(value.encode("utf-8")),
    )


def classify(value: str) -> str | None:
    """遮断すべき理由を返す。載せてよければ None。"""
    if _CONTROL_CHARS.search(value):
        return KIND_CONTROL_CHAR
    if _URL_USERINFO.search(value):
        return KIND_URL_USERINFO
    if _DIGEST.match(value):
        return None
    if value.startswith("/") or _WINDOWS_ABSOLUTE.match(value) or _UNC_PATH.match(value):
        return KIND_ABSOLUTE_PATH
    if any(prefix in value for prefix in _TOKEN_PREFIXES):
        return KIND_TOKEN
    if _OPAQUE_RUN.search(value):
        return KIND_TOKEN
    return None


def sanitize_value(field: str, value: str) -> tuple[str | None, Redaction | None]:
    """1つの値を検査する。遮断した場合は値を返さず Redaction を返す。"""
    kind = classify(value)
    if kind is None:
        return value, None
    return None, _redaction(field, value, kind)


def relative_to_repo(field: str, path: str, repo_root: str | Path) -> tuple[str | None, Redaction | None]:
    """repo 配下の path だけを相対表現で通す。repo 外は診断へ載せない。"""
    try:
        resolved = Path(path).resolve()
        root = Path(repo_root).resolve()
        relative = resolved.relative_to(root)
    except (ValueError, OSError):
        return None, _redaction(field, path, KIND_OUTSIDE_REPO)
    text = PurePosixPath(*relative.parts).as_posix() if relative.parts else "."
    kind = classify(text)
    if kind is not None:
        return None, _redaction(field, path, kind)
    return text, None


def sanitize_diagnostic(fields: dict[str, str], *, repo_root: str | Path | None = None) -> SafeDiagnostic:
    """診断用の field 群をまとめて検査する。"""
    values: dict[str, str] = {}
    redactions: list[Redaction] = []
    for field, raw in fields.items():
        if repo_root is not None and field.endswith("_path"):
            safe, redaction = relative_to_repo(field, raw, repo_root)
        else:
            safe, redaction = sanitize_value(field, raw)
        if redaction is not None:
            redactions.append(redaction)
        else:
            values[field] = safe  # type: ignore[assignment]
    return SafeDiagnostic(values=values, redactions=tuple(redactions))


def allowed_causes() -> tuple[str, ...]:
    """診断に載せてよい cause の許可語彙（正は result モジュール）。"""
    return tuple(sorted(R.ALLOWED_CAUSES))


def normalize_cause(cause: str | None) -> str | None:
    """許可語彙に無い cause は診断へ載せない。生の Git メッセージを通さないための関門。"""
    if cause is None:
        return None
    return cause if cause in R.ALLOWED_CAUSES else None


# --- 秘密値 canary -------------------------------------------------------------


def detect_canaries(text: str, canaries: Iterable[str]) -> list[str]:
    """raw log 等に仕込んだ canary の検出。1件でも見つかれば Gate を停止できる。"""
    return [c for c in canaries if c and c in text]


def canary_clean(text: str, canaries: Iterable[str]) -> bool:
    return not detect_canaries(text, canaries)


def windows_path_is_absolute(value: str) -> bool:
    """platform に依存せず Windows 絶対 path を判定する（POSIX 上の検査でも効かせる）。"""
    return bool(_WINDOWS_ABSOLUTE.match(value) or _UNC_PATH.match(value)) or PureWindowsPath(
        value
    ).is_absolute()
