"""`TargetExpansion(root, purpose)`（関係・トレースモデル §6.1〜§6.4）。

起点から対象を展開する唯一の契約。`context`、明示対象の`check`、`verify`はこの関数を再利用する
（同 §6.4）。`purpose=interpret`は`check`の明示対象の検査が使う閉包の規則と完全に同じコードを使う
（Step 2 フェーズCで実装済み）。:func:`_interpret_closure`は閉包の集合と到達したエッジを変えずに保ち、
距離は到達元の記録から最短の段数として求める（関係・トレースモデル §7の6.。2026-10-06）。

`implement`／`verify`はStep 3で追加した。`context`だけがこれらの目的（`purpose`）を使う。返り値
:class:`TargetExpansionResult` は、`context`が必要とする追加の情報（到達したエッジ、距離、役割`advisory`として含めた、閉包内の文書を`refines`する
状態`draft`の文書の集合、状態の診断）を任意のフィールドとして保持する。`errors`が空でない場合、`context`は
完全解決を成立させず、`errors`の内容をそのまま診断へ変換して閉包全体を止める
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
    #: ``doc_id -> [(relation, source_doc_id), ...]``。`context`の`reachedBy`の計算に使う
    #: （重複排除・並べ替えは呼び出し側）。
    document_edges: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    #: ``doc_id -> 起点からの最短の到達段数``（0＝起点自身）。`context`の提示形式（`projection`）と役割（`role`）の
    #: 計算に使う。
    document_distance: dict[str, int] = field(default_factory=dict)
    #: §6.1「6.」で役割`advisory`として含めた、閉包内の文書を`refines`する、状態`draft`の文書の``doc_id``の集合。
    #: 目的`interpret`のときだけ空でない（§6.1の末尾）。
    draft_advisory: set[str] = field(default_factory=set)
    #: 目的が`implement`または`verify`のときの状態違反（§10「状態と閉包」）。空でなければ閉包を完全解決の不成立とする。
    errors: list[dict] = field(default_factory=list)
    #: 強い関係（型制約）を検査する文書の``doc_id``。目的が`implement`または`verify`のときに設定する（`contextDocuments`に加え、
    #: `verify`のTASK起点では起点の`requires`の閉包）。
    relation_scope: list[str] = field(default_factory=list)
    #: §6.1「5.」: `interpret`で起点が置換済み（有効な後継が単一）のときの``(origin_id, successor_id)``。
    #: `context`は``origin``を参考（`advisory`）、``successor``を後継（`replacement`）として示す（暗黙に差し替えはしない）。
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
    """``entry``の`relations.refines`のうち、規範文ID形式の参照の、解決済みの正規の規範文IDを返す。

    複合ワークスペースでは``ref``の綴り（宣言側の修飾形式）ではなく、``statement_index``で実際に
    解決した規範文の``dict``の``id``を正規の表現として返す（Step 5C）。同じ統合索引の中では、作業
    ワークスペース自身の規範文は常に修飾のない表現、他のワークスペースの規範文は常に`ws::local`の表現で
    一意に定まるため、これにより呼び出し側（`_applicable_refinement_statements`）の`frontier`の比較
    （修飾のない表現または修飾した表現のいずれか一方に統一された表現どうしの比較）が常に成立する。単一ワークスペースでは
    ``ref``自体が唯一の表現なので、この変更は挙動を変えない（`statement_index[ref]["id"] == ref`）。
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
    """TASKの`relations.addresses`の参照（規範文ID、または規範文のないTECHの文書ID）を返す。"""

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
    """``start_ids``からの`requires`の推移閉包を``(target_doc_id, source_doc_id)``の``list``で返す。

    ``source_doc_id``はそのエッジを宣言した文書（`requires`を持つ文書自身）。同じ参照先へ複数の経路で
    到達しても、到達した参照元ごとに1要素を返す（呼び出し側が重複排除・距離の計算を行う）。
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
    """§6.1「6.」: 閉包内の適用可能な文書またはその規範文を`refines`する、状態`draft`の文書を、役割`advisory`として含める。

    状態`draft`の文書の`requires`と、それを`refines`する文書は辿らない（`advisory`の文書は規範として
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


