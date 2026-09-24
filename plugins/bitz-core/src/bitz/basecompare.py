"""Git基準版比較（`03_操作仕様/02_check.md` §5〜§9）。

状態遷移・管理済みSPEC削除（§9文書仕様 §6・§9）、承認済みREQ保護（同 §8）、changed対象選択
（check.md §6）、影響候補（check.md §8）をここへ集約する。いずれもGit基準版が解決できた場合
（``revision``が非``None``）だけ呼び出し側（`check.py`）から呼ばれる。
"""

from __future__ import annotations

from . import gitutil
from . import messages
from .config import Diagnostic
from .document import DocEntry, build_base_catalog

#: 文書・Frontmatter・状態仕様 §6。
_REQ_TECH_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"draft", "approved", "rejected"},
    "approved": {"approved", "draft", "outdated"},
    "outdated": {"outdated", "draft", "approved"},
    "rejected": {"rejected"},
}
_ADR_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"proposed", "accepted", "rejected"},
    "accepted": {"accepted", "superseded"},
    "rejected": {"rejected"},
    "superseded": {"superseded"},
}
_TASK_TRANSITIONS: dict[str, set[str]] = {
    "open": {"open", "done", "cancelled"},
    "done": {"done"},
    "cancelled": {"cancelled"},
}

#: 関係・トレースモデル §3「強さ」。`related`はweakのため含めない。
STRONG_RELATIONS = ("requires", "refines", "addresses", "supersedes")


def _transition_table(kind: str) -> dict[str, set[str]] | None:
    if kind in ("REQ", "TECH"):
        return _REQ_TECH_TRANSITIONS
    if kind == "ADR":
        return _ADR_TRANSITIONS
    if kind == "TASK":
        return _TASK_TRANSITIONS
    return None


def _mk(code, severity, status, summary, path, workspace_id, *, key=None) -> Diagnostic:
    src: dict = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if key is not None:
        src["key"] = key
    return Diagnostic(code=code, severity=severity, resultStatus=status, summary=summary, source=src)


def load_base_catalog(
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    base_commit: str | None,
    workspace_root: str,
    workspace_id: str,
) -> dict[str, DocEntry]:
    """Git基準版のcatalogを``doc_id -> DocEntry``で返す。解決不能なら空dict。"""

    if not git.available or git.executable is None or base_commit is None:
        return {}
    return build_base_catalog(git.executable, cwd, env, base_commit, workspace_root, workspace_id)


def state_transition_diagnostics(
    base_by_id: dict[str, DocEntry],
    current_by_id: dict[str, DocEntry],
    workspace_id: str,
    *,
    current_ids_present: set[str] | None = None,
    source_ids: set[str] | None = None,
) -> list[Diagnostic]:
    """禁止状態遷移と管理済みSPEC削除を検査する（文書・Frontmatter・状態仕様 §6・§9）。

    基準版と現在版は``documentId``で対応付ける。path差だけの変更は
    （``current_by_id``が現在版のIDだけで索引化されているため）同一文書として扱われ、
    rename扱いになる。``current_ids_present``（省略時は``current_by_id``のkeyと同じ）は、
    ID重複やFrontmatter破損でcheckの索引（``current_by_id``）から除かれた文書も含む、
    現在版に実在するdocument ID全体である。これを使わずに``current_by_id``の有無だけで
    削除を判定すると、重複IDで両方skip-documentになった文書を「削除された」と誤検出する
    （ID重複はそれ自体`SPEC-ID-DUPLICATE-001`が既に報告するため、二重にDiagnosticを作らない）。

    ``source_ids``を渡すと（`scope: selected`の`full_check_ids`）、対象を``doc_id``がその集合に
    含まれる文書だけへ絞る（`check.md §5`「同じ基準版を対象選択、状態遷移、削除検出、REQ保護、
    TASK境界へ使用」）。削除された文書のIDは現在版の索引（`source_ids`の元）に存在し得ないため、
    この絞り込みだけで自然に「明示対象checkでは削除Diagnosticを生成しない」を満たす。
    """

    if current_ids_present is None:
        current_ids_present = set(current_by_id)

    diags: list[Diagnostic] = []
    for doc_id in sorted(base_by_id):
        if source_ids is not None and doc_id not in source_ids:
            continue
        base_entry = base_by_id[doc_id]
        current_entry = current_by_id.get(doc_id)
        if current_entry is None:
            if doc_id in current_ids_present:
                # ID重複などで索引から除かれただけで、実際には削除されていない。
                continue
            diags.append(
                _mk(
                    "SPEC-STATE-TRANSITION-001",
                    "error",
                    "failed",
                    messages.DOCUMENT_DELETED,
                    base_entry.path,
                    workspace_id,
                )
            )
            continue
        table = _transition_table(current_entry.kind)
        if table is None:
            continue
        allowed = table.get(base_entry.status)
        if allowed is None or current_entry.status in allowed:
            continue
        diags.append(
            _mk(
                "SPEC-STATE-TRANSITION-001",
                "error",
                "failed",
                messages.state_transition_forbidden(current_entry.kind, base_entry.status, current_entry.status),
                current_entry.path,
                workspace_id,
                key="status",
            )
        )
    return diags


