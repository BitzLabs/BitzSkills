"""複合workspaceの修飾ID解決とrelation／path／coverage Diagnostic（Step 5B）。

`02_SPECモデル/04_関係・トレースモデル.md` §5・§5.1・§9、`02_SPECモデル/05_複合workspace仕様.md`
§4・§5・§5.1、`00_共通契約/05_Diagnostic-registry.md` §7 を実装する。

`relations.py`は単一workspace（またはworkspace内表現に限定した）索引を前提とするため、Phase Cの
関数（`check_relations`／`check_paths`／`check_coverage`）をそのまま複合workspace全体へは使わない。
本moduleは``(workspace_id, localId)``を索引keyとする横断解決を独立に実装し、`check.py`の
`--all-workspaces`（member単位のフル検査）と、明示修飾対象を持つworkspace単独checkの両方から使う。

循環検査（`CTX-CYCLE-001`）はworkspace内のlocal edgeだけを対象とする簡略化を採る
（横断`requires`／`refines`edgeを跨いだ循環検出はStep 5Bのfixtureが要求しないため、既知の
未対応として扱う。`relations.py`のlocal索引・private helperをそのまま再利用する）。
"""

from __future__ import annotations

import os
from dataclasses import replace

from . import document as document_mod
from . import lex
from . import messages
from . import multiws
from . import relations as relations_mod
from .config import Diagnostic
from .document import DocEntry

_STRONG_RELATIONS = ("requires", "refines", "addresses", "supersedes")
_ALL_RELATIONS = (*_STRONG_RELATIONS, "related")


def _qualify_local_ref(ref: str, owner_ws_id: str) -> str:
    """非修飾``ref``を``owner_ws_id``で修飾する。既に修飾済み（``"::"``を含む）ならそのまま返す。"""

    if not isinstance(ref, str) or "::" in ref:
        return ref
    return f"{owner_ws_id}::{ref}"


def _qualified_relations_view(entry: DocEntry, owner_ws_id: str) -> DocEntry:
    """``entry``の`relations`と`tests[].covers`の非修飾targetを``owner_ws_id``で修飾したviewを返す。

    複合workspace仕様 §4「`relations`と`tests[].covers`は同じworkspaceを参照するとき非修飾形式を
    許可し、別workspaceを参照するとき複合workspaceの正規形式を必須とする」に基づき、非修飾targetは
    **宣言元（＝``entry``自身）の所有workspace**で解決しなければならない。

    `targetexpand.py`／`relations._resolve_ref`は単一のflat `id_index`/`statement_index`を前提とし、
    宣言元workspaceの文脈を持たない。この統合索引を組み立てる段（本moduleの
    :func:`build_multi_context`・:func:`merge_indices`）で、active workspace以外の各workspaceの
    entryについてだけ、前もって非修飾targetを宣言元workspaceで修飾しておけば、既存の解決経路
    （`relations._resolve_ref`が``"::"``を含む参照をそのまま索引keyとして引く）がそのまま
    正しく機能する。

    `entry.frontmatter`の`id`・`doc_id`・`statements`など識別子そのものは変更しない
    （`build_id_index`／`build_statement_index`のkeyは影響を受けない）。変更が無ければ``entry``自身を
    そのまま返す（不要なcopyを作らない）。修飾は冪等（`_normalize_frontmatter`等が行うDigest材料の
    正規化と同じ``_canon``相当の規則）なので、Bundle出力・Digest材料の正規化結果はこの前処理の
    有無で変わらない。
    """

    fm = entry.frontmatter
    if not isinstance(fm, dict):
        return entry

    relations_raw = fm.get("relations")
    new_relations = None
    if isinstance(relations_raw, dict):
        rebuilt: dict = {}
        changed = False
        for key, vals in relations_raw.items():
            if isinstance(vals, list):
                new_vals = [_qualify_local_ref(v, owner_ws_id) for v in vals]
                if new_vals != vals:
                    changed = True
                rebuilt[key] = new_vals
            else:
                rebuilt[key] = vals
        if changed:
            new_relations = rebuilt

    tests_raw = fm.get("tests")
    new_tests = None
    if isinstance(tests_raw, list):
        rebuilt_tests = []
        changed_tests = False
        for t in tests_raw:
            if isinstance(t, dict) and isinstance(t.get("covers"), list):
                new_covers = [_qualify_local_ref(c, owner_ws_id) for c in t["covers"]]
                if new_covers != t["covers"]:
                    changed_tests = True
                    nt = dict(t)
                    nt["covers"] = new_covers
                    rebuilt_tests.append(nt)
                    continue
            rebuilt_tests.append(t)
        if changed_tests:
            new_tests = rebuilt_tests

    if new_relations is None and new_tests is None:
        return entry

    new_fm = dict(fm)
    if new_relations is not None:
        new_fm["relations"] = new_relations
    if new_tests is not None:
        new_fm["tests"] = new_tests
    return replace(entry, frontmatter=new_fm)


