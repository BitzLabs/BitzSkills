"""複合ワークスペースの全体事前検査（複合ワークスペース仕様）。

Step 5Aの範囲: §2（カタログ）、§3（ワークスペースの決定・`--workspace`の終了コード4）、§5.1（メンバーのパスの
正規の判定のうち、セグメントの境界・シンボリックリンク・サブモジュール・別のワークツリー／リポジトリ）、§8（全体操作の発見と
Gitの既知の設定の事前検査）、§10（スナップショット全体のリソースの上限と早期停止）を実装する。
あわせて、除外（`multiWorkspace.exclude`）の検証と、除外した範囲の中の単一ワークスペース・入れ子の複合ワークスペースの決定
（§2・§2.1、ADR-064）を実装する。入れ子の複合ワークスペースでは、`PrecheckResult.repo_root`が入れ子のルートになる。

事前検査が非成功なら :func:`precheck` は ``ok=False`` を返し、呼び出し側（`check.py`／`doctor.py`）は
メンバーの処理（横断する関係の解決、メンバー単位の`check`/`verify`/`context`）を一切開始せず、`workspaces: []`の
全体結果を返す（複合ワークスペース仕様 §8「非成功ならメンバーの処理、コンテキストの解決、テストコマンドの実行を開始せず、
`workspaces: []`で結果を返す」）。メンバーの処理そのものはStep 5B・5Cで実装するため、事前検査を通過した
場合は呼び出し側が既存の:class:`~bitz.notimpl.NotImplementedOperation`の作法で明示的に停止する。
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field

from . import config as config_mod
from . import gitutil
from . import lex
from . import messages
from .config import Diagnostic
from .earsai.scanner import scan_candidates
from .resultmodel import worst_status
from .yamlsafe import YamlForbiddenError, YamlSyntaxError, parse_yaml_subset

# 優先順位（診断レジストリ §7・複合ワークスペース仕様 §11）。同じメンバー／同じ元の原因に複数の
# 候補のコードが成立する場合、最小の`priority`の1件だけを残す（`_PRIORITY.get`の未知のコードは0＝最優先として
# 扱う。メンバー配下から返る一般的な`SPEC-CONFIG-*`系は`SPEC-MULTI-*`系のコードより常に優先する）。
_PRIORITY = {
    "SPEC-MULTI-CONFIG-001": 900,
    "SPEC-MULTI-MEMBER-001": 910,
    "SPEC-MULTI-ID-001": 920,
    "SPEC-MULTI-PATH-001": 930,
    "SPEC-MULTI-GIT-001": 940,
    "SPEC-MULTI-VERSION-001": 950,
    "SPEC-MULTI-UNREGISTERED-001": 960,
    "SPEC-MULTI-LIMIT-001": 970,
}

ROOT_CONFIG_PATH = config_mod.CONFIG_PATH  # ".spec/bitz.yaml"

_SPEC_KIND_DIRS = ("requirements", "technical", "decisions", "tasks")

HARD_LIMITS: dict[str, int] = {
    "memberCount": 100,
    "specFileCount": 10_000,
    "inputBytes": 256 * 1024 * 1024,
    "statementCount": 100_000,
    "relationEdgeCount": 1_000_000,
    "traceEntryCount": 1_000_000,
    "commandDefinitionCount": 10_000,
    # `verifyBindingCount`は事前検査（カタログ全体のスナップショットの走査）では計数しない。1回の`verify`
    # の実行計画のテスト割当ての数だけに適用するため、`verify.py`が自分で数える（複合ワークスペース仕様 §10）。
    "verifyBindingCount": 10_000,
}

# 早期停止のときにどの次元を優先して報告するか（§10「複数の次元が同時に超過する場合は…」の
# 一般化。Step 5Aの範囲では`verifyBindingCount`を計算しないため対象外とする）。
_LIMIT_DIMENSION_ORDER = (
    "specFileCount",
    "inputBytes",
    "statementCount",
    "relationEdgeCount",
    "traceEntryCount",
    "commandDefinitionCount",
)


@dataclass
class MemberRecord:
    id: str
    path: str  # 複合ワークスペースのルートからの相対パス（"/"区切り、正規化済み）
    root: str  # 絶対パス
    config: dict


@dataclass
class PrecheckResult:
    discovery_failed: bool = False
    ok: bool = False
    root_id: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    git_status: str = "blocked"  # `doctor`の`checks[]`用（"passed"／"blocked"）
    catalog_status: str | None = None  # `doctor`の`checks[]`用（Noneならカタログの検査項目を出力しない）
    members: list[MemberRecord] = field(default_factory=list)
    #: 複合ワークスペースのルート（絶対パス）。Gitのリポジトリのルート、または入れ子の複合ワークスペースのルート（§2.1）。
    repo_root: str | None = None
    #: Gitでリポジトリの境界を確定できたか（``False``なら``SPEC-MULTI-GIT-001``か、それより前のルートの設定の停止）。
    git_confirmed: bool = False
    #: ルートの設定をYAMLとして読めた値（版の非対応で停止したときも含む）。読めなければ``None``。
    #: 単独操作の停止結果が、選択した設定のカタログへの登録を判定する（:func:`selected_is_registered`）ために使う。
    root_config: dict | None = None


def _diag(code: str, status: str, summary: str, source: dict, evidence: object = None) -> Diagnostic:
    return Diagnostic(code=code, severity="error", resultStatus=status, summary=summary, source=source, evidence=evidence)


def _root_source(root_id: str | None, key: str | None = None) -> dict:
    src: dict = {"kind": "file", "workspaceId": root_id, "path": ROOT_CONFIG_PATH}
    if key:
        src["key"] = key
    return src


@dataclass
class ScopeDecision:
    """探索の開始位置から決まる複合ワークスペースの範囲（複合ワークスペース仕様 §2.1）。"""

    #: ``outer``＝Gitのリポジトリのルート（除外した範囲の外、または除外を決めない）、
    #: ``nested``＝除外した範囲の中の入れ子の複合ワークスペース、``single``＝除外した範囲の中の単一ワークスペース。
    kind: str
    #: ``nested``のときだけ、入れ子の複合ワークスペースのルート（絶対パス）。
    root: str | None = None


def _config_file_in(directory: str) -> str | None:
    """``directory``の``.spec/bitz.yaml``のパス。なければ（``.spec``がシンボリックリンクのときも）``None``。"""

    candidate = os.path.join(directory, ".spec", "bitz.yaml")
    if os.path.isfile(candidate) and not os.path.islink(os.path.join(directory, ".spec")):
        return candidate
    return None


def resolve_scope(top: str, start: str) -> ScopeDecision:
    """探索の開始位置``start``が除外した範囲にあるとき、入れ子の複合ワークスペースか単一ワークスペースかを決める（§2.1、ADR-064の3・4）。

    ``top``はGitのリポジトリのルート（絶対パス）で、その``.spec/bitz.yaml``が存在する前提。除外を決めるのは、
    設定が読めて``multiWorkspace``を宣言し、除外が妥当なときだけである（読めない設定は単一の探索、版の非対応や
    除外の不正は外側の規則で停止するため、``outer``を返す）。入れ子の複合ワークスペースの中の除外にも同じ規則を再帰的に適用する。
    """

    top_real = os.path.realpath(top)
    start_real = os.path.realpath(start)
    rel = os.path.relpath(start_real, top_real)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return ScopeDecision("outer")
    segments = [] if rel == "." else rel.split(os.sep)
    nfc_segments = tuple(unicodedata.normalize("NFC", seg) for seg in segments)

    root = os.path.abspath(top)
    depth = 0  # ``root``の、``segments``の中での深さ（外側のルートは0）
    nested = False
    while True:
        cfg = _config_file_in(root)
        if cfg is None:
            break
        outcome = config_mod.read_config(cfg)
        if outcome.config is None or "multiWorkspace" not in outcome.config:
            break
        excludes = valid_exclude_parts(outcome.config)
        if not excludes:
            break
        relative = nfc_segments[depth:]
        matched = next((e for e in excludes if _is_prefix_or_equal(e, relative)), None)
        if matched is None:
            break
        # 除外のディレクトリ自身から開始位置までの経路の上の設定を、浅い方から見る。
        path_dirs = [
            (depth + k, os.path.join(root, *segments[depth : depth + k]))
            for k in range(len(matched), len(relative) + 1)
        ]
        with_config = [(d, dirpath) for d, dirpath in path_dirs if _config_file_in(dirpath) is not None]
        if not with_config:
            break  # 経路の上に設定がなければ、外側の規則のまま（3.）
        declaring = next(
            (
                (d, dirpath)
                for d, dirpath in with_config
                if _declares_multiworkspace(config_mod.read_config(_config_file_in(dirpath)))  # type: ignore[arg-type]
            ),
            None,
        )
        if declaring is None:
            return ScopeDecision("single")  # 開始位置に最も近い設定を単一ワークスペースとして使う（2.）
        depth, root = declaring
        nested = True
    return ScopeDecision("nested", root) if nested else ScopeDecision("outer")


def _locate_root(
    cwd: str, git: gitutil.GitInfo, env: dict[str, str], nearest_config_path: str | None = None
) -> tuple[str | None, str | None, bool, str | None]:
    """複合ワークスペースの全体操作の候補のルート（絶対パス）と`.spec/bitz.yaml`を発見する（複合ワークスペース仕様 §8）。

    戻り値は``(repo_root, config_path, git_boundary_confirmed, git_top)``。候補を発見できなければ
    ``(None, None, False, None)``（呼び出し側は引数不正・終了コード4）。``git_top``はGitのリポジトリのルート（絶対パス）で、
    Gitの境界を確定できたときだけ返す。以降のGitの列挙で、ルートを求める呼び出しを繰り返さないために使う。

    ``nearest_config_path``は、Gitでリポジトリのルートを確定できないときだけ使う候補で、単独操作が通常の探索
    （:func:`bitz.workspace.locate_workspace`）で見つけた最も近い設定の絶対パス。``None``（全体操作）なら現在のディレクトリ自身だけを見る。
    """

    if git.available and git.executable:
        top = gitutil.show_toplevel(git.executable, cwd, env)
        if top:
            root = os.path.abspath(top)
            cfg = os.path.join(root, ".spec", "bitz.yaml")
            if os.path.isfile(cfg) and not os.path.islink(os.path.join(root, ".spec")):
                scope = resolve_scope(root, cwd)
                if scope.kind == "single":
                    # 除外した範囲の中の単一ワークスペース: 複合ワークスペースを発見できない（§2.1の2.）。
                    return None, None, False, None
                if scope.kind == "nested":
                    assert scope.root is not None
                    return scope.root, os.path.join(scope.root, ".spec", "bitz.yaml"), True, root
                return root, cfg, True, root
            return None, None, False, None

    # Gitがない、またはGitの最上位のディレクトリを解決できない場合のフォールバック: 現在のディレクトリ自身を候補にする
    # （メンバー配下からの広域の探索はGitに依存するため提供できないが、現在のディレクトリ自身に候補があれば
    # `SPEC-MULTI-GIT-001`／`blocked`として境界を確定できないことを報告できる。複合ワークスペース仕様 §10）。
    # 単独操作は、最も近い設定のディレクトリを候補にする（ルートの下のサブディレクトリからでも止まる。複合ワークスペース仕様 §3）。
    if nearest_config_path is not None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(nearest_config_path)))
    else:
        root = os.path.abspath(cwd)
    cfg = os.path.join(root, ".spec", "bitz.yaml")
    if os.path.isfile(cfg) and not os.path.islink(os.path.join(root, ".spec")):
        return root, cfg, False, None
    return None, None, False, None


def _path_lexically_valid(path: str) -> bool:
    if not isinstance(path, str) or path == "" or path == ".":
        return False
    if os.path.isabs(path) or path.startswith("/"):
        return False
    if "\x00" in path:
        return False
    segments = path.split("/")
    for seg in segments:
        if seg in ("", ".", ".."):
            return False
        if any(ch in seg for ch in "*?[]"):
            return False
    return True


def _is_ancestor(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    return len(a) < len(b) and b[: len(a)] == a


# --- 除外（`multiWorkspace.exclude`。ADR-064、複合ワークスペース仕様 §2・§2.1） ---------------------------------

#: 除外の最大件数（ワークスペース・設定仕様 §5）。
EXCLUDE_LIMIT = 100


def _nfc_parts(path: str) -> tuple[str, ...]:
    """パスをUnicode NFCへ正規化し、セグメントへ分ける（大文字と小文字は区別する。複合ワークスペース仕様 §2.1）。"""

    return tuple(unicodedata.normalize("NFC", seg) for seg in path.split("/"))


def _is_prefix_or_equal(prefix: tuple[str, ...], parts: tuple[str, ...]) -> bool:
    """``prefix``が``parts``と同じ、またはその祖先か（ディレクトリの単位の前方一致）。"""

    return parts[: len(prefix)] == prefix


def _in_excluded_area(parts: tuple[str, ...], exclude_parts: list[tuple[str, ...]]) -> bool:
    """``parts``のディレクトリが、いずれかの除外のディレクトリと同じかその配下にあるか。"""

    return any(_is_prefix_or_equal(e, parts) for e in exclude_parts)


def _exclude_shape_diag(mw: dict, root_id: str | None) -> Diagnostic | None:
    """``exclude``の型（文字列の配列）と件数（0〜100）を検査する。キーがなければ``None``（既定は空）。"""

    if "exclude" not in mw:
        return None
    raw = mw["exclude"]
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_EXCLUDE_TYPE,
            _root_source(root_id, "multiWorkspace.exclude"),
        )
    if len(raw) > EXCLUDE_LIMIT:
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_EXCLUDE_COUNT,
            _root_source(root_id, "multiWorkspace.exclude"),
        )
    return None


def _evaluate_excludes(root_id: str | None, raw: list[str]) -> tuple[list[Diagnostic], list[tuple[str, ...]]]:
    """型と件数が妥当な``exclude``の要素を検査する。``(診断, 字句が妥当な除外のNFCのセグメント)``を返す。

    要素ごとの原因（形式の不正、`.spec`を含む）は要素につき1件、2つの要素の間の原因（重複、入れ子）は組につき1件にする
    （メンバーのパスの検査と同じ作り方。診断レジストリ §2）。
    """

    source = _root_source(root_id, "multiWorkspace.exclude")
    diags: list[Diagnostic] = []
    clean: list[tuple[int, tuple[str, ...]]] = []
    valid_parts: list[tuple[str, ...]] = []
    for index, path in enumerate(raw):
        if not _path_lexically_valid(path):
            diags.append(_diag("SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_EXCLUDE_INVALID, source))
            continue
        parts = _nfc_parts(path)
        valid_parts.append(parts)
        if ".spec" in parts:
            diags.append(_diag("SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_EXCLUDE_SPEC, source))
            continue
        clean.append((index, parts))

    consumed: set[int] = set()
    for pos_i, (i, a) in enumerate(clean):
        if i in consumed:
            continue
        for j, b in clean[pos_i + 1 :]:
            if j in consumed:
                continue
            if a == b:
                message = messages.MULTI_EXCLUDE_DUPLICATE
            elif _is_ancestor(a, b) or _is_ancestor(b, a):
                message = messages.MULTI_EXCLUDE_NESTED
            else:
                continue
            diags.append(_diag("SPEC-MULTI-CONFIG-001", "failed", message, source))
            consumed.update((i, j))
            break
    return diags, valid_parts


def _member_paths_overlapping(members_raw: object, exclude_parts: list[tuple[str, ...]]) -> bool:
    """字句が妥当なメンバーのパスのうち、除外と同じまたは除外の配下にあるものがあるか（メンバーの配下の除外は重ならない）。"""

    if not isinstance(members_raw, list):
        return False
    for raw in members_raw:
        path = raw.get("path") if isinstance(raw, dict) else None
        if isinstance(path, str) and _path_lexically_valid(path) and _in_excluded_area(_nfc_parts(path), exclude_parts):
            return True
    return False


def valid_exclude_parts(root_config: dict) -> list[tuple[str, ...]] | None:
    """ルートの設定の``multiWorkspace.exclude``を信用できるなら、そのNFCのセグメントの一覧を返す。信用できなければ``None``。

    信用できるのは、``multiWorkspace``が設定不適合（``SPEC-MULTI-CONFIG-001``。members の不在・型・件数、maxMembers、
    exclude の型・件数・字句・重複・入れ子・`.spec`を含む）を持たず、メンバーのパスと重ならないときだけである
    （複合ワークスペース仕様 §2・§2.1、ADR-064の3）。members が不在または配列でなければ、重なりを判定できないため信用しない。
    メンバーのパスの字句の不正など``SPEC-MULTI-PATH-001``は、ほかの不備として除外の信用に影響しない。
    除外がなければ空の一覧を返す。
    """

    mw = root_config.get("multiWorkspace")
    if not isinstance(mw, dict) or "exclude" not in mw:
        return []
    shape_diag, _members = _validate_multiworkspace_shape(root_config, None)
    if shape_diag is not None:
        return None
    diags, parts = _evaluate_excludes(None, mw["exclude"])
    if diags or _member_paths_overlapping(mw.get("members"), parts):
        return None
    return parts


def _validate_multiworkspace_shape(root_config: dict, root_id: str | None) -> tuple[Diagnostic | None, list[tuple[str, str]] | None]:
    mw = root_config.get("multiWorkspace")
    if mw is None:
        return None, []
    if not isinstance(mw, dict):
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_NOT_MAP,
            _root_source(root_id, "multiWorkspace"),
        ), None

    max_members = mw.get("maxMembers", 20)
    if not isinstance(max_members, int) or isinstance(max_members, bool) or not (1 <= max_members <= 100):
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MAX_MEMBERS_RANGE,
            _root_source(root_id, "multiWorkspace.maxMembers"),
        ), None

    members_raw = mw.get("members", [])
    if not isinstance(members_raw, list):
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MEMBERS_TYPE,
            _root_source(root_id, "multiWorkspace.members"),
        ), None
    if len(members_raw) == 0:
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MEMBERS_REQUIRED,
            _root_source(root_id, "multiWorkspace.members"),
        ), None

    members: list[tuple[str, str]] = []
    for raw in members_raw:
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("id"), str)
            or not isinstance(raw.get("path"), str)
        ):
            return _diag(
                "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MEMBER_ENTRY_TYPE,
                _root_source(root_id, "multiWorkspace.members"),
            ), None
        members.append((raw["id"], raw["path"]))

    shape_diag = _exclude_shape_diag(mw, root_id)
    if shape_diag is not None:
        return shape_diag, None
    return None, members


def _member_config_check(
    root_id: str, root: str, mid: str, mpath: str, *, check_id_match: bool = True
) -> tuple[Diagnostic | None, dict | None]:
    """メンバー自身の`.spec/bitz.yaml`を検証する（MEMBER段階、910）。``mpath``は字句として有効な前提。

    ``check_id_match``は呼び出し側が``mid``自体の構文をすでに不正と判定済みのとき``False``にする
    （カタログのid形式の不正はID段階、920が単独の主診断になれるよう、無意味な不一致の比較を
    しない。`priority`どおりMEMBER(910)をID(920)より優先するのは、両者が独立に成立する場合だけに限る）。
    """

    member_root = os.path.join(root, *mpath.split("/"))
    member_cfg = os.path.join(member_root, ".spec", "bitz.yaml")
    if not os.path.isfile(member_cfg) or os.path.islink(os.path.join(member_root, ".spec")):
        return _diag(
            "SPEC-MULTI-MEMBER-001", "failed", messages.MEMBER_CONFIG_MISSING,
            _root_source(root_id, "multiWorkspace.members"),
        ), None

    m_outcome = config_mod.read_config(member_cfg)
    if m_outcome.stop:
        if m_outcome.stop_stage in ("schema-major", "ears-major"):
            code = "SPEC-MULTI-VERSION-001"
            msg = (
                messages.MULTI_VERSION_SCHEMA_MAJOR
                if m_outcome.stop_stage == "schema-major"
                else messages.MULTI_VERSION_EARS_MAJOR
            )
            return _diag(code, "blocked", msg, _root_source(root_id, "multiWorkspace.members")), None
        # 一般的な設定の不適合（YAML構文・型・必須のフィールド・I/O）はメンバー自身の診断をそのまま返す。
        all_diags = m_outcome.diagnostics + m_outcome.warnings
        return (all_diags[0] if all_diags else _diag(
            "SPEC-CONFIG-SCHEMA-001", "error", "メンバーの設定が不正です", _root_source(root_id, "multiWorkspace.members")
        )), None

    assert m_outcome.config is not None
    if check_id_match and m_outcome.workspace_id != mid:
        return _diag(
            "SPEC-MULTI-MEMBER-001", "failed", messages.MEMBER_ID_MISMATCH,
            _root_source(root_id, "multiWorkspace.members"),
        ), None
    if m_outcome.config.get("multiWorkspace") is not None:
        return _diag(
            "SPEC-MULTI-MEMBER-001", "failed", messages.MEMBER_NESTED_MULTIWORKSPACE,
            _root_source(root_id, "multiWorkspace.members"),
        ), None
    return None, m_outcome.config


@dataclass
class _LocalMember:
    id: str
    path: str
    parts: tuple[str, ...]
    config: dict


def _evaluate_member_local(
    root: str, root_id: str, mid: str, mpath: str, exclude_parts: list[tuple[str, ...]] | None = None
) -> tuple[Diagnostic | None, _LocalMember | None]:
    """1つのメンバーについて、他のメンバーとの比較を伴わない候補を集め、最小の`priority`の1件を選ぶ。

    同じメンバーに複数の条件が成立しても、返す診断は1件だけにする
    （診断レジストリ §2「1つの元の原因から、同義の診断を複数生成しない」の運用として、
    「1つのメンバー」を単位に適用する）。
    """

    candidates: list[Diagnostic] = []

    id_valid = isinstance(mid, str) and bool(lex.WORKSPACE_ID_RE.match(mid))
    if not id_valid:
        candidates.append(_diag(
            "SPEC-MULTI-ID-001", "failed", messages.MULTI_ID_INVALID,
            _root_source(root_id, "multiWorkspace.members"),
        ))
    elif mid == root_id:
        candidates.append(_diag(
            "SPEC-MULTI-ID-001", "failed", messages.MULTI_ID_DUPLICATE,
            _root_source(root_id, "multiWorkspace.members"),
        ))

    path_valid = _path_lexically_valid(mpath)
    parts = tuple(mpath.split("/")) if path_valid else ()
    if not path_valid:
        candidates.append(_diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_INVALID,
            _root_source(root_id, "multiWorkspace.members"),
        ))

    if path_valid and exclude_parts and _in_excluded_area(_nfc_parts(mpath), exclude_parts):
        candidates.append(_diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_EXCLUDED,
            _root_source(root_id, "multiWorkspace.members"),
        ))

    config: dict | None = None
    if path_valid:
        d, config = _member_config_check(root_id, root, mid, mpath, check_id_match=id_valid)
        if d is not None:
            candidates.append(d)

    if candidates:
        candidates.sort(key=lambda d: _PRIORITY.get(d.code, 0))
        return candidates[0], None

    assert config is not None
    return None, _LocalMember(id=mid, path=mpath, parts=parts, config=config)


def _deep_path_check(
    root: str,
    root_id: str,
    rec: _LocalMember,
    submodule_paths: set[str],
    worktree_paths: set[str],
) -> Diagnostic | None:
    """上位のディレクトリにあるシンボリックリンク・サブモジュール・別のワークツリー・別のリポジトリを検証する（PATH段階、930・Git依存）。"""

    if rec.path in submodule_paths:
        return _diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_SUBMODULE,
            _root_source(root_id, "multiWorkspace.members"),
        )
    member_root = os.path.join(root, *rec.parts)
    if os.path.abspath(member_root) in worktree_paths:
        return _diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_WORKTREE,
            _root_source(root_id, "multiWorkspace.members"),
        )
    cur = root
    for seg in rec.parts:
        cur = os.path.join(cur, seg)
        if os.path.islink(cur):
            return _diag(
                "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_SYMLINK,
                _root_source(root_id, "multiWorkspace.members"),
            )
    if os.path.isdir(os.path.join(member_root, ".git")):
        return _diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_SEPARATE_REPO,
            _root_source(root_id, "multiWorkspace.members"),
        )
    return None


def _validate_catalog(
    root: str,
    root_id: str,
    root_config: dict,
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    extra_config_revs: list[str],
    *,
    skip_limit_dimensions: frozenset[str] = frozenset(),
    compare_git_configs: bool = True,
    selected_dir: str | None = None,
    git_top: str | None = None,
) -> tuple[list[Diagnostic], list[MemberRecord] | None]:
    """カタログ・ID・パス・バージョン・未登録の設定を検証する（優先順位900〜960。`GIT`は呼び出し側で解決済み）。

    独立した元の原因はそれぞれ1件の診断を持つ（診断レジストリ §2）。同じメンバーに
    複数の条件が成立する場合や、2つのメンバーの間の同一の元の原因（重複ID・重複／入れ子のパス）は1件に絞る。
    カタログ自体が構成できない場合（`multiWorkspace`の形状不正）だけ、単独の打ち切りとして
    1件の診断を返す。問題がなければ ``([], member_records)`` を返す。

    未登録の設定の照合（UNREGISTERED段階）は、``compare_git_configs``が真ならGitが認識する設定の列挙と比較し
    （全体操作と単独の`doctor`）、``selected_dir``があれば単独操作が選んだ最も近い設定のディレクトリがルートか
    カタログのメンバーのルートかを照合する（複合ワークスペース仕様 §3の4・§7）。両方が同じパスを見つけたときはGit側の1件にする。
    """

    shape_diag, members_raw = _validate_multiworkspace_shape(root_config, root_id)
    if shape_diag is not None:
        return [shape_diag], None
    assert members_raw is not None

    # --- PASS A: メンバーごとの独立検証（IDの構文・パスの字句・メンバーの設定） -----------------
    mw = root_config.get("multiWorkspace") or {}
    exclude_diags, exclude_parts = _evaluate_excludes(root_id, mw.get("exclude", []))

    local_diags: list[Diagnostic] = []
    locals_: list[_LocalMember | None] = []
    for mid, mpath in members_raw:
        d, rec = _evaluate_member_local(root, root_id, mid, mpath, exclude_parts)
        if d is not None:
            local_diags.append(d)
        locals_.append(rec)

    clean_indices = [i for i, rec in enumerate(locals_) if rec is not None]

    # --- PASS B: 2つのメンバーの間の組ごとの元の原因（重複ID・重複／入れ子のパス）を1件ずつに絞る -------
    consumed: set[int] = set()
    pairwise_diags: list[Diagnostic] = []
    for pos_i in range(len(clean_indices)):
        i = clean_indices[pos_i]
        if i in consumed:
            continue
        a = locals_[i]
        assert a is not None
        for pos_j in range(pos_i + 1, len(clean_indices)):
            j = clean_indices[pos_j]
            if j in consumed:
                continue
            b = locals_[j]
            assert b is not None
            if a.id == b.id:
                pairwise_diags.append(_diag(
                    "SPEC-MULTI-ID-001", "failed", messages.MULTI_ID_DUPLICATE,
                    _root_source(root_id, "multiWorkspace.members"),
                ))
                consumed.add(i)
                consumed.add(j)
                break
            if a.parts == b.parts:
                pairwise_diags.append(_diag(
                    "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_DUPLICATE,
                    _root_source(root_id, "multiWorkspace.members"),
                ))
                consumed.add(i)
                consumed.add(j)
                break
            if _is_ancestor(a.parts, b.parts) or _is_ancestor(b.parts, a.parts):
                pairwise_diags.append(_diag(
                    "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_NESTED,
                    _root_source(root_id, "multiWorkspace.members"),
                ))
                consumed.add(i)
                consumed.add(j)
                break

    # --- PASS C: 残ったメンバーだけGit依存の深い判定（シンボリックリンク／サブモジュール／ワークツリー／別のリポジトリ） ---
    deep_diags: list[Diagnostic] = []
    members: list[MemberRecord] = []
    remaining = [i for i in clean_indices if i not in consumed]
    if git.available and git.executable:
        submodule_paths = gitutil.list_submodule_paths(git.executable, cwd, env, root, git_top)
        worktree_paths = gitutil.list_worktree_paths(git.executable, cwd, env)
        for i in remaining:
            rec = locals_[i]
            assert rec is not None
            d = _deep_path_check(root, root_id, rec, submodule_paths, worktree_paths)
            if d is not None:
                deep_diags.append(d)
            else:
                members.append(MemberRecord(
                    id=rec.id, path=rec.path, root=os.path.join(root, *rec.parts), config=rec.config
                ))
    else:
        for i in remaining:
            rec = locals_[i]
            assert rec is not None
            members.append(MemberRecord(
                id=rec.id, path=rec.path, root=os.path.join(root, *rec.parts), config=rec.config
            ))

    all_diags = local_diags + exclude_diags + pairwise_diags + deep_diags
    if all_diags:
        return all_diags, None

    # --- UNREGISTERED段階（960） --------------------------------------------------
    # 各スナップショットは自身のカタログとだけ比較する（複合ワークスペース仕様 §8「各スナップショット自身のルートの
    # 設定が`multiWorkspace`を宣言する場合だけ、そのスナップショット自身のカタログとの差分を検査する」）。基準版の
    # スナップショットが現在版と異なるメンバー構成（例: メンバーのパスのリネーム）を持つ場合、基準版の
    # スナップショットの既知の設定は基準版自身のカタログへ照合し、現在版側の既知の設定は現在版のカタログへ照合する
    # （どちらか一方の集合だけで比較すると、IDを保ったメンバーの移動を誤って未登録にする）。
    unregistered: dict[str, str] = {}  # パス -> summary
    if selected_dir is not None:
        selected_real = os.path.realpath(selected_dir)
        registered_real = {os.path.realpath(root)} | {os.path.realpath(rec.root) for rec in members}
        if selected_real not in registered_real:
            rel_dir = os.path.relpath(selected_real, os.path.realpath(root)).replace(os.sep, "/")
            # 除外した範囲の中の設定は照合の対象にしない（§2.1。通常は除外した範囲の操作はここへ来ない）。
            if not _in_excluded_area(_nfc_parts(rel_dir), exclude_parts):
                unregistered[f"{rel_dir}/.spec/bitz.yaml"] = messages.MULTI_UNREGISTERED_SELECTED
    if compare_git_configs and git.available and git.executable:
        catalog_paths = {".spec/bitz.yaml"} | {f"{rec.path}/.spec/bitz.yaml" for rec in members}
        extra_set: set[str] = set()
        for rev in extra_config_revs:
            # 基準版のルートの設定は1回だけ読み、カタログの対応表と除外の両方を求める。
            rev_config = _read_base_root_config(git, cwd, env, rev, root, git_top)
            rev_map = _workspace_map(rev_config) if rev_config is not None else {}
            if not rev_map:
                # このリビジョンは`multiWorkspace`を宣言していない（単一ワークスペースから複合ワークスペース化する前の
                # スナップショット）。リポジトリ全体の不存在保証をさかのぼって適用しない（複合ワークスペース仕様 §8）。
                continue
            rev_catalog_paths = {
                ".spec/bitz.yaml" if p == "." else f"{p}/.spec/bitz.yaml" for p in rev_map.values()
            }
            # 各スナップショットは、そのスナップショット自身のルートの設定の除外を使う（§2.1）。
            rev_exclude = (valid_exclude_parts(rev_config) if rev_config is not None else None) or []
            rev_known = {
                p for p in gitutil.list_tree_config_paths(git.executable, cwd, env, rev, root, git_top)
                if not _config_in_excluded_area(p, rev_exclude)
            }
            extra_set |= rev_known - rev_catalog_paths
        current_known = {
            p for p in gitutil.list_working_config_paths(git.executable, cwd, env, root, git_top)
            if not _config_in_excluded_area(p, exclude_parts)
        }
        extra_set |= current_known - catalog_paths
        for p in extra_set:
            unregistered[p] = messages.MULTI_UNREGISTERED
    if unregistered:
        return [
            _diag(
                "SPEC-MULTI-UNREGISTERED-001", "blocked", unregistered[p],
                {"kind": "file", "workspaceId": None, "path": p},
            )
            for p in sorted(unregistered)
        ], None

    # --- LIMIT段階（970） -------------------------------------------------------
    # 上限の超過は複合ワークスペース全体を停止する単一の元の原因であり、複合ワークスペース仕様 §10のとおり
    # 最初に検出した次元で早期停止する（複数のメンバーに個別の独立した元の原因とは扱いが異なる）。
    limit_diag = _check_resource_limits(root, root_id, root_config, members, skip_dimensions=skip_limit_dimensions)
    if limit_diag is not None:
        return [limit_diag], None

    return [], members


def _config_in_excluded_area(config_path: str, exclude_parts: list[tuple[str, ...]]) -> bool:
    """``<dir>/.spec/bitz.yaml``の``<dir>``が除外した範囲にあるか。``config_path``は複合ワークスペースのルートからの相対。"""

    parts = _nfc_parts(config_path)[:-2]
    return bool(parts) and _in_excluded_area(parts, exclude_parts)


def _iter_spec_md_files(workspace_root: str):
    spec_dir = os.path.join(workspace_root, ".spec")
    for kind_dir in _SPEC_KIND_DIRS:
        base = os.path.join(spec_dir, kind_dir)
        if os.path.islink(base) or not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                if os.path.islink(full):
                    continue
                if name.endswith(".md"):
                    yield full


def _extract_frontmatter_dict(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    closing = text.find("\n---\n", 4)
    if closing < 0 and text.endswith("\n---"):
        closing = len(text) - 4
    if closing < 0:
        return {}
    try:
        value = parse_yaml_subset(text[4:closing])
    except (YamlSyntaxError, YamlForbiddenError):
        return {}
    return value if isinstance(value, dict) else {}


def _scan_document_counts(text: str) -> tuple[int, int, int]:
    """``(statementCount, relationEdgeCount, traceEntryCount)``をこの1文書分だけ返す。

    本文全体を保持せず、この関数の呼出しが終われば``text``は解放できる（複合ワークスペース仕様
    §10.1「全ファイルの本文を索引として同時に保持しない」）。
    """

    candidates = scan_candidates(text)
    fm = _extract_frontmatter_dict(text)

    rel_count = 0
    relations = fm.get("relations")
    if isinstance(relations, dict):
        for v in relations.values():
            if isinstance(v, list):
                rel_count += len(v)

    trace_count = 0
    implements = fm.get("implements")
    if isinstance(implements, list):
        trace_count += len(implements)
    tests = fm.get("tests")
    if isinstance(tests, list):
        for t in tests:
            trace_count += 1
            if isinstance(t, dict) and isinstance(t.get("covers"), list):
                trace_count += len(t["covers"])
    changes = fm.get("changes")
    if isinstance(changes, list):
        trace_count += len(changes)

    return len(candidates), rel_count, trace_count


def _first_exceeded(totals: dict[str, int], skip_dimensions: frozenset[str] = frozenset()) -> str | None:
    for dim in _LIMIT_DIMENSION_ORDER:
        if dim in skip_dimensions:
            continue
        if totals[dim] > HARD_LIMITS[dim]:
            return dim
    return None


def _limit_diag(root_id: str, dimension: str, limit: int, observed: int) -> Diagnostic:
    return _diag(
        "SPEC-MULTI-LIMIT-001", "blocked", messages.multi_limit_exceeded(dimension, limit),
        _root_source(root_id),
        evidence={"dimension": dimension, "limit": limit, "observedAtLeast": observed},
    )


def _check_resource_limits(
    root: str,
    root_id: str,
    root_config: dict,
    members: list[MemberRecord],
    *,
    skip_dimensions: frozenset[str] = frozenset(),
) -> Diagnostic | None:
    # `memberCount`は`multiWorkspace.maxMembers`（既定20、範囲1〜100）の実効上限で判定し、Coreの絶対上限
    # 100を超えない（複合ワークスペース仕様 §2・§10）。値域は_validate_catalogで検査済み。
    member_count = len(members)
    max_members = (root_config.get("multiWorkspace") or {}).get("maxMembers", 20)
    member_limit = min(max_members, HARD_LIMITS["memberCount"])
    if member_count > member_limit:
        return _limit_diag(root_id, "memberCount", member_limit, member_count)

    totals = {k: 0 for k in _LIMIT_DIMENSION_ORDER}

    workspaces = [(root, root_config)] + [(rec.root, rec.config) for rec in members]
    for wroot, wconfig in workspaces:
        cfg_path = os.path.join(wroot, ".spec", "bitz.yaml")
        try:
            totals["inputBytes"] += os.path.getsize(cfg_path)
        except OSError:
            pass
        commands = ((wconfig.get("verify") or {}) if isinstance(wconfig.get("verify"), dict) else {}).get("commands")
        if isinstance(commands, dict):
            totals["commandDefinitionCount"] += len(commands)

        dim = _first_exceeded(totals, skip_dimensions)
        if dim:
            return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])

        for md_path in _iter_spec_md_files(wroot):
            try:
                size = os.path.getsize(md_path)
            except OSError:
                continue
            totals["specFileCount"] += 1
            totals["inputBytes"] += size
            dim = _first_exceeded(totals, skip_dimensions)
            if dim:
                return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])

            try:
                with open(md_path, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            del raw
            stmt_count, rel_count, trace_count = _scan_document_counts(text)
            del text
            totals["statementCount"] += stmt_count
            totals["relationEdgeCount"] += rel_count
            totals["traceEntryCount"] += trace_count
            dim = _first_exceeded(totals, skip_dimensions)
            if dim:
                return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])

    dim = _first_exceeded(totals, skip_dimensions)
    if dim:
        return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])
    return None


def ordered_workspaces(pre: "PrecheckResult") -> list[tuple[str, str, str]]:
    """``(workspace_id, root_abs, 複合ワークスペースのルートからの相対パス)``をルートを先頭に、以降はIDの辞書順で返す(§8)。"""

    out: list[tuple[str, str, str]] = [(pre.root_id, pre.repo_root, ".")]
    for m in sorted(pre.members, key=lambda r: r.id):
        out.append((m.id, m.root, m.path))
    return out


def _declares_multiworkspace(outcome: config_mod.ConfigOutcome) -> bool:
    """設定の読込みの結果が複合ワークスペース（`multiWorkspace`キー）を宣言しているかを返す。

    設定が読めれば`multiWorkspace`の有無で判定する。スキーマまたはEARS-AIのメジャーバージョンが非対応で
    停止したときは、YAMLとして読めた値の`multiWorkspace`の有無で判定する。構文、型、必須フィールド、I/O、上限による
    停止（``stop_stage``が``"config"``）では複合ワークスペースと判定しない（複合ワークスペース仕様 §3、ADR-063）。
    """

    if outcome.config is not None:
        return "multiWorkspace" in outcome.config
    if outcome.stop_stage in ("schema-major", "ears-major") and outcome.parsed is not None:
        return "multiWorkspace" in outcome.parsed
    return False


def is_declared(
    cwd: str, git: gitutil.GitInfo, env: dict[str, str], nearest_config_path: str | None = None
) -> bool:
    """単独操作が複合ワークスペースを宣言しているリポジトリで動いているかを返す。

    Gitでリポジトリのルートを確定できるときは、ルートの`.spec/bitz.yaml`で判定する。確定できないとき
    （Gitがない、Gitのリポジトリでない）は、通常の探索で見つけた最も近い設定（``nearest_config_path``）で判定する。
    判定の規則は :func:`_declares_multiworkspace` のとおり。

    単独操作が非修飾の対象を受けた場合でも、メンバーを含むカタログを使う必要がある。
    一方、単一ワークスペースで :func:`precheck` を実行すると``multiWorkspace``の不在を設定不適合として
    扱うため、呼び出し側はこの軽量な判定を先に使う。
    """

    _root, config_path, _git_confirmed, _top = _locate_root(cwd, git, env, nearest_config_path)
    if config_path is None:
        return False
    return _declares_multiworkspace(config_mod.read_config(config_path))


def selected_is_registered(pre: "PrecheckResult", selected_rel: str) -> bool:
    """単独操作が選んだ最も近い設定が、カタログに登録されているかを返す（複合ワークスペース仕様 §3、ADR-063）。

    ``selected_rel``は選択した設定のディレクトリのリポジトリのルートからの相対パス（ルートは``.``）。
    ルート、またはルートの設定の`multiWorkspace.members`に載るメンバーのパスは登録済みとする。
    カタログの形が不正で構成できないとき（:func:`_validate_multiworkspace_shape`が診断を返すとき）は、ルートだけを登録済みとみなす。
    """

    if selected_rel == ".":
        return True
    if pre.root_config is None:
        return False
    shape_diag, members_raw = _validate_multiworkspace_shape(pre.root_config, None)
    if shape_diag is not None or members_raw is None:
        return False
    return any(path == selected_rel for _mid, path in members_raw)


def catalog_member_id(pre: "PrecheckResult", selected_rel: str) -> str | None:
    """``selected_rel``のメンバーのカタログのIDを返す。ルート、未登録、カタログの形が不正なときは``None``。"""

    if selected_rel == "." or pre.root_config is None:
        return None
    shape_diag, members_raw = _validate_multiworkspace_shape(pre.root_config, None)
    if shape_diag is not None or members_raw is None:
        return None
    return next((mid for mid, path in members_raw if path == selected_rel), None)


def _read_base_root_config(
    git: gitutil.GitInfo, cwd: str, env: dict[str, str], base_rev: str | None, repo_root: str,
    git_top: str | None = None,
) -> dict | None:
    """``base_rev``の時点の複合ワークスペースのルート（``repo_root``。入れ子では入れ子のルート）の``.spec/bitz.yaml``をYAMLとして読む。

    読めなければ``None``。``ROOT_CONFIG_PATH``は``repo_root``からの相対で、入れ子の複合ワークスペースでは
    基準版でも同じディレクトリの設定を読む（§2.1）。
    """

    if base_rev is None or not git.available or git.executable is None:
        return None
    raw = gitutil.show_base_file(git.executable, cwd, env, base_rev, repo_root, ROOT_CONFIG_PATH, git_top)
    if raw is None:
        return None
    try:
        text = raw.decode("utf-8")
        value = parse_yaml_subset(text)
    except (UnicodeDecodeError, YamlSyntaxError, YamlForbiddenError):
        return None
    return value if isinstance(value, dict) else None


def base_exclude_parts(
    git: gitutil.GitInfo, cwd: str, env: dict[str, str], base_rev: str | None, repo_root: str
) -> list[tuple[str, ...]]:
    """``base_rev``のスナップショット自身のルートの設定の除外を返す。読めない、または妥当でない除外は何も除外しない（空）。"""

    value = _read_base_root_config(git, cwd, env, base_rev, repo_root)
    if value is None:
        return []
    return valid_exclude_parts(value) or []


def base_workspace_map(
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    base_rev: str | None,
    repo_root: str,
    *,
    current_root_id: str | None = None,
) -> dict[str, str]:
    """``base_rev``の時点のルート／メンバーのカタログを``{workspace_id: リポジトリのルートからの相対パス}``で返す。

    ルートワークスペースのIDは基準版のフロントマターの``workspace.id``をそのまま使う。基準版のルートの設定が
    ``multiWorkspace``を宣言していない場合は、``current_root_id``が与えられ、かつ基準版が
    ``workspace.id``を省略しているときに限り、単一ワークスペースから初めて複合ワークスペース化するGitの比較の
    写像（複合ワークスペース仕様 §4.1後段）として、基準版の実効ID`root`を``current_root_id``へ
    一方向に写像した``{current_root_id: "."}``を返す（状態遷移・削除の検出・承認済み要求の保護の
    基準版／現在版の対応にだけ使う）。``current_root_id``を渡さない呼出し（全体事前検査のGitの既知の設定の
    比較。複合ワークスペース仕様 §8「初めて複合ワークスペース化する前の単一ワークスペースのスナップショットへ、
    リポジトリ全体の不存在保証をさかのぼって適用しない」）では、この写像を行わず、引き続き空の``dict``を返す。
    """

    value = _read_base_root_config(git, cwd, env, base_rev, repo_root)
    if value is None:
        return {}
    return _workspace_map(value, current_root_id)


def _workspace_map(value: dict, current_root_id: str | None = None) -> dict[str, str]:
    """基準版のルートの設定（YAMLとして読めた値）から :func:`base_workspace_map` の対応表を求める。"""

    mw = value.get("multiWorkspace")
    if not isinstance(mw, dict):
        if current_root_id is not None:
            ws_block = value.get("workspace")
            has_explicit_id = isinstance(ws_block, dict) and isinstance(ws_block.get("id"), str)
            if not has_explicit_id:
                return {current_root_id: "."}
        return {}
    members_raw = mw.get("members")
    if not isinstance(members_raw, list):
        return {}
    ws_block = value.get("workspace")
    root_id = ws_block.get("id") if isinstance(ws_block, dict) and isinstance(ws_block.get("id"), str) else "root"
    result: dict[str, str] = {root_id: "."}
    for raw_member in members_raw:
        if (
            isinstance(raw_member, dict)
            and isinstance(raw_member.get("id"), str)
            and isinstance(raw_member.get("path"), str)
        ):
            result[raw_member["id"]] = raw_member["path"]
    return result


def precheck(
    cwd: str,
    git: gitutil.GitInfo,
    env: dict[str, str],
    *,
    extra_config_revs: list[str] | None = None,
    skip_limit_dimensions: frozenset[str] = frozenset(),
    ears_version_code: str = "SPEC-EARS-VERSION-001",
    nearest_config_path: str | None = None,
    selected_dir: str | None = None,
    compare_git_configs: bool = True,
    report_git_with_config_stop: bool = False,
) -> PrecheckResult:
    """`--all-workspaces`の全体事前検査（複合ワークスペース仕様 §8）。

    ``extra_config_revs``は、現在のスナップショットに加えてGitの既知の設定を比較するリビジョンの一覧
    （`check`の`--base`、`doctor`の`HEAD`など。§8「`check`は指定した基準版のスナップショット、`doctor`は`HEAD`の
    スナップショットも対象にする」）。

    ``skip_limit_dimensions``は全体事前検査のリソースの上限の判定から除外する次元の名前の集合
    （空集合が既定＝従来どおり全次元を判定する）。`verifyBindingCount`は
    `commandDefinitionCount`の部分集合であり、両方が同時に超過し得るが、複数の次元が同時に
    超過する場合は`verify`の実行計画の次元を優先して報告する（複合ワークスペース仕様 §10）。
    `verify --all-workspaces`は自分のテスト割当ての計画から`verifyBindingCount`を直接数えるため、
    ここでは`commandDefinitionCount`を渡して一般の事前検査の早期停止を避け、`verify`側の判定を
    優先させる。`check`と`doctor`は空集合のまま呼び出し、この判定順を変えない。

    ``ears_version_code``は、ルートの設定のEARS-AIのメジャーバージョンが非互換のときの診断コードである。`doctor`は
    `SPEC-DOCTOR-EARS-001`を渡す（診断レジストリの`DOCTOR-EARS-VERSION`。ほかの操作は`EARS-SCHEMA-MAJOR`の`SPEC-EARS-VERSION-001`）。

    次の3つは単独操作（`context`・`check`・`verify`・`doctor`）の全体事前検査だけが渡す（複合ワークスペース仕様 §3・§7、ADR-063）。
    ``nearest_config_path``は、Gitでリポジトリのルートを確定できないときのルートの候補（通常の探索で見つけた最も近い設定）、
    ``selected_dir``は選択した最も近い設定のディレクトリ（カタログに登録されていなければ`SPEC-MULTI-UNREGISTERED-001`）、
    ``compare_git_configs``はGitが認識する設定の列挙と比較するか（単独の`context`・`check`・`verify`は偽）。
    
    ``report_git_with_config_stop``が真なら、ルートの設定で停止したときも、Gitの境界を確定できなければ`SPEC-MULTI-GIT-001`を加える
    （`doctor`だけが真を渡す。`04_doctor.md` §3）。
    """

    root, cfg_path, git_confirmed, git_top = _locate_root(cwd, git, env, nearest_config_path)
    if root is None:
        return PrecheckResult(discovery_failed=True)

    outcome = config_mod.read_config(cfg_path, ears_version_code=ears_version_code)
    if outcome.stop:
        diags = outcome.diagnostics + outcome.warnings
        if report_git_with_config_stop and not git_confirmed:
            # `doctor`は設定の不適合とGitの不在を独立した2つの原因とし、設定で止まっても`SPEC-MULTI-GIT-001`を返す
            # （`04_doctor.md` §3、ユーザーの決定D5。ほかの操作は設定の停止の診断だけを返す）。
            diags = diags + [_diag(
                "SPEC-MULTI-GIT-001", "blocked", messages.MULTI_GIT_BOUNDARY_UNKNOWN,
                {"kind": "environment", "component": "git"},
            )]
        return PrecheckResult(
            ok=False,
            root_id=outcome.workspace_id,
            diagnostics=diags,
            git_status="passed" if git_confirmed else "blocked",
            # ルートの設定のスキーマまたはEARS-AIのメジャーバージョンが非互換なら、メンバーの非互換（`SPEC-MULTI-VERSION-001`）と
            # 同じく、カタログの検査項目を`blocked`で置く（`04_doctor.md` §3。ユーザーの決定）。そのほかの停止では置かない。
            catalog_status="blocked" if outcome.stop_stage in ("schema-major", "ears-major") else None,
            repo_root=root,
            git_confirmed=git_confirmed,
            root_config=outcome.parsed,
        )

    root_id = outcome.workspace_id
    assert outcome.config is not None

    if not git_confirmed:
        diag = _diag(
            "SPEC-MULTI-GIT-001", "blocked", messages.MULTI_GIT_BOUNDARY_UNKNOWN,
            {"kind": "environment", "component": "git"},
        )
        return PrecheckResult(
            ok=False, root_id=root_id, diagnostics=[diag], git_status="blocked", catalog_status=None, repo_root=root,
            git_confirmed=False, root_config=outcome.config,
        )

    revs = list(extra_config_revs or [])
    catalog_diags, members = _validate_catalog(
        root, root_id, outcome.config, git, cwd, env, revs, skip_limit_dimensions=skip_limit_dimensions,
        compare_git_configs=compare_git_configs, selected_dir=selected_dir, git_top=git_top,
    )
    if catalog_diags:
        status = worst_status([d.resultStatus for d in catalog_diags])
        return PrecheckResult(
            ok=False,
            root_id=root_id,
            diagnostics=catalog_diags,
            git_status="passed",
            catalog_status=status,
            repo_root=root,
            git_confirmed=True,
            root_config=outcome.config,
        )

    assert members is not None
    return PrecheckResult(
        ok=True,
        root_id=root_id,
        diagnostics=[],
        git_status="passed",
        catalog_status="passed",
        members=members,
        repo_root=root,
        git_confirmed=True,
        root_config=outcome.config,
    )