def _shortest_distances(owning_id: str, preds: dict[str, set[str]], fallback: dict[str, int]) -> dict[str, int]:
    """到達元の記録から、起点からの最短の段数を幅優先探索で求める（関係・トレースモデル §7の6.）。

    ``preds``は``doc_id -> {到達元のdoc_id, ...}``。閉包を作るときに辿ったエッジ1本を1段とする。到達元の記録が
    ない文書（起こらない想定）は``fallback``の値を残す。
    """

    succs: dict[str, list[str]] = {}
    for doc_id, sources in preds.items():
        for source in sources:
            succs.setdefault(source, []).append(doc_id)
    distance = {owning_id: 0}
    frontier = [owning_id]
    while frontier:
        current = frontier.pop(0)
        for doc_id in sorted(succs.get(current, [])):
            if doc_id not in distance:
                distance[doc_id] = distance[current] + 1
                frontier.append(doc_id)
    for doc_id, value in fallback.items():
        distance.setdefault(doc_id, value)
    return distance


def _interpret_closure(
    owning_id: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    *,
    include_draft: bool = True,
) -> tuple[list[str], dict[str, list[tuple[str, str]]], dict[str, int], set[str], dict[str, set[str]]]:
    """`interpret`の完全閉包を計算する（§6.1、Step 2 フェーズCから移設。閉包と到達したエッジの挙動は変更しない）。

    ``include_draft``が偽のときは§6.1の6.（`refines`する状態`draft`の文書）を適用しない。目的`implement`と`verify`は
    `draft`の文書を閉包へ含めない（§6.1の末尾）。

    戻り値は``(context_order, document_edges, document_distance, draft_advisory, preds)``。``preds``は
    ``doc_id -> {到達元のdoc_id, ...}``で、距離は閉包を作った後に``preds``から最短の段数として求める（§7の6.）。
    """

    context_set: set[str] = {owning_id}
    context_order: list[str] = [owning_id]
    edges: dict[str, list[tuple[str, str]]] = {owning_id: []}
    distance: dict[str, int] = {owning_id: 0}
    preds: dict[str, set[str]] = {}

    def _add(
        doc_id: str, relation: str, source_id: str, dist_from: int, pred: str | None = None, *, record_pred: bool = True
    ) -> None:
        # ``pred``は到達元の文書（省略時は``source_id``）。``record_pred=False``は、到達元を呼び出し側で記録する場合。
        if record_pred and doc_id != owning_id:
            preds.setdefault(doc_id, set()).add(source_id if pred is None else pred)
        is_new = doc_id not in context_set
        if is_new:
            context_set.add(doc_id)
            context_order.append(doc_id)
            distance[doc_id] = dist_from + 1
            edges[doc_id] = []
        pair = (relation, source_id)
        if pair not in edges[doc_id]:
            edges[doc_id].append(pair)

    # 2. `requires`を終端まで辿る。
    for target_id, source_id in _requires_closure([owning_id], id_index, statement_index):
        _add(target_id, "requires", source_id, distance.get(source_id, 0))

    # 3. `refines`の参照先を含める（起点自身の`refines`）。
    root_entry = id_index[owning_id]
    for target_id in _refines_targets(root_entry, id_index, statement_index):
        _add(target_id, "refines", owning_id, distance[owning_id])

    # 4. 対象を`refines`する適用可能な文書を逆参照で含め、その`requires`を辿る（推移的）。
    # 距離は参照先自身の距離+1とする（`refines`する文書をさらに`refines`する文書が正しい間接距離を持つように、
    # 参照先を幅優先探索の`frontier`として順に処理する）。
    refiner_seen: set[str] = set()
    frontier4 = [owning_id]
    refiners: list[str] = []
    while frontier4:
        target = frontier4.pop(0)
        target_dist = distance.get(target, 0)
        for cand_id, cand_entry in id_index.items():
            if cand_id == owning_id:
                continue
            if cand_entry.kind not in ("REQ", "TECH") or not _is_applicable(cand_entry):
                continue
            if target in _refines_targets(cand_entry, id_index, statement_index):
                if cand_id in refiner_seen:
                    # 2つ目以降の参照先からの到達も、最短の段数の計算のために記録する。
                    preds.setdefault(cand_id, set()).add(target)
                    continue
                refiner_seen.add(cand_id)
                _add(cand_id, "refines", cand_id, target_dist, pred=target)
                refiners.append(cand_id)
                frontier4.append(cand_id)
    # `refines`する文書の`requires`の閉包（推移的）。
    for target_id, source_id in _requires_closure(refiners, id_index, statement_index):
        _add(target_id, "requires", source_id, distance.get(source_id, 0))

    # 6. 閉包内の文書を`refines`する、状態`draft`の文書を役割`advisory`として含める（`requires`・逆方向の`refines`は辿らない）。
    draft_advisory: set[str] = set()
    closure_docs = set(context_set)
    for doc_id in (_draft_refinements(context_set, id_index, statement_index) if include_draft else []):
        entry = id_index[doc_id]
        targets = _refines_targets(entry, id_index, statement_index)
        for target_id in targets:
            if target_id in context_set:
                _add(doc_id, "refines", doc_id, distance.get(target_id, 0), record_pred=False)
                break
        # 到達元は、閉包（`draft`の文書を加える前）にある参照先のすべてとする（エッジは上の1件のまま）。`advisory`の文書を
        # `refines`する文書は辿らないので（§6.1の6.）、先に加えた`draft`の文書は到達元にしない。
        for target_id in targets:
            if target_id in closure_docs and doc_id != owning_id:
                preds.setdefault(doc_id, set()).add(target_id)
        draft_advisory.add(doc_id)

    distance = _shortest_distances(owning_id, preds, distance)
    return context_order, edges, distance, draft_advisory, preds