def _mk(code, severity, status, summary, path, workspace_id, *, key=None, evidence=None) -> Diagnostic:
    src: dict = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if key is not None:
        src["key"] = key
    return Diagnostic(code=code, severity=severity, resultStatus=status, summary=summary, source=src, evidence=evidence)


def parse_qualified(ref: str) -> tuple[str, str] | None:
    """``ref``を``(workspace_id, local_ref)``へ分割する。非修飾なら``None``を返す。"""

    if "::" not in ref:
        return None
    ws, _, local = ref.partition("::")
    return ws, local


def _qualifier_lexically_valid(ws: str, local: str) -> bool:
    if not isinstance(ws, str) or not lex.WORKSPACE_ID_RE.match(ws):
        return False
    return local != ""


def _resolve_local(
    local_ref: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> tuple[DocEntry | None, str | None]:
    """1つのworkspaceの非修飾索引だけを使って``local_ref``を解決する（`relations._resolve_ref`と同型）。"""

    if ":" in local_ref:
        stmt = statement_index.get(local_ref)
        if stmt is None:
            return None, None
        doc_id = stmt["documentId"]
        return id_index.get(doc_id), doc_id
    entry = id_index.get(local_ref)
    return entry, (local_ref if entry is not None else None)


def resolve_edge(
    ref: str,
    source_ws_id: str,
    local_id_indices: dict[str, dict[str, DocEntry]],
    local_stmt_indices: dict[str, dict[str, dict]],
    known_ws_ids: set[str],
):
    """``ref``を関係・トレースモデル §5.1 の優先順位で解決する。

    戻り値は``("ok", target_entry, qualified_id)``または``("diag", reason, None)``。``reason``は
    ``"lexical"``（修飾IDの字句不正）、``"unqualified-elsewhere"``（別workspaceにだけ存在する
    非修飾参照）、``"workspace-unknown"``（修飾workspaceがcatalog不在）、``"missing"``
    （workspaceは存在するがtarget不在）のいずれか。
    """

    q = parse_qualified(ref)
    if q is None:
        entry, local_doc_id = _resolve_local(
            ref, local_id_indices.get(source_ws_id, {}), local_stmt_indices.get(source_ws_id, {})
        )
        if entry is not None:
            return "ok", entry, f"{source_ws_id}::{local_doc_id}"
        for ws in known_ws_ids:
            if ws == source_ws_id:
                continue
            other_entry, _ = _resolve_local(ref, local_id_indices.get(ws, {}), local_stmt_indices.get(ws, {}))
            if other_entry is not None:
                return "diag", "unqualified-elsewhere", None
        return "diag", "missing", None

    ws, local = q
    if not _qualifier_lexically_valid(ws, local):
        return "diag", "lexical", None
    if ws not in known_ws_ids:
        return "diag", "workspace-unknown", None
    entry, local_doc_id = _resolve_local(local, local_id_indices.get(ws, {}), local_stmt_indices.get(ws, {}))
    if entry is not None:
        return "ok", entry, f"{ws}::{local_doc_id}"
    return "diag", "missing", None


def _kind_ok(entry: DocEntry, relation: str, ref: str, target_entry: DocEntry) -> bool:
    allowed = relations_mod.RELATION_ALLOWED_TARGET_KINDS.get((entry.kind, relation), set())
    if target_entry.kind not in allowed:
        return False
    if relation == "requires" and target_entry.kind == "ADR" and target_entry.status != "accepted":
        return False
    if relation == "addresses":
        q = parse_qualified(ref)
        local_part = q[1] if q is not None else ref
        if ":" not in local_part:
            if target_entry.kind != "TECH" or target_entry.statement_count > 0:
                return False
    return True


def field_diagnostics(
    entry: DocEntry,
    ws_id: str,
    local_id_indices: dict[str, dict[str, DocEntry]],
    local_stmt_indices: dict[str, dict[str, dict]],
    known_ws_ids: set[str],
) -> list[Diagnostic]:
    """1文書分のrelation Diagnosticを、修飾ID解決の優先順位（関係・トレースモデル §5.1）で生成する。"""

    diags: list[Diagnostic] = []
    relations = entry.frontmatter.get("relations") or {}
    for relation in _ALL_RELATIONS:
        refs = relations.get(relation) or []
        if not refs:
            continue
        is_related = relation == "related"
        for ref in refs:
            status, payload, _qid = resolve_edge(ref, ws_id, local_id_indices, local_stmt_indices, known_ws_ids)
            if status == "diag":
                if payload == "lexical":
                    diags.append(
                        _mk(
                            "SPEC-MULTI-REF-001", "error", "failed", messages.MULTI_REF_QUALIFIER_INVALID,
                            entry.path, ws_id, key=f"relations.{relation}", evidence=ref,
                        )
                    )
                elif payload == "unqualified-elsewhere":
                    diags.append(
                        _mk(
                            "SPEC-MULTI-REF-001", "error", "failed", messages.MULTI_REF_UNQUALIFIED,
                            entry.path, ws_id, key=f"relations.{relation}", evidence=ref,
                        )
                    )
                elif payload == "workspace-unknown":
                    diags.append(
                        _mk(
                            "SPEC-MULTI-REF-001", "error", "failed", messages.MULTI_REF_WORKSPACE_UNKNOWN,
                            entry.path, ws_id, key=f"relations.{relation}", evidence=ref,
                        )
                    )
                else:  # missing
                    if is_related:
                        diags.append(
                            _mk(
                                "SPEC-RELATION-ADVISORY-MISSING-001", "warning", "passed_with_warnings",
                                messages.RELATION_ADVISORY_MISSING, entry.path, ws_id, key=f"relations.{relation}",
                                evidence=ref,
                            )
                        )
                    else:
                        diags.append(
                            _mk(
                                "SPEC-RELATION-MISSING-001", "error", "failed",
                                messages.relation_missing_strong(entry.path), entry.path, ws_id,
                                key=f"relations.{relation}", evidence=ref,
                            )
                        )
                continue
            target_entry = payload
            if not is_related and not _kind_ok(entry, relation, ref, target_entry):
                diags.append(
                    _mk(
                        "CTX-RELATION-TYPE-001", "error", "failed",
                        messages.relation_type_mismatch(entry.kind, target_entry.kind, relation),
                        entry.path, ws_id, key=f"relations.{relation}", evidence=ref,
                    )
                )

    if "refs" in entry.frontmatter:
        diags.append(
            _mk("SPEC-RELATION-LEGACY-001", "error", "failed", messages.RELATION_LEGACY_REFS, entry.path, ws_id, key="refs")
        )
    return diags


def _cyclic_edge_diagnostics(
    adjacency: dict[str, list[tuple[str, str]]], owner: dict[str, tuple[str, DocEntry]]
) -> list[Diagnostic]:
    """``adjacency``（qualified ID keyed）の循環edgeをDiagnosticへ変換する。

    ``owner``は``qualified_id -> (workspace_id, entry)``。単一workspaceの`_cycle_diagnostics`と同じ
    規則（循環に参加するedgeのsource文書）で1件を返すが、sourceのworkspaceIdはそのedgeを宣言した
    文書自身のworkspaceにする（複合workspace仕様 §4「member単独操作を含め複合workspaceの正規形式で
    返す」の運用として、横断edgeの循環も宣言元workspaceへ帰属させる）。
    """

    cyclic_pairs = relations_mod._find_cyclic_edges(adjacency)
    diags: list[Diagnostic] = []
    for qid, relation in sorted(cyclic_pairs):
        ws_id, entry = owner[qid]
        diags.append(
            _mk(
                "CTX-CYCLE-001", "error", "failed", messages.relation_cycle(relation),
                entry.path, ws_id, key=f"relations.{relation}",
            )
        )
    return diags


def global_cycle_diagnostics(entries_by_ws: dict[str, list[DocEntry]]) -> list[Diagnostic]:
    """複合workspace全体で、横断edge（修飾IDで解決したedge）も含めたgraphの循環を検出する。

    関係・トレースモデル §4「`requires`と`refines`を合わせた意味依存graph、`supersedes`連鎖…の
    循環を禁止する」は複合workspaceでも変わらない（workspace境界で図が分断されるわけではない）。
    ノードは``"ws::localId"``で複合workspace全体を通じて一意化する。``related``循環は対象外
    （関係・トレースモデル §4「`related`循環は許可し探索しない」）。
    """

    local_id_indices: dict[str, dict[str, DocEntry]] = {}
    local_stmt_indices: dict[str, dict[str, dict]] = {}
    owner: dict[str, tuple[str, DocEntry]] = {}
    for ws_id, entries in entries_by_ws.items():
        lid = relations_mod.build_id_index(entries)
        lstmt = relations_mod.build_statement_index(entries)
        local_id_indices[ws_id] = lid
        local_stmt_indices[ws_id] = lstmt
        for local_id, entry in lid.items():
            owner[f"{ws_id}::{local_id}"] = (ws_id, entry)
    known_ws_ids = set(entries_by_ws)

    def _adjacency_for(relation_names: tuple[str, ...]) -> dict[str, list[tuple[str, str]]]:
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for ws_id, entries in entries_by_ws.items():
            for entry in relations_mod.valid_entries(entries):
                qid = f"{ws_id}::{entry.doc_id}"
                edges: list[tuple[str, str]] = []
                relations = entry.frontmatter.get("relations") or {}
                for relation in relation_names:
                    for ref in relations.get(relation) or []:
                        status, payload, target_qid = resolve_edge(
                            ref, ws_id, local_id_indices, local_stmt_indices, known_ws_ids
                        )
                        if status != "ok" or target_qid is None:
                            continue
                        target_entry = payload
                        if not _kind_ok(entry, relation, ref, target_entry):
                            continue
                        edges.append((relation, target_qid))
                if edges:
                    adjacency[qid] = edges
        return adjacency

    diags = _cyclic_edge_diagnostics(_adjacency_for(("requires", "refines")), owner)
    diags += _cyclic_edge_diagnostics(_adjacency_for(("supersedes",)), owner)
    return diags


def _skip_path_and_coverage(entry: DocEntry) -> bool:
    return entry.status in ("rejected", "cancelled")


def _resolve_owned_path(ws_root_abs: str, own_real: str, rel_path: str) -> tuple[bool, bool]:
    """``(exists_ok, ownership_violation)``を返す（複合workspace仕様 §5.1）。

    symlink leaf は実path解決後、自workspaceの実rootの配下（境界を含む）にあるときだけ許可する。
    symlink祖先directoryの追跡はStep 5Aのcatalog検証（member path）側の責務であり、ここでは
    宣言pathのleaf symlinkだけを判定する（fixtureが要求する範囲）。
    """

    abs_path = os.path.join(ws_root_abs, rel_path)
    if not os.path.lexists(abs_path):
        return False, False
    if os.path.islink(abs_path):
        real = os.path.realpath(abs_path)
        if not os.path.isfile(real):
            return False, False
        if real == own_real or real.startswith(own_real + os.sep):
            return True, False
        return False, True
    if not os.path.isfile(abs_path):
        return False, False
    return True, False


def path_diagnostics(
    entries: list[DocEntry], ws_id: str, ws_root_abs: str, real_roots: dict[str, str]
) -> list[Diagnostic]:
    """`implements`と`tests[].path`の存在・所有境界を検査する（関係・トレースモデル §9、複合workspace仕様 §5.1）。"""

    own_real = real_roots[ws_id]
    diags: list[Diagnostic] = []
    for entry in relations_mod.valid_entries(entries):
        if _skip_path_and_coverage(entry):
            continue
        is_draft = entry.status == "draft"
        severity = "warning" if is_draft else "error"
        status = "passed_with_warnings" if is_draft else "failed"

        implements = entry.frontmatter.get("implements") or []
        for p in implements:
            ok, violation = _resolve_owned_path(ws_root_abs, own_real, p)
            if violation:
                diags.append(
                    _mk(
                        "SPEC-MULTI-OWNERSHIP-001", "error", "failed",
                        messages.multi_ownership_resolved(p, ws_id), entry.path, ws_id, key="implements",
                    )
                )
                break
            if not ok:
                diags.append(
                    _mk(
                        "SPEC-PATH-INVALID-001", severity, status,
                        messages.IMPLEMENTS_PATH_DRAFT if is_draft else messages.IMPLEMENTS_PATH_MISSING,
                        entry.path, ws_id, key="implements",
                    )
                )
                break

        tests = entry.frontmatter.get("tests") or []
        for idx, t in enumerate(tests):
            p = t.get("path") if isinstance(t, dict) else None
            if not p:
                continue
            ok, violation = _resolve_owned_path(ws_root_abs, own_real, p)
            if violation:
                diags.append(
                    _mk(
                        "SPEC-MULTI-OWNERSHIP-001", "error", "failed",
                        messages.multi_ownership_resolved(p, ws_id), entry.path, ws_id, key=f"tests[{idx}].path",
                    )
                )
            elif not ok:
                diags.append(
                    _mk(
                        "SPEC-PATH-INVALID-001", severity, status,
                        messages.TEST_PATH_DRAFT if is_draft else messages.TEST_PATH_MISSING,
                        entry.path, ws_id, key=f"tests[{idx}].path",
                    )
                )
    return diags


def _covers_allowed_refs(
    entry: DocEntry,
    ws_id: str,
    local_id_indices: dict[str, dict[str, DocEntry]],
    local_stmt_indices: dict[str, dict[str, dict]],
    known_ws_ids: set[str],
) -> tuple[set[str], set[str]]:
    allowed_statement_ids: set[str] = set()
    allowed_doc_ids: set[str] = set()

    for stmt in entry.statements:
        allowed_statement_ids.add(stmt["id"])
    if not entry.statements:
        allowed_doc_ids.add(entry.doc_id)

    refines_refs = (entry.frontmatter.get("relations") or {}).get("refines") or []
    for ref in refines_refs:
        status, payload, _qid = resolve_edge(ref, ws_id, local_id_indices, local_stmt_indices, known_ws_ids)
        if status != "ok":
            continue
        target_entry = payload
        q = parse_qualified(ref)
        local_part = q[1] if q is not None else ref
        if ":" in local_part:
            allowed_statement_ids.add(ref)
            continue
        target_ws = q[0] if q is not None else ws_id
        for stmt in target_entry.statements:
            allowed_statement_ids.add(stmt["id"] if target_ws == ws_id else f"{target_ws}::{stmt['id']}")

    return allowed_statement_ids, allowed_doc_ids


def coverage_diagnostics(
    entries: list[DocEntry],
    ws_id: str,
    local_id_indices: dict[str, dict[str, DocEntry]],
    local_stmt_indices: dict[str, dict[str, dict]],
    known_ws_ids: set[str],
) -> list[Diagnostic]:
    """`tests[].covers`が妥当なstatementまたは文書IDを参照することを検査する（関係・トレースモデル §9）。"""

    diags: list[Diagnostic] = []
    for entry in relations_mod.valid_entries(entries):
        if _skip_path_and_coverage(entry):
            continue
        allowed_statement_ids, allowed_doc_ids = _covers_allowed_refs(
            entry, ws_id, local_id_indices, local_stmt_indices, known_ws_ids
        )
        tests = entry.frontmatter.get("tests") or []
        for idx, t in enumerate(tests):
            if not isinstance(t, dict):
                continue
            covers = t.get("covers") or []
            # covers要素を単位とするDiagnostic（結果契約 §4）。独立した原因（配列の各要素）は
            # それぞれprimaryを持つため、最初の不正参照で打ち切らず全要素を検査する。
            for ref in covers:
                q = parse_qualified(ref)
                local_part = q[1] if q is not None else ref
                if ":" in local_part:
                    valid = ref in allowed_statement_ids
                else:
                    valid = ref in allowed_doc_ids
                if not valid:
                    diags.append(
                        _mk(
                            "SPEC-TEST-COVERAGE-001", "error", "failed", messages.TEST_COVERAGE_INVALID,
                            entry.path, ws_id, key=f"tests[{idx}].covers", evidence=ref,
                        )
                    )
    return diags


def build_multi_context(
    active_ws_id: str, active_entries: list[DocEntry], pre: "multiws.PrecheckResult", *, keep_body: bool = False
):
    """複合workspace内のworkspace単独check（明示修飾対象）向けの横断解決材料を組み立てる。

    戻り値は``(merged_id_index, merged_statement_index, local_id_indices, local_statement_indices,
    known_ws_ids)``。``merged_*``はactive workspace自身の非修飾索引に、他workspaceの``"ws::local"``
    修飾aliasを重ねたもの（`targetexpand.target_expansion`をそのまま再利用するための索引。
    `relations._resolve_ref`は``"::"``を含む参照を索引keyとしてそのまま引くため、修飾aliasを
    用意すれば横断`refines`／`requires`閉包が既存のTargetExpansionコードのまま動く）。
    ``local_*``はworkspace単位の非修飾索引（``resolve_edge``がsourceの所有workspaceだけを対象に
    非修飾参照を解決するために使う）。
    """

    local_id_indices: dict[str, dict[str, DocEntry]] = {
        active_ws_id: relations_mod.build_id_index(active_entries)
    }
    local_stmt_indices: dict[str, dict[str, dict]] = {
        active_ws_id: relations_mod.build_statement_index(active_entries)
    }
    merged_id_index: dict[str, DocEntry] = dict(local_id_indices[active_ws_id])
    merged_stmt_index: dict[str, dict] = dict(local_stmt_indices[active_ws_id])
    known_ws_ids: set[str] = set()

    # active workspace自身にも修飾aliasを重ねる（宣言側は読み手のactiveを知らず、常に自身の実IDで
    # 他workspaceを修飾するため、他workspaceの文書がactive workspaceを`"<active>::local"`形式で
    # 参照する場合も解決できる必要がある）。foreign workspaceのaliasと異なり、ここではdictを複製せず
    # 同じ値（bareな`id`/`documentId`のまま）を追加keyとして重ねるだけにする。target_expansionの
    # 逆参照走査（`_refines_targets`/`_refines_target_statements`）はresolve結果の`documentId`／`id`を
    # 正準表現として使うため、active workspace自身の統一表現（常にbare）を保つ必要がある。
    for local_id, entry in local_id_indices[active_ws_id].items():
        merged_id_index[f"{active_ws_id}::{local_id}"] = entry
    for local_sid, stmt in local_stmt_indices[active_ws_id].items():
        merged_stmt_index[f"{active_ws_id}::{local_sid}"] = stmt

    for wid, root, _relpath in multiws.ordered_workspaces(pre):
        known_ws_ids.add(wid)
        if wid == active_ws_id:
            continue
        catalog = document_mod.build_catalog(root, wid)
        if not keep_body:
            for e in catalog.entries:
                e.body = None
        qualified_entries = [_qualified_relations_view(e, wid) for e in catalog.entries]
        lid = relations_mod.build_id_index(qualified_entries)
        lstmt = relations_mod.build_statement_index(qualified_entries)
        local_id_indices[wid] = lid
        local_stmt_indices[wid] = lstmt
        for local_id, entry in lid.items():
            merged_id_index[f"{wid}::{local_id}"] = entry
        for local_sid, stmt in lstmt.items():
            qid = f"{wid}::{local_sid}"
            new_stmt = dict(stmt)
            new_stmt["id"] = qid
            new_stmt["documentId"] = f"{wid}::{stmt['documentId']}"
            merged_stmt_index[qid] = new_stmt

    return merged_id_index, merged_stmt_index, local_id_indices, local_stmt_indices, known_ws_ids


def merge_indices(active_ws_id: str, entries_by_ws: dict[str, list[DocEntry]]):
    """:func:`build_multi_context`と同じ戻り値形状を、**既に読み込み済みの**catalog entriesから組み立てる。

    `verify --all-workspaces`はmemberごとに別のworkspaceをactiveとして`TargetExpansion`を呼ぶため、
    :func:`build_multi_context`をそのままmember数だけ呼ぶと、他workspaceのcatalogをmember数
    （おおむね）二乗の回数だけdiskから読み直すことになる（複合workspace仕様 §10.1
    「全体verifyの解決時間はO(Σq(...))を許容する」だが、catalog自体の再parseはfile I/Oを伴うため
    避けられるなら避ける）。呼び出し側が1度だけ全workspaceのcatalogを読み、``entries_by_ws``
    （``{workspace_id: entries}``）として渡せば、本関数は索引構築（`build_id_index`／
    `build_statement_index`、いずれもO(そのworkspaceの文書・statement数)）だけをmemberごとに
    やり直す。
    """

    local_id_indices: dict[str, dict[str, DocEntry]] = {}
    local_stmt_indices: dict[str, dict[str, dict]] = {}
    for wid, entries in entries_by_ws.items():
        # active workspace自身は非修飾のまま（既存の統一表現）。他workspaceだけ、非修飾target
        # （同workspace参照、複合workspace仕様 §4）を宣言元workspaceで修飾したviewを使う。
        use_entries = entries if wid == active_ws_id else [_qualified_relations_view(e, wid) for e in entries]
        local_id_indices[wid] = relations_mod.build_id_index(use_entries)
        local_stmt_indices[wid] = relations_mod.build_statement_index(use_entries)
    merged_id_index: dict[str, DocEntry] = dict(local_id_indices[active_ws_id])
    merged_stmt_index: dict[str, dict] = dict(local_stmt_indices[active_ws_id])
    known_ws_ids: set[str] = set(entries_by_ws)

    for local_id, entry in local_id_indices[active_ws_id].items():
        merged_id_index[f"{active_ws_id}::{local_id}"] = entry
    for local_sid, stmt in local_stmt_indices[active_ws_id].items():
        merged_stmt_index[f"{active_ws_id}::{local_sid}"] = stmt

    for wid in entries_by_ws:
        if wid == active_ws_id:
            continue
        lid = local_id_indices[wid]
        lstmt = local_stmt_indices[wid]
        for local_id, entry in lid.items():
            merged_id_index[f"{wid}::{local_id}"] = entry
        for local_sid, stmt in lstmt.items():
            qid = f"{wid}::{local_sid}"
            new_stmt = dict(stmt)
            new_stmt["id"] = qid
            new_stmt["documentId"] = f"{wid}::{stmt['documentId']}"
            merged_stmt_index[qid] = new_stmt

    return merged_id_index, merged_stmt_index, local_id_indices, local_stmt_indices, known_ws_ids