def _statement_semantics(entry: DocEntry) -> dict[str, tuple]:
    """statement IDごとの意味field（source・rawを除く）を返す（承認済みREQ保護の比較対象）。"""

    out: dict[str, tuple] = {}
    for stmt in entry.statements:
        out[stmt["id"]] = (
            stmt.get("actor"),
            stmt.get("activation"),
            stmt.get("modality"),
            stmt.get("reason"),
            stmt.get("operation"),
            stmt.get("extensions"),
        )
    return out


def _meaning_change_key(base_entry: DocEntry, current_entry: DocEntry) -> str | None:
    """`title`、EARS-AI規範文の意味field、強い関係のいずれかが変わっていればそのkeyを返す。

    `implements`、`tests`、`verify`、`related`、`x-`拡張、説明文だけの変更は対象外
    （文書・Frontmatter・状態仕様 §8）。
    """

    if base_entry.title != current_entry.title:
        return "title"
    base_relations = (base_entry.frontmatter or {}).get("relations") or {}
    current_relations = (current_entry.frontmatter or {}).get("relations") or {}
    for relation in STRONG_RELATIONS:
        if (base_relations.get(relation) or []) != (current_relations.get(relation) or []):
            return f"relations.{relation}"
    if _statement_semantics(base_entry) != _statement_semantics(current_entry):
        return "statements"
    return None


def approved_protection_diagnostics(
    base_by_id: dict[str, DocEntry],
    current_by_id: dict[str, DocEntry],
    workspace_id: str,
    *,
    source_ids: set[str] | None = None,
) -> list[Diagnostic]:
    """approved REQの意味変更時にstatusを戻していない場合を検査する（文書仕様 §8）。

    ``source_ids``（`scope: selected`の`full_check_ids`）を渡すと、対象をその集合内の文書だけへ
    絞る（`check.md §5`）。
    """

    diags: list[Diagnostic] = []
    for doc_id in sorted(base_by_id):
        if source_ids is not None and doc_id not in source_ids:
            continue
        base_entry = base_by_id[doc_id]
        if base_entry.kind != "REQ" or base_entry.status != "approved":
            continue
        current_entry = current_by_id.get(doc_id)
        if current_entry is None or current_entry.status != "approved":
            # 削除はSTATE-TRANSITIONが扱う。statusを戻していれば保護は働かない。
            continue
        key = _meaning_change_key(base_entry, current_entry)
        if key is not None:
            diags.append(
                _mk(
                    "SPEC-SAFETY-APPROVED-001",
                    "error",
                    "failed",
                    messages.APPROVED_MEANING_CHANGED,
                    current_entry.path,
                    workspace_id,
                    key=key,
                )
            )
    return diags


def _owning_doc_id(path: str, current_by_path: dict[str, DocEntry], base_by_path: dict[str, DocEntry]) -> str | None:
    entry = current_by_path.get(path)
    if entry is None:
        entry = base_by_path.get(path)
    return entry.doc_id if entry is not None else None


def build_reverse_index(current_by_id: dict[str, DocEntry], field: str) -> dict[str, set[str]]:
    """``implements``または``tests[].path``のpath逆索引を返す（`check.md §6`）。

    rejected REQ/TECHは所有逆索引へ含めない。
    """

    index: dict[str, set[str]] = {}
    for doc_id, entry in current_by_id.items():
        if entry.kind not in ("REQ", "TECH") or entry.status == "rejected":
            continue
        if field == "implements":
            paths = entry.frontmatter.get("implements") or []
        else:
            paths = [
                t.get("path")
                for t in (entry.frontmatter.get("tests") or [])
                if isinstance(t, dict) and t.get("path")
            ]
        for p in paths:
            index.setdefault(p, set()).add(doc_id)
    return index