def target_expansion(
    root: str,
    purpose: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
) -> TargetExpansionResult | None:
    """単一の起点への`TargetExpansion(root, purpose)`。起点を解決できなければ``None``を返す。"""

    owning_id = _owning_document_id(root, id_index, statement_index)
    if owning_id is None:
        return None
    root_entry = id_index[owning_id]

    context_order, edges, distance, draft_advisory, preds = _interpret_closure(
        owning_id, id_index, statement_index, include_draft=purpose == "interpret"
    )

    def _owner(ref: str) -> str | None:
        return _resolve_ref(ref, id_index, statement_index)[1]

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
        # §6.1「5.」: 置換済みの起点は旧文書を役割`advisory`、後継を役割`replacement`として示す
        # （後継へ暗黙に起点を差し替えない）。有効な後継が複数なら`CTX-STATE-SUPERSEDED-002`。
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
                # 後継は起点から`supersedes`のエッジを1本辿って到達する（距離1）。
                preds.setdefault(successor_id, set()).add(owning_id)
                distance = _shortest_distances(owning_id, preds, distance)
                pair = ("supersedes", successor_id)
                if pair not in edges[successor_id]:
                    edges[successor_id].append(pair)
                result.context_documents = sorted(set(context_order))
                result.document_edges = edges
                result.document_distance = distance
        return result

    # --- implement／verify: 対象規範文の決定と、TASKを起点にした場合／状態検査の追加の規則。 -------

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
            elif purpose == "implement" and entry.status == "done" and is_root:
                # 文書・フロントマター・状態仕様 §7: `done`のTASKを`blocked`にするのは、目的`implement`で起点にした場合だけ。
                # 起点のTASKが`requires`する先行TASKは`done`であることが前提（関係・トレースモデル §6.2）で、未完了は
                # 下の`CTX-TASK-DEPENDENCY-001`が扱う。
                errors.append(
                    {
                        "code": "CTX-STATE-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": messages.state_inapplicable(doc_id),
                        "doc_id": doc_id,
                    }
                )
        # ADRは状態の診断を出さない。状態`accepted`でないADRへの`requires`は、関係・トレースモデル §4の状態を含む型制約であり、
        # 関係の検査が`CTX-RELATION-TYPE-001`として返す（呼び出し側は``relation_scope``の文書の強い関係を検査する）。

    _check_state(owning_id, is_root=True)
    if root_entry.kind in ("REQ", "TECH"):
        for doc_id in context_order:
            if doc_id == owning_id or doc_id in draft_advisory:
                continue
            _check_state(doc_id, is_root=False)
    elif root_entry.kind == "TASK":
        # 関係・トレースモデル §6.2・§6.3・§10、文書・フロントマター・状態仕様 §7: TASKを起点にした場合の依存先も状態を検査する。
        # `implement`は`addresses`の参照先の所有文書と`requires`の閉包（すでに`context_order`にある）、
        # `verify`は`addresses`の参照先の所有文書とそこからの`interpret`の閉包上の強い依存先に加え、コンテキストへ含めない
        # 起点の`requires`の閉包（ADRを除く）を対象とする（ADR-034の`Decision`の5番目の項目）。
        # 起点以外のTASKの状態は検査しない。先行TASKは下の`CTX-TASK-DEPENDENCY-001`が直接の参照先だけを扱い（ADR-029、ADR-036の
        # `Decision`の8番目の項目）、推移的に到達したTASKは対象にしない。
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
                sub_order, _e, _d, _da, _p = _interpret_closure(
                    target_doc_id, id_index, statement_index, include_draft=False
                )
                dep_ids |= set(sub_order)
            # ADRは除く。状態が`accepted`でないADRへの強い関係は§4の型制約（`CTX-RELATION-TYPE-001`）で扱う（関係の検査）。
            dep_ids |= {
                target_id
                for target_id, _source in _requires_closure([owning_id], id_index, statement_index)
                if target_id in id_index and id_index[target_id].kind != "ADR"
            }
        for dep_id in sorted(dep_ids):
            if dep_id == owning_id:
                continue
            dep_entry = id_index.get(dep_id)
            if dep_entry is None or dep_entry.kind == "TASK":
                continue
            _check_state(dep_id, is_root=False)

    if root_entry.kind == "TASK" and purpose in ("implement", "verify"):
        # ADR-029 Decision 1、`verify` §4の手順2: 目的`implement`と`verify`では、起点のTASKの`requires`が指すTASKがすべて`done`であることを
        # 要求する。`verify`では`requires`の閉包をコンテキストへ含めない（関係・トレースモデル §6.3）が、この検査は行う。
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

    # 状態の診断があっても閉包の構成を続け、型制約の検査の範囲（``relation_scope``）を確定してから返す。独立した元の原因は
    # それぞれ主診断を持つため、呼び出し側は状態の診断と型制約の診断の両方を返す（診断レジストリ）。
    if purpose == "verify" and root_entry.kind == "TASK":
        # §6.3: 起点のTASKの`addresses`の参照先と、当該の参照先を所有する文書を`contextDocuments`へ含め、
        # それらから`interpret`の閉包の規則を適用する（起点自身の`requires`の閉包は含めない）。
        # 対象規範文の決定（`_applicable_refinement_statements`）より前に、閉包を
        # `addresses`の参照先の文書を起点に組み直す必要がある。
        addressed_owning_ids: list[str] = []
        for ref in _addresses_targets(root_entry, id_index, statement_index):
            target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
            if target_doc_id is not None and target_doc_id not in addressed_owning_ids:
                addressed_owning_ids.append(target_doc_id)

        merged_order = [owning_id]
        merged_edges: dict[str, list[tuple[str, str]]] = {owning_id: []}
        merged_distance: dict[str, int] = {owning_id: 0}
        merged_draft_advisory: set[str] = set()
        merged_preds: dict[str, set[str]] = {}

        for target_doc_id in addressed_owning_ids:
            sub_order, sub_edges, sub_distance, sub_draft, sub_preds = _interpret_closure(
                target_doc_id, id_index, statement_index, include_draft=False
            )
            for doc_id, sources in sub_preds.items():
                merged_preds.setdefault(doc_id, set()).update(sources)
            merged_preds.setdefault(target_doc_id, set()).add(owning_id)
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
            # 起点のTASKから`addresses`の参照先の文書への、到達したエッジを追加する。
            if ("addresses", owning_id) not in merged_edges[target_doc_id]:
                merged_edges[target_doc_id].append(("addresses", owning_id))

        context_order = merged_order
        edges = merged_edges
        distance = merged_distance
        draft_advisory = merged_draft_advisory
        preds = merged_preds

    # --- 対象規範文の決定（§6.4）。 -----------------------------------------

    def _ensure_in_context(doc_id: str, relation: str, source_id: str, pred: str | None = None) -> None:
        """``doc_id``がまだコンテキストになければ、エッジ付きで追加する（`refines`する文書の遅延追加）。

        ``pred``は到達元の文書（具体化された規範文を所有する文書）で、最短の段数の計算に使う。
        """

        if pred is not None and doc_id != owning_id:
            preds.setdefault(doc_id, set()).add(pred)
        if doc_id not in edges:
            edges[doc_id] = []
            context_order.append(doc_id)
            distance[doc_id] = distance.get(owning_id, 0) + 1
        pair = (relation, source_id)
        if pair not in edges[doc_id]:
            edges[doc_id].append(pair)

    def _applicable_refinement_statements(stmt_id: str) -> list[str]:
        """``stmt_id``を（推移的に）`refines`する適用可能な文書の規範文を、ID順・発見順で返す。

        `refines`する文書はカタログ全体（``id_index``）から探す（TASKを起点にした場合、`refines`する文書は
        起点自身の`interpret`の閉包に含まれていないことがあるため）。見つけた`refines`する文書は
        :func:`_ensure_in_context` でコンテキストへ追加する。
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
            # ``cand_id``は``id_index``の索引のキー（複合ワークスペースでは他のワークスペースの候補が`ws::local`の
            # 修飾形式）であり、``cand_entry.doc_id``（常に修飾なし）ではなくこちらをコンテキストの追跡のキーに使う
            # （単一ワークスペースでは両者が一致するため挙動を変えない）。
            for cand_id, cand_entry in sorted(candidates, key=lambda pair: pair[0]):
                _ensure_in_context(cand_id, "refines", cand_id, pred=_owner(target))
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
        # 3. TASKを起点にした場合: `addresses`する規範文と、その具体化文書の規範文。
        addressed_refs = _addresses_targets(root_entry, id_index, statement_index)
        for ref in addressed_refs:
            if ":" in ref:
                _add_target(ref)
                for s in _applicable_refinement_statements(ref):
                    _add_target(s)
    elif root_entry.statements:
        if ":" in root:
            # 2. 規範文を起点にした場合: 指定した規範文とその具体化文書の規範文。ほかの規範文は隣接規範文（`adjacentStatements`）。
            _add_target(root)
            for s in _applicable_refinement_statements(root):
                _add_target(s)
            for stmt in root_entry.statements:
                if stmt["id"] != root:
                    adjacent_statements.append(stmt["id"])
        else:
            # 1. 文書を起点にした場合（規範文あり）: 所有するすべての規範文とその具体化文書の規範文。
            for stmt in root_entry.statements:
                _add_target(stmt["id"])
            for stmt in root_entry.statements:
                for s in _applicable_refinement_statements(stmt["id"]):
                    _add_target(s)
    # 5. 規範文のないTECHを起点にした場合は`targetStatements`を空のままとする。

    result.target_statements = target_statements
    result.adjacent_statements = adjacent_statements

    # --- implement: 対象規範文を`addresses`する、状態`open`のTASKを追加する。TASKを起点にした場合は、その起点自身の`addresses`／`requires`の閉包も含める。
    if purpose == "implement":
        if root_entry.kind == "TASK":
            for ref in _addresses_targets(root_entry, id_index, statement_index):
                target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
                if target_doc_id is not None and target_doc_id not in edges:
                    edges[target_doc_id] = []
                    context_order.append(target_doc_id)
                    distance[target_doc_id] = distance.get(owning_id, 0) + 1
                if target_doc_id is not None:
                    if target_doc_id != owning_id:
                        preds.setdefault(target_doc_id, set()).add(owning_id)
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
                # TASKは、`addresses`する対象規範文を所有する文書から1段で到達する。
                for ref in _addresses_targets(id_index[task_id], id_index, statement_index):
                    owner = _owner(ref) if ref in target_set else None
                    if owner is not None and task_id != owning_id:
                        preds.setdefault(task_id, set()).add(owner)
                pair = ("addresses", task_id)
                if pair not in edges[task_id]:
                    edges[task_id].append(pair)

    result.root_documents = [owning_id]
    result.context_documents = sorted(set(context_order))
    result.document_edges = edges
    result.document_distance = _shortest_distances(owning_id, preds, distance)
    result.draft_advisory = draft_advisory
    # 呼び出し側の関係の検査は、コンテキストの文書のうち起点ワークスペースが所有するもの（修飾のないID）が宣言する関係を対象にする。
    result.relation_scope = sorted(set(context_order))
    # その検査が見ない文書（複合ワークスペースの他のメンバーの文書と、目的`verify`でTASKを起点にした場合のコンテキストへ含めない
    # 起点の`requires`の閉包）については、閉包を構成する`requires`の辺の型制約だけをここで検査する。状態が`accepted`でないADRへの
    # `requires`は、関係・トレースモデル §4の状態を含む型制約である（同 §6.3、ユーザー決定）。
    extra = set(context_order)
    if purpose == "verify" and root_entry.kind == "TASK":
        extra |= {target_id for target_id, _source in _requires_closure([owning_id], id_index, statement_index)}
    covered = {d for d in context_order if "::" not in d}
    for doc_id in sorted(extra - covered):
        errors.extend(_adr_requires_type_errors(doc_id, id_index, statement_index))
    result.errors = errors
    return result


def _adr_requires_type_errors(doc_id: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[dict]:
    """``doc_id``の`requires`のうち、状態が`accepted`でないADRを指すものを`CTX-RELATION-TYPE-001`の候補として返す。

    診断の形は関係の検査（`relations.check_relations`）と同じにする。発生元は関係を宣言した文書の`relations.requires`、
    ``evidence``は宣言した参照先（複合ワークスペースの他のメンバーの文書では、そのメンバーの中で書いた修飾のない形）。
    """

    entry = id_index.get(doc_id)
    if entry is None:
        return []
    owner = doc_id.partition("::")[0] if "::" in doc_id else None
    out: list[dict] = []
    for ref in (entry.frontmatter.get("relations") or {}).get("requires") or []:
        if not isinstance(ref, str):
            continue
        target_entry, _target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None or target_entry.kind != "ADR" or target_entry.status == "accepted":
            continue
        evidence = ref[len(owner) + 2 :] if owner is not None and ref.startswith(f"{owner}::") else ref
        out.append(
            {
                "code": "CTX-RELATION-TYPE-001",
                "severity": "error",
                "resultStatus": "failed",
                "summary": messages.relation_type_mismatch(entry.kind, target_entry.kind, "requires"),
                "doc_id": doc_id,
                "key": "relations.requires",
                "evidence": evidence,
            }
        )
    return out


def _successors(doc_id: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[str]:
    """``doc_id``を`supersedes`する有効な（適用可能な）後継のID一覧を辞書順で返す。"""

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
