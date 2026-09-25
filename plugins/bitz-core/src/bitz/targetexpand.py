"""`TargetExpansion(root, purpose)`（`02_SPECモデル/04_関係・トレースモデル.md` §6.1〜§6.4）。

起点から対象を展開する唯一の契約。`context`、明示対象`check`、`verify`はこの関数を再利用する
（同 §6.4）。`purpose=interpret`は`check`の明示対象検査が使う閉包規則と完全に同じコードを使う
（Step 2 Phase Cで実装済み。挙動を変えないため:func:`_interpret_closure`は変更しない）。

`implement`／`verify`はStep 3で追加した。`context`だけがこれらのpurposeを使う。返り値
:class:`TargetExpansionResult` は、`context`が必要とする追加情報（到達edge、距離、draft
advisory集合、状態Diagnostic）を任意fieldとして保持する。`errors`が非空の場合、`context`は
完全解決を成立させず、`errors`の内容をそのままDiagnosticへ変換して閉包全体を止める
（関係・トレースモデル §10「状態と閉包」）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import messages
from .document import DocEntry
from .relations import RELATION_ALLOWED_TARGET_KINDS, resolve_ref as _resolve_ref

APPLICABLE_STATUS = {
    "REQ": {"approved"},
    "TECH": {"approved"},
    "ADR": {"accepted"},
    "TASK": {"open", "done"},
}


@dataclass
class TargetExpansionResult:
    root_documents: list[str] = field(default_factory=list)
    context_documents: list[str] = field(default_factory=list)
    target_statements: list[str] = field(default_factory=list)
    adjacent_statements: list[str] = field(default_factory=list)
    #: ``doc_id -> [(relation, source_doc_id), ...]``。`context`のreachedBy計算に使う
    #: （重複排除・sortは呼び出し側）。
    document_edges: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    #: ``doc_id -> 起点からの最短到達段数``（0＝起点自身）。`context`のprojection/role計算に使う。
    document_distance: dict[str, int] = field(default_factory=dict)
    #: §6.1「6.」で advisory として含めた draft refinement の doc_id 集合。
    draft_advisory: set[str] = field(default_factory=set)
    #: purpose=implement/verifyの状態違反（§10「状態と閉包」）。非空なら閉包を完全解決不成立とする。
    errors: list[dict] = field(default_factory=list)
    #: §6.1「5.」: interpretで起点が置換済み（有効な後継が単一）のときの``(origin_id, successor_id)``。
    #: `context`はoriginをadvisory、successorをreplacementとして示す（暗黙差替えはしない）。
    superseded_origin: tuple[str, str] | None = None


def _is_applicable(entry: DocEntry) -> bool:
    return entry.status in APPLICABLE_STATUS.get(entry.kind, set())


def _refines_targets(entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[str]:
    if entry.kind not in ("REQ", "TECH"):
        return []
    allowed = RELATION_ALLOWED_TARGET_KINDS.get((entry.kind, "refines"), set())
    refs = (entry.frontmatter.get("relations") or {}).get("refines") or []
    out: list[str] = []
    for ref in refs:
        target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None or target_entry.kind not in allowed:
            continue
        if target_doc_id not in out:
            out.append(target_doc_id)
    return out


def _refines_target_statements(
    entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[str]:
    """``entry``の`relations.refines`のうち、statement ID形式の参照の解決済み正準statement IDを返す。

    複合workspaceでは``ref``の綴り（宣言側の修飾形式）ではなく、``statement_index``で実際に
    解決したstatement dictの``id``を正準表現として返す（Step 5C）。同じ統合索引の中では、active
    workspace自身のstatementは常にbare表現、他workspaceのstatementは常に`ws::local`表現で
    一意に定まるため、これにより呼び出し側（`_applicable_refinement_statements`）のfrontier比較
    （bare/修飾のいずれか一方に統一された表現同士の比較）が常に成立する。単一workspaceでは
    ``ref``自体が唯一の表現なので、この変更は挙動を変えない（statement_index[ref]["id"] == ref）。
    """

    if entry.kind not in ("REQ", "TECH"):
        return []
    refs = (entry.frontmatter.get("relations") or {}).get("refines") or []
    out: list[str] = []
    for ref in refs:
        if ":" not in ref:
            continue
        target_entry, _target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None:
            continue
        stmt = statement_index.get(ref)
        canonical_id = stmt["id"] if stmt is not None else ref
        if canonical_id not in out:
            out.append(canonical_id)
    return out


def _requires_targets(entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[str]:
    allowed = RELATION_ALLOWED_TARGET_KINDS.get((entry.kind, "requires"), set())
    refs = (entry.frontmatter.get("relations") or {}).get("requires") or []
    out: list[str] = []
    for ref in refs:
        target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None or target_entry.kind not in allowed:
            continue
        if target_doc_id not in out:
            out.append(target_doc_id)
    return out


def _addresses_targets(entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[str]:
    """TASKの`relations.addresses`の参照（statement IDまたは規範文なしTECHの文書ID）を返す。"""

    if entry.kind != "TASK":
        return []
    allowed = RELATION_ALLOWED_TARGET_KINDS.get((entry.kind, "addresses"), set())
    refs = (entry.frontmatter.get("relations") or {}).get("addresses") or []
    out: list[str] = []
    for ref in refs:
        target_entry, _target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None or target_entry.kind not in allowed:
            continue
        if ref not in out:
            out.append(ref)
    return out


def _requires_closure(
    start_ids: list[str], id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[tuple[str, str]]:
    """``start_ids``からの`requires`推移閉包を``(target_doc_id, source_doc_id)``のlistで返す。

    ``source_doc_id``はその edge を宣言した文書（`requires`を持つ文書自身）。同じtargetへ複数経路で
    到達しても、到達したsourceごとに1要素を返す（呼び出し側が重複排除・distance計算を行う）。
    """

    edges: list[tuple[str, str]] = []
    seen_set: set[str] = set(start_ids)
    frontier = list(start_ids)
    while frontier:
        cur = frontier.pop(0)
        entry = id_index.get(cur)
        if entry is None:
            continue
        for target_id in _requires_targets(entry, id_index, statement_index):
            edges.append((target_id, cur))
            if target_id not in seen_set:
                seen_set.add(target_id)
                frontier.append(target_id)
    return edges


def _draft_refinements(
    context_ids: set[str], id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[str]:
    """§6.1「6.」: 閉包内のapplicable文書またはそのstatementをrefinesするdraft文書をadvisoryで含める。

    draft refinementの`requires`とそれをrefinesする文書は辿らない（advisoryは規範として
    適用しない）。
    """

    advisory: list[str] = []
    for cand_id, cand_entry in id_index.items():
        if cand_id in context_ids:
            continue
        if cand_entry.kind not in ("REQ", "TECH") or cand_entry.status != "draft":
            continue
        if any(t in context_ids for t in _refines_targets(cand_entry, id_index, statement_index)):
            advisory.append(cand_id)
    return advisory


def _owning_document_id(root: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> str | None:
    if ":" in root:
        stmt = statement_index.get(root)
        return stmt["documentId"] if stmt is not None else None
    return root if root in id_index else None


def _interpret_closure(
    owning_id: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> tuple[list[str], dict[str, list[tuple[str, str]]], dict[str, int], set[str]]:
    """`interpret`の完全閉包を計算する（§6.1、Step 2 Phase Cから移設。挙動は変更しない）。

    戻り値は``(context_order, document_edges, document_distance, draft_advisory)``。
    """

    context_set: set[str] = {owning_id}
    context_order: list[str] = [owning_id]
    edges: dict[str, list[tuple[str, str]]] = {owning_id: []}
    distance: dict[str, int] = {owning_id: 0}

    def _add(doc_id: str, relation: str, source_id: str, dist_from: int) -> None:
        is_new = doc_id not in context_set
        if is_new:
            context_set.add(doc_id)
            context_order.append(doc_id)
            distance[doc_id] = dist_from + 1
            edges[doc_id] = []
        pair = (relation, source_id)
        if pair not in edges[doc_id]:
            edges[doc_id].append(pair)

    # 2. requiresを終端まで辿る。
    for target_id, source_id in _requires_closure([owning_id], id_index, statement_index):
        _add(target_id, "requires", source_id, distance.get(source_id, 0))

    # 3. refines targetを含める（起点自身のrefines）。
    root_entry = id_index[owning_id]
    for target_id in _refines_targets(root_entry, id_index, statement_index):
        _add(target_id, "refines", owning_id, distance[owning_id])

    # 4. targetをrefineするapplicable文書を逆参照で含め、そのrequiresを辿る（推移的）。
    # 距離はtarget自身の距離+1とする（refiner-of-refinerが正しい間接距離を持つように、
    # targetをBFS frontierとして順に処理する）。
    refiner_seen: set[str] = set()
    frontier4 = [owning_id]
    refiners: list[str] = []
    while frontier4:
        target = frontier4.pop(0)
        target_dist = distance.get(target, 0)
        for cand_id, cand_entry in id_index.items():
            if cand_id == owning_id or cand_id in refiner_seen:
                continue
            if cand_entry.kind not in ("REQ", "TECH") or not _is_applicable(cand_entry):
                continue
            if target in _refines_targets(cand_entry, id_index, statement_index):
                refiner_seen.add(cand_id)
                _add(cand_id, "refines", cand_id, target_dist)
                refiners.append(cand_id)
                frontier4.append(cand_id)
    # refinerのrequires閉包（推移的）。
    for target_id, source_id in _requires_closure(refiners, id_index, statement_index):
        _add(target_id, "requires", source_id, distance.get(source_id, 0))

    # 6. draft refinementをadvisoryとして含める（requires・逆refinesは辿らない）。
    draft_advisory: set[str] = set()
    for doc_id in _draft_refinements(context_set, id_index, statement_index):
        entry = id_index[doc_id]
        for target_id in _refines_targets(entry, id_index, statement_index):
            if target_id in context_set:
                _add(doc_id, "refines", doc_id, distance.get(target_id, 0))
                break
        draft_advisory.add(doc_id)

    return context_order, edges, distance, draft_advisory


def target_expansion(
    root: str,
    purpose: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
) -> TargetExpansionResult | None:
    """単一起点への`TargetExpansion(root, purpose)`。起点を解決できなければ``None``を返す。"""

    owning_id = _owning_document_id(root, id_index, statement_index)
    if owning_id is None:
        return None
    root_entry = id_index[owning_id]

    context_order, edges, distance, draft_advisory = _interpret_closure(owning_id, id_index, statement_index)

    result = TargetExpansionResult(
        root_documents=[owning_id],
        context_documents=sorted(context_order),
        target_statements=[],
        adjacent_statements=[],
        document_edges=edges,
        document_distance=distance,
        draft_advisory=draft_advisory,
    )

    if purpose == "interpret":
        # §6.1「5.」: 置換済み起点は旧文書をadvisory、後継をreplacementとして示す
        # （後継へ暗黙に起点を差し替えない）。有効な後継が複数ならCTX-STATE-SUPERSEDED-002。
        if root_entry.kind in ("REQ", "TECH"):
            successors = _successors(owning_id, id_index, statement_index)
            if len(successors) > 1:
                result.errors = [
                    {
                        "code": "CTX-STATE-SUPERSEDED-002",
                        "severity": "error",
                        "resultStatus": "failed",
                        "summary": messages.state_superseded_multiple(owning_id),
                        "doc_id": owning_id,
                    }
                ]
                return result
            if len(successors) == 1:
                successor_id = successors[0]
                result.superseded_origin = (owning_id, successor_id)
                if successor_id not in edges:
                    edges[successor_id] = []
                    context_order.append(successor_id)
                    distance[successor_id] = distance.get(owning_id, 0)
                pair = ("supersedes", successor_id)
                if pair not in edges[successor_id]:
                    edges[successor_id].append(pair)
                result.context_documents = sorted(set(context_order))
                result.document_edges = edges
                result.document_distance = distance
        return result

    # --- implement／verify: 対象statementの決定と、TASK起点／状態検査の追加規則。 -------

    errors: list[dict] = []

    def _check_state(doc_id: str, *, is_root: bool) -> None:
        entry = id_index[doc_id]
        if entry.kind in ("REQ", "TECH"):
            successors = _successors(doc_id, id_index, statement_index)
            if len(successors) > 1:
                errors.append(
                    {
                        "code": "CTX-STATE-SUPERSEDED-002",
                        "severity": "error",
                        "resultStatus": "failed",
                        "summary": messages.state_superseded_multiple(doc_id),
                        "doc_id": doc_id,
                    }
                )
                return
            if len(successors) == 1:
                summary = (
                    messages.state_superseded_origin(doc_id, successors[0])
                    if is_root
                    else messages.state_superseded_dependency(doc_id, successors[0])
                )
                errors.append(
                    {
                        "code": "CTX-STATE-SUPERSEDED-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": summary,
                        "doc_id": doc_id,
                    }
                )
                return
            if not _is_applicable(entry):
                errors.append(
                    {
                        "code": "CTX-STATE-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": messages.state_inapplicable(doc_id),
                        "doc_id": doc_id,
                    }
                )
        elif entry.kind == "TASK":
            if entry.status == "cancelled":
                summary = (
                    messages.state_task_cancelled(doc_id) if is_root else messages.state_inapplicable(doc_id)
                )
                errors.append(
                    {
                        "code": "CTX-STATE-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": summary,
                        "doc_id": doc_id,
                    }
                )
            elif purpose == "implement" and entry.status == "done":
                errors.append(
                    {
                        "code": "CTX-STATE-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": messages.state_inapplicable(doc_id),
                        "doc_id": doc_id,
                    }
                )
        elif entry.kind == "ADR":
            # accepted ADRだけを規範的な強い依存先にできる（文書仕様 §7）。
            if entry.status != "accepted":
                errors.append(
                    {
                        "code": "CTX-STATE-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": messages.state_inapplicable(doc_id),
                        "doc_id": doc_id,
                    }
                )

    _check_state(owning_id, is_root=True)
    if root_entry.kind in ("REQ", "TECH"):
        for doc_id in context_order:
            if doc_id == owning_id or doc_id in draft_advisory:
                continue
            _check_state(doc_id, is_root=False)
    elif root_entry.kind == "TASK":
        # 関係モデル §6.2・§6.3・§10、文書仕様 §7: TASK起点の依存先も状態を検査する。
        # implementはaddresses先の所有文書とrequires閉包（既にcontext_orderにある）、
        # verifyはaddresses先の所有文書とそこからのinterpret閉包上の強い依存先を対象とする。
        dep_ids: set[str] = set()
        addressed_owning: set[str] = set()
        for ref in _addresses_targets(root_entry, id_index, statement_index):
            _target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
            if target_doc_id is not None:
                addressed_owning.add(target_doc_id)
        if purpose == "implement":
            dep_ids |= addressed_owning
            dep_ids |= {d for d in context_order if d != owning_id}
        elif purpose == "verify":
            dep_ids |= addressed_owning
            for target_doc_id in addressed_owning:
                sub_order, _e, _d, _da = _interpret_closure(target_doc_id, id_index, statement_index)
                dep_ids |= set(sub_order)
        for dep_id in sorted(dep_ids):
            if dep_id == owning_id:
                continue
            _check_state(dep_id, is_root=False)

    if root_entry.kind == "TASK" and purpose == "implement":
        for target_id in _requires_targets(root_entry, id_index, statement_index):
            target_entry = id_index.get(target_id)
            if target_entry is not None and target_entry.kind == "TASK" and target_entry.status != "done":
                errors.append(
                    {
                        "code": "CTX-TASK-DEPENDENCY-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": messages.task_dependency_incomplete(target_id),
                        "doc_id": owning_id,
                        "key": "relations.requires",
                    }
                )

    if errors:
        result.errors = errors
        return result

    if purpose == "verify" and root_entry.kind == "TASK":
        # §6.3: 起点TASKのaddresses先と当該先を所有する文書をcontextDocumentsへ含め、
        # それらからinterpretの閉包規則を適用する（起点自身のrequires閉包は含めない）。
        # 対象statement決定（`_applicable_refinement_statements`）より前に、closureを
        # addressed文書起点で組み直す必要がある。
        addressed_owning_ids: list[str] = []
        for ref in _addresses_targets(root_entry, id_index, statement_index):
            target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
            if target_doc_id is not None and target_doc_id not in addressed_owning_ids:
                addressed_owning_ids.append(target_doc_id)

        merged_order = [owning_id]
        merged_edges: dict[str, list[tuple[str, str]]] = {owning_id: []}
        merged_distance: dict[str, int] = {owning_id: 0}
        merged_draft_advisory: set[str] = set()

        for target_doc_id in addressed_owning_ids:
            sub_order, sub_edges, sub_distance, sub_draft = _interpret_closure(
                target_doc_id, id_index, statement_index
            )
            for doc_id in sub_order:
                is_new = doc_id not in merged_edges
                if is_new:
                    merged_order.append(doc_id)
                    merged_edges[doc_id] = []
                    merged_distance[doc_id] = sub_distance[doc_id] + 1
                for pair in sub_edges[doc_id]:
                    if pair not in merged_edges[doc_id]:
                        merged_edges[doc_id].append(pair)
                if doc_id in sub_draft:
                    merged_draft_advisory.add(doc_id)
            # 起点TASKからaddressed文書への到達edgeを追加する。
            if ("addresses", owning_id) not in merged_edges[target_doc_id]:
                merged_edges[target_doc_id].append(("addresses", owning_id))

        context_order = merged_order
        edges = merged_edges
        distance = merged_distance
        draft_advisory = merged_draft_advisory

    # --- 対象statementの決定（§6.4）。 -----------------------------------------

    def _ensure_in_context(doc_id: str, relation: str, source_id: str) -> None:
        """``doc_id``がまだcontextに無ければ、edge付きで追加する（refiner文書の遅延追加）。"""

        if doc_id not in edges:
            edges[doc_id] = []
            context_order.append(doc_id)
            distance[doc_id] = distance.get(owning_id, 0) + 1
        pair = (relation, source_id)
        if pair not in edges[doc_id]:
            edges[doc_id].append(pair)

    def _applicable_refinement_statements(stmt_id: str) -> list[str]:
        """``stmt_id``を(推移的に)`refines`するapplicable文書のstatementを、ID順・発見順で返す。

        refiner文書はcatalog全体（``id_index``）から探す（TASK起点の場合、refiner文書は
        起点自身のinterpret閉包に含まれていないことがあるため）。見つけた refiner文書は
        :func:`_ensure_in_context` でcontextへ追加する。
        """

        out: list[str] = []
        seen: set[str] = set()
        frontier = [stmt_id]
        while frontier:
            target = frontier.pop(0)
            candidates: list[tuple[str, DocEntry]] = []
            for cand_id, cand_entry in id_index.items():
                if cand_entry.kind not in ("REQ", "TECH") or not _is_applicable(cand_entry):
                    continue
                if target in _refines_target_statements(cand_entry, id_index, statement_index):
                    candidates.append((cand_id, cand_entry))
            # ``cand_id``はid_indexの索引key（複合workspaceでは他workspaceの候補が`ws::local`修飾
            # 形式）であり、``cand_entry.doc_id``（常にbare）ではなくこちらをcontext追跡keyに使う
            # （単一workspaceでは両者が一致するため挙動を変えない）。
            for cand_id, cand_entry in sorted(candidates, key=lambda pair: pair[0]):
                _ensure_in_context(cand_id, "refines", cand_id)
                ws_prefix = cand_id.partition("::")[0] if "::" in cand_id else None
                for stmt in cand_entry.statements:
                    sid = f"{ws_prefix}::{stmt['id']}" if ws_prefix is not None else stmt["id"]
                    if sid not in seen:
                        seen.add(sid)
                        out.append(sid)
                        frontier.append(sid)
        return out

    target_statements: list[str] = []
    adjacent_statements: list[str] = []
    target_set: set[str] = set()

    def _add_target(stmt_id: str) -> None:
        if stmt_id not in target_set:
            target_set.add(stmt_id)
            target_statements.append(stmt_id)

    if root_entry.kind == "TASK":
        # 3. TASK起点: addressesするstatementと、そのapplicable refinement。
        addressed_refs = _addresses_targets(root_entry, id_index, statement_index)
        for ref in addressed_refs:
            if ":" in ref:
                _add_target(ref)
                for s in _applicable_refinement_statements(ref):
                    _add_target(s)
    elif root_entry.statements:
        if ":" in root:
            # 2. statement起点: 指定句とそのapplicable refinement。他statementはadjacent。
            _add_target(root)
            for s in _applicable_refinement_statements(root):
                _add_target(s)
            for stmt in root_entry.statements:
                if stmt["id"] != root:
                    adjacent_statements.append(stmt["id"])
        else:
            # 1. 文書起点（規範文あり）: 所有する全statementとそのapplicable refinement。
            for stmt in root_entry.statements:
                _add_target(stmt["id"])
            for stmt in root_entry.statements:
                for s in _applicable_refinement_statements(stmt["id"]):
                    _add_target(s)
    # 5. 規範文なしTECH起点はtargetStatementsを空のままとする。

    result.target_statements = target_statements
    result.adjacent_statements = adjacent_statements

    # --- implement: 対象句をaddressesするopen TASKを追加する。TASK起点自身のaddresses／requires閉包も含める。
    if purpose == "implement":
        if root_entry.kind == "TASK":
            for ref in _addresses_targets(root_entry, id_index, statement_index):
                target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
                if target_doc_id is not None and target_doc_id not in edges:
                    edges[target_doc_id] = []
                    context_order.append(target_doc_id)
                    distance[target_doc_id] = distance.get(owning_id, 0) + 1
                if target_doc_id is not None:
                    pair = ("addresses", owning_id)
                    if pair not in edges[target_doc_id]:
                        edges[target_doc_id].append(pair)
        else:
            addressing_tasks: list[str] = []
            for cand_id, cand_entry in id_index.items():
                if cand_entry.kind != "TASK" or cand_entry.status != "open":
                    continue
                refs = _addresses_targets(cand_entry, id_index, statement_index)
                if any(r in target_set for r in refs):
                    addressing_tasks.append(cand_id)
            for task_id in sorted(addressing_tasks):
                if task_id not in edges:
                    edges[task_id] = []
                    context_order.append(task_id)
                    distance[task_id] = 1
                pair = ("addresses", task_id)
                if pair not in edges[task_id]:
                    edges[task_id].append(pair)

    result.root_documents = [owning_id]
    result.context_documents = sorted(set(context_order))
    result.document_edges = edges
    result.document_distance = distance
    result.draft_advisory = draft_advisory
    return result


def _successors(doc_id: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[str]:
    """``doc_id``を`supersedes`する有効な（applicable）後継のID一覧を辞書順で返す。"""

    entry = id_index[doc_id]
    kind = entry.kind
    out: set[str] = set()
    for cand_id, cand_entry in id_index.items():
        if cand_entry.kind != kind:
            continue
        refs = (cand_entry.frontmatter.get("relations") or {}).get("supersedes") or []
        for ref in refs:
            target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
            if target_doc_id == doc_id and target_entry is not None and target_entry.kind == kind:
                if _is_applicable(cand_entry):
                    out.add(cand_id)
                break
    return sorted(out)