def changed_selection(
    changed_paths: list,
    current_by_path: dict[str, DocEntry],
    base_by_path: dict[str, DocEntry],
    implements_index: dict[str, set[str]],
    tests_index: dict[str, set[str]],
) -> tuple[set[str], int, int]:
    """引数なしcheckの対象文書選択（`check.md §6`）。

    戻り値は``(owning_doc_ids, changedPathCount, excludedCodeTestPathCount)``。SPEC pathは
    Frontmatter IDへ（現在版になければ削除検出用に基準版へ）正規化し、code／test pathは
    `implements`／`tests[].path`の逆索引で正規化する。どの逆索引にも該当しないcode/test pathは
    件数だけを残す（Diagnosticを出さない）。
    """

    owning: set[str] = set()
    excluded = 0
    for c in changed_paths:
        touched = [p for p in (c.path, c.old_path) if p]
        matched = False
        has_spec_path = False
        for p in touched:
            if p.startswith(".spec/"):
                has_spec_path = True
                doc_id = _owning_doc_id(p, current_by_path, base_by_path)
                if doc_id is not None:
                    owning.add(doc_id)
                    matched = True
            else:
                ids = implements_index.get(p, set()) | tests_index.get(p, set())
                if ids:
                    owning.update(ids)
                    matched = True
        if not matched and not has_spec_path:
            excluded += 1
    return owning, len(changed_paths), excluded


def changed_spec_document_ids(
    changed_paths: list,
    current_by_path: dict[str, DocEntry],
    base_by_path: dict[str, DocEntry],
    kinds: tuple[str, ...] = ("REQ", "TECH"),
) -> set[str]:
    """SPEC pathが直接変更されたkinds文書のID集合を返す（影響候補 `check.md §8`の起点）。

    `related`、code、test変更を起点にしない（§8）ため、SPEC path直接変更だけを見る。
    """

    result: set[str] = set()
    for c in changed_paths:
        for p in (c.path, c.old_path):
            if p is None or not p.startswith(".spec/"):
                continue
            entry = current_by_path.get(p) or base_by_path.get(p)
            if entry is not None and entry.doc_id is not None and entry.kind in kinds:
                result.add(entry.doc_id)
    return result


def impact_candidate_diagnostics(
    changed_doc_ids: set[str],
    current_by_id: dict[str, DocEntry],
    workspace_id: str,
    *,
    source_ids: set[str] | None = None,
) -> list[Diagnostic]:
    """changed REQ/TECHへ強く依存するapproved文書を警告する（`check.md §8`）。

    ``source_ids``（`scope: selected`の`full_check_ids`）を渡すと、警告を出す側（依存元）の文書を
    その集合内だけへ絞る（`check.md §5`）。
    """

    diags: list[Diagnostic] = []
    for doc_id in sorted(current_by_id):
        if source_ids is not None and doc_id not in source_ids:
            continue
        entry = current_by_id[doc_id]
        if entry.status != "approved":
            continue
        relations = (entry.frontmatter or {}).get("relations") or {}
        for relation in STRONG_RELATIONS:
            hit_id: str | None = None
            for ref in relations.get(relation) or []:
                target_id = ref.split(":", 1)[0] if ":" in ref else ref
                if target_id in changed_doc_ids:
                    hit_id = target_id
                    break
            if hit_id is not None:
                diags.append(
                    _mk(
                        "SPEC-IMPACT-OUTDATED-001",
                        "warning",
                        "passed_with_warnings",
                        messages.impact_outdated(doc_id, hit_id),
                        entry.path,
                        workspace_id,
                        key=f"relations.{relation}",
                    )
                )
    return diags


def strong_dependency_closure(start_ids: set[str], current_by_id: dict[str, DocEntry]) -> set[str]:
    """``start_ids``から強い関係（`STRONG_RELATIONS`）を前方へ辿った推移閉包を返す（`check.md §3`）。"""

    seen: set[str] = set()
    frontier = list(start_ids)
    while frontier:
        cur = frontier.pop()
        entry = current_by_id.get(cur)
        if entry is None:
            continue
        relations = (entry.frontmatter or {}).get("relations") or {}
        for relation in STRONG_RELATIONS:
            for ref in relations.get(relation) or []:
                target_id = ref.split(":", 1)[0] if ":" in ref else ref
                if target_id in current_by_id and target_id not in seen and target_id not in start_ids:
                    seen.add(target_id)
                    frontier.append(target_id)
    return seen
