"""`TargetExpansion(root, purpose)`（関係・トレースモデル §6.1〜§6.4、ADR-071）。

起点から対象を展開する唯一の契約。`context`、明示対象の`check`、`verify`はこの関数を再利用する
（同 §6.4）。閉包（`contextDocuments`）は、下方向の出発点から下方向へ具体化（`refines`の逆向き）を辿り、そこから上方向へ
依存（`requires`、`refines`、`addresses`の参照先）を終端まで辿って得る（:func:`_closure`。ADR-071 Decision 2）。下方向の出発点と
具体化文書の集合をSとすると、閉包はSとSの上方向の閉包の和集合である。上方向の辺がSの文書へ戻る場合は、その文書へ着いたとはみなさず、
役割・到達したエッジ・距離に使わない。距離は到達元の記録から最短の段数として求める（同 §7の6.）。

目的`interpret`・`implement`・`verify`は同じ閉包の関数を使う。違いは次の3点だけである。TASKを起点にするとき、起点のTASKの`requires`を
閉包に含めるのは`interpret`と`implement`で、`verify`は含めずに適用可能性の検査だけを行う（:attr:`_Closure.check_only`）。
状態`draft`の文書を役割`advisory`として示すのは`interpret`だけで、Sの文書（またはその規範文）を`refines`する`draft`の文書に限る。
`implement`は対象規範文を`addresses`する状態`open`のTASKを閉包へ加える（起点がTASKのときは加えない）。

返り値 :class:`TargetExpansionResult` は、`context`が必要とする追加の情報（到達したエッジ、距離、役割`advisory`の文書の集合、状態の診断）を
任意のフィールドとして保持する。`errors`が空でない場合、`context`は完全解決を成立させず、`errors`の内容をそのまま診断へ変換して
閉包全体を止める（関係・トレースモデル §10「状態と閉包」）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import messages
from . import relations as relations_mod
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
    #: §6.1「6.」で役割`advisory`として含めた、S（下方向の出発点と具体化文書）の文書またはその規範文を`refines`する、状態`draft`の文書の
    #: ``doc_id``の集合。目的`interpret`のときだけ空でない（§6.1の末尾）。
    draft_advisory: set[str] = field(default_factory=set)
    #: 目的が`implement`または`verify`のときの状態違反（§10「状態と閉包」）。空でなければ閉包を完全解決の不成立とする。
    errors: list[dict] = field(default_factory=list)
    #: 強い関係（型制約）を検査する文書の``doc_id``。目的が`implement`または`verify`のときに設定する（`contextDocuments`。
    #: `verify`のTASK起点で、コンテキストへ含めない起点の`requires`の上方向の範囲は、:func:`_adr_type_errors`が`requires`の型制約だけを検査する）。
    relation_scope: list[str] = field(default_factory=list)
    #: §6.1「5.」: `interpret`で起点が置換済み（有効な後継が単一）のときの``(origin_id, successor_id)``。
    #: `context`は``origin``を参考（`advisory`）、``successor``を後継（`replacement`）として示す（暗黙に差し替えはしない）。
    superseded_origin: tuple[str, str] | None = None
    #: 閉包を作るときに辿った文書のID（`contextDocuments`に加え、`verify`のTASK起点でコンテキストへ含めない起点の`requires`の上方向の範囲、
    #: 有効な後継が複数あるときのすべての後継、閉包の文書が`supersedes`で置き換える旧文書）。文書IDの重複を、閉包を作るときに辿るIDについて返すために使う
    #: （関係・トレースモデル §5.1、確認事項C96。:mod:`bitz.dupclosure`）。`related`の参照先は辿らないので含まない。
    traversed_documents: list[str] = field(default_factory=list)


def _is_applicable(entry: DocEntry) -> bool:
    return entry.status in APPLICABLE_STATUS.get(entry.kind, set())


def _canonical_items(id_index: dict[str, DocEntry]) -> list[tuple[str, DocEntry]]:
    """``id_index``の``(キー, DocEntry)``のうち、別名のキーを除いたものを索引の順に``list``で返す。

    複合ワークスペースの統合索引は、作業ワークスペースの文書を修飾のないID（正規）と`<作業ワークスペース>::<ID>`（別名）の
    2つのキーで同じDocEntryへ登録する。全文書を走査する処理（逆参照、`supersedes`の後継）が別名のキーも数えると、
    同じ文書を2回数え、閉包へ2つのIDで収録する（関係・トレースモデル §7「同一の文書が複数の経路から到達しても
    1回だけ収録し」）。修飾のないキーが同じDocEntryを指す修飾キーを別名として除く。他のワークスペースの文書
    （修飾のないキーが無いか、別のDocEntry）は除かない。単一ワークスペースは修飾キーを持たず、挙動を変えない。

    索引の全キーを絞り込むため、全文書の走査のたびに呼ぶと閉包の文書数に比例して重くなる。`target_expansion`が冒頭で
    1回だけ計算し、各走査へ渡す（索引は`target_expansion`の実行中に変わらない）。
    """

    return [
        (key, entry)
        for key, entry in id_index.items()
        if not ("::" in key and id_index.get(key.partition("::")[2]) is entry)
    ]


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


def _refines_target_documents(
    entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[str]:
    """``entry``の`relations.refines`のうち、文書ID形式の参照（規範文IDでない参照）の、解決済みの文書IDを返す。"""

    if entry.kind not in ("REQ", "TECH"):
        return []
    allowed = RELATION_ALLOWED_TARGET_KINDS.get((entry.kind, "refines"), set())
    refs = (entry.frontmatter.get("relations") or {}).get("refines") or []
    out: list[str] = []
    for ref in refs:
        # 修飾（`ws::`）を外した字句に`:`があれば規範文IDである（文書IDは`:`を含まない）。
        if not isinstance(ref, str) or ":" in ref.rpartition("::")[2]:
            continue
        target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None or target_entry.kind not in allowed or target_doc_id in out:
            continue
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
    """TASKの`relations.addresses`の参照（規範文ID、または規範文のないTECHの文書ID）を、解決済みの正規の表現で返す。

    ``_refines_target_statements``と同じく、宣言側の綴りではなく索引で解決した正規の表現を返す。作業ワークスペース自身を
    修飾した別名（`<作業ワークスペース>::<ID>`）で書いた参照も修飾のない表現にそろい、対象規範文（`target_set`）や
    起点の規範文との比較が一致する（同じ実体を2つの表現で扱わない）。別名でない参照は``ref``のまま＝挙動を変えない。
    """

    if entry.kind != "TASK":
        return []
    allowed = RELATION_ALLOWED_TARGET_KINDS.get((entry.kind, "addresses"), set())
    refs = (entry.frontmatter.get("relations") or {}).get("addresses") or []
    out: list[str] = []
    for ref in refs:
        target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None or target_entry.kind not in allowed:
            continue
        stmt = statement_index.get(ref)
        canonical_id = stmt["id"] if stmt is not None else target_doc_id
        if canonical_id not in out:
            out.append(canonical_id)
    return out


@dataclass
class _RefineIndex:
    """適用可能な文書がどの文書・規範文を`refines`するかの逆引き（``target_expansion``の1回の呼び出しで1度だけ作る）。

    閉包の下方向（:func:`_closure`）と、対象規範文の具体化の展開（``_applicable_refinement_statements``）が、文書の全体を何度も走査せずに使う。
    値は、適用可能なREQ／TECHの索引のキーの``list``（``canonical``の順）。
    """

    #: 参照先の文書ID（規範文IDの参照はその所有文書）-> `refines`する文書。
    by_owner: dict[str, list[str]]
    #: 参照先の規範文ID（正規の表現）-> 規範文IDで`refines`する文書。
    by_statement: dict[str, list[str]]
    #: 参照先の文書ID（文書ID形式の参照だけ）-> 文書IDで`refines`する文書。
    by_document: dict[str, list[str]]


def _refine_index(
    canonical: list[tuple[str, DocEntry]], id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> _RefineIndex:
    index = _RefineIndex({}, {}, {})
    for cand_id, cand_entry in canonical:
        if cand_entry.kind not in ("REQ", "TECH") or not _is_applicable(cand_entry):
            continue
        for target in _refines_targets(cand_entry, id_index, statement_index):
            index.by_owner.setdefault(target, []).append(cand_id)
        for target in _refines_target_statements(cand_entry, id_index, statement_index):
            index.by_statement.setdefault(target, []).append(cand_id)
        for target in _refines_target_documents(cand_entry, id_index, statement_index):
            index.by_document.setdefault(target, []).append(cand_id)
    return index


def _draft_refinements(
    selected_ids: set[str],
    context_ids: set[str],
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    canonical: list[tuple[str, DocEntry]],
) -> list[str]:
    """§6.1の6.（ADR-071 Decision 2の3.）: S（``selected_ids``。下方向の出発点と具体化文書）の文書またはその規範文を`refines`する、
    状態`draft`の文書を、役割`advisory`として含めるために返す。

    閉包のすべての文書からは辿らない（上方向で着いた文書の`draft`の具体化文書は含めない）。すでに閉包にある文書（``context_ids``）は返さない。
    `advisory`の文書は規範として適用しないので、その`requires`と、それを`refines`する文書は辿らない。
    """

    advisory: list[str] = []
    for cand_id, cand_entry in canonical:
        if cand_id in context_ids:
            continue
        if cand_entry.kind not in ("REQ", "TECH") or cand_entry.status != "draft":
            continue
        if any(t in selected_ids for t in _refines_targets(cand_entry, id_index, statement_index)):
            advisory.append(cand_id)
    return advisory


def _upward_targets(entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[tuple[str, str]]:
    """上方向の辺（ADR-071 Decision 2の1.）: ``entry``から`requires`・`refines`・`addresses`の参照先を``(relation, 参照先の文書ID)``で返す。

    規範文IDの参照は、その所有文書にする。辺の種類は区別せず終端まで辿る対象であり、`supersedes`と`related`は含めない。
    """

    out: list[tuple[str, str]] = []
    for target_id in _requires_targets(entry, id_index, statement_index):
        out.append(("requires", target_id))
    for target_id in _refines_targets(entry, id_index, statement_index):
        out.append(("refines", target_id))
    for ref in _addresses_targets(entry, id_index, statement_index):
        _target_entry, owner = _resolve_ref(ref, id_index, statement_index)
        if owner is not None:
            out.append(("addresses", owner))
    return out


def _upward_reach(
    start_ids: list[str], id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[tuple[str, str, str]]:
    """``start_ids``から上方向の辺を終端まで辿った``(relation, 参照先の文書ID, 宣言した文書ID)``を返す（辺ごとに1要素）。

    同じ参照先へ複数の経路で到達しても、辺ごとに1要素を返す（呼び出し側が重複排除と、Sへ戻る辺の除外を行う）。
    """

    edges: list[tuple[str, str, str]] = []
    seen: set[str] = set(start_ids)
    frontier = list(start_ids)
    while frontier:
        cur = frontier.pop(0)
        entry = id_index.get(cur)
        if entry is None:
            continue
        for relation, target_id in _upward_targets(entry, id_index, statement_index):
            edges.append((relation, target_id, cur))
            if target_id not in seen:
                seen.add(target_id)
                frontier.append(target_id)
    return edges


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


@dataclass
class _Closure:
    """:func:`_closure`の結果。"""

    #: 閉包の文書（起点を先頭に、到達順）。
    order: list[str]
    #: ``doc_id -> [(relation, 宣言した文書のdoc_id), ...]``（到達したエッジ）。
    edges: dict[str, list[tuple[str, str]]]
    #: ``doc_id -> 起点からの最短の段数``。
    distance: dict[str, int]
    #: 役割`advisory`として含めた、状態`draft`の文書（目的`interpret`だけ）。
    draft_advisory: set[str]
    #: ``doc_id -> {到達元のdoc_id, ...}``。距離の計算と、後から加える文書の到達元の記録に使う。
    preds: dict[str, set[str]]
    #: 目的`verify`でTASKを起点にしたときの、コンテキストへ含めず、適用可能性と型制約だけを検査する文書
    #: （起点のTASKの`requires`の上方向の範囲のうち、閉包にないもの）。
    check_only: set[str]


def _closure(
    owning_id: str,
    purpose: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    canonical: list[tuple[str, DocEntry]],
    refiners: _RefineIndex,
) -> _Closure:
    """閉包を計算する（関係・トレースモデル §6.1、ADR-071 Decision 2）。

    1. 下方向の出発点: 起点がTASKなら、その`addresses`の参照先の所有文書（距離1）。それ以外は起点文書自身。
    2. 下方向: 出発点の文書またはそのいずれかの規範文を`refines`する適用可能な文書を、逆向きに終端まで辿る。出発点と合わせてS。
       上方向で着いた文書からは、下方向へ辿らない。
    3. 上方向: Sの文書から、`requires`・`refines`・`addresses`の参照先を、辺の種類を区別せず終端まで辿る。辺がSの文書へ戻る場合は、
       その文書へ着いたとはみなさず、到達したエッジも到達元（距離）も記録しない。
    4. 起点がTASKなら、起点のTASKの`requires`の参照先と、その上方向の閉包を含める。`verify`は含めず（``check_only``）、適用可能性の検査だけを行う。
    5. 目的`interpret`だけ、Sの文書またはその規範文を`refines`する状態`draft`の文書を、役割`advisory`として含める。

    ``canonical``は別名を除いた索引の``(キー, DocEntry)``（:func:`_canonical_items`）。``refiners``は`refines`の逆引き。
    """

    root_entry = id_index[owning_id]
    is_task = root_entry.kind == "TASK"
    context_set: set[str] = {owning_id}
    order: list[str] = [owning_id]
    edges: dict[str, list[tuple[str, str]]] = {owning_id: []}
    preds: dict[str, set[str]] = {}

    def _add(doc_id: str, relation: str, source_id: str, pred: str | None = None) -> None:
        # ``pred``は到達元の文書（省略時は``source_id``）。距離は、``preds``から最短の段数として後で求める。
        if doc_id != owning_id:
            preds.setdefault(doc_id, set()).add(source_id if pred is None else pred)
        if doc_id not in context_set:
            context_set.add(doc_id)
            order.append(doc_id)
            edges[doc_id] = []
        pair = (relation, source_id)
        if pair not in edges[doc_id]:
            edges[doc_id].append(pair)

    # 1. 下方向の出発点。
    starts: list[str] = [] if is_task else [owning_id]
    if is_task:
        for ref in _addresses_targets(root_entry, id_index, statement_index):
            _target_entry, owner = _resolve_ref(ref, id_index, statement_index)
            if owner is not None and owner not in starts:
                starts.append(owner)
                _add(owner, "addresses", owning_id)

    # 2. 下方向。出発点の文書またはその規範文を`refines`する適用可能な文書を、終端まで辿る。
    selected: set[str] = set(starts)
    frontier = list(starts)
    while frontier:
        target = frontier.pop(0)
        for cand_id in sorted(refiners.by_owner.get(target, [])):
            if cand_id == owning_id:
                continue
            _add(cand_id, "refines", cand_id, pred=target)
            if cand_id not in selected:
                selected.add(cand_id)
                frontier.append(cand_id)

    # 3.・4. 上方向。TASKを起点にした`interpret`と`implement`は、起点のTASK自身も出発点にして、その`requires`を辿る。
    up_starts = list(order)
    if is_task and purpose == "verify":
        up_starts.remove(owning_id)
    for relation, target_id, source_id in _upward_reach(up_starts, id_index, statement_index):
        if target_id not in selected:
            _add(target_id, relation, source_id)

    # 4. `verify`で起点のTASKの`requires`の上方向の範囲は、コンテキストへ含めない。適用可能性と型制約の検査の範囲だけにする。
    check_only: set[str] = set()
    if is_task and purpose == "verify":
        required = _requires_targets(root_entry, id_index, statement_index)
        reach = {target_id for _relation, target_id, _source in _upward_reach(required, id_index, statement_index)}
        check_only = (reach | set(required)) - context_set

    # 5. 状態`draft`の文書を役割`advisory`として含める。到達元は、Sにある参照先のすべてとする（エッジは1件）。
    draft_advisory: set[str] = set()
    if purpose == "interpret":
        for doc_id in _draft_refinements(selected, context_set, id_index, statement_index, canonical):
            sources = [t for t in _refines_targets(id_index[doc_id], id_index, statement_index) if t in selected]
            _add(doc_id, "refines", doc_id, pred=sources[0])
            preds[doc_id].update(sources)
            draft_advisory.add(doc_id)

    fallback = {doc_id: 1 for doc_id in order}
    distance = _shortest_distances(owning_id, preds, fallback)
    return _Closure(order, edges, distance, draft_advisory, preds, check_only)


def target_expansion(
    root: str,
    purpose: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    *,
    active_ws_id: str | None = None,
) -> TargetExpansionResult | None:
    """単一の起点への`TargetExpansion(root, purpose)`。起点を解決できなければ``None``を返す。

    ``active_ws_id``は複合ワークスペースの作業ワークスペースのID（単一ワークスペースでは``None``）。渡すと、`CTX-STATE-SUPERSEDED-*`の
    `summary`に差し込む文書IDを複合ワークスペースの正規形式（`ws::local`）にする（複合ワークスペース仕様 §4。索引の
    作業ワークスペースの文書は修飾のないID、他のワークスペースの文書は修飾済み）。``None``なら今までどおり修飾しない。
    """

    owning_id = _owning_document_id(root, id_index, statement_index)
    if owning_id is None:
        return None
    root_entry = id_index[owning_id]
    canonical = _canonical_items(id_index)

    def _display_id(doc_id: str) -> str:
        """診断の`summary`に差し込む文書ID。複合ワークスペースでは修飾のないIDを作業ワークスペースで修飾する。"""

        return doc_id if active_ws_id is None or "::" in doc_id else f"{active_ws_id}::{doc_id}"

    refiners = _refine_index(canonical, id_index, statement_index)
    closure = _closure(owning_id, purpose, id_index, statement_index, canonical, refiners)
    context_order, edges, distance, draft_advisory, preds = (
        closure.order, closure.edges, closure.distance, closure.draft_advisory, closure.preds
    )
    check_only = closure.check_only

    def _owner(ref: str) -> str | None:
        return _resolve_ref(ref, id_index, statement_index)[1]

    def _adr_type_errors(context_ids: list[str], extra_ids: set[str]) -> list[dict]:
        """呼び出し側の関係の検査が見ない文書の`requires`のうち、状態が`accepted`でないADRを指すものを返す（全目的で共通）。

        呼び出し側の関係の検査は、コンテキストの文書のうち起点ワークスペースが所有するもの（修飾のないID）が宣言する関係を
        対象にする。その検査が見ない文書（複合ワークスペースの他のメンバーの文書。目的`verify`でTASKを起点にした場合のコンテキストへ
        含めない起点の`requires`の上方向の範囲は``extra_ids``で渡す）については、閉包を構成する`requires`の辺の型制約だけをここで検査する。
        状態が`accepted`でないADRへの`requires`は、関係・トレースモデル §4の状態を含む型制約である（同 §6.3、ユーザー決定）。
        目的`interpret`でも同じ辺を同じ診断にする（単一ワークスペースの`interpret`は関係の検査が同じ辺を検出する）。
        """

        # 複合ワークスペースの統合索引は、起点ワークスペースの文書にも修飾形の別名（`<起点>::<ID>`）を登録するため、同じ文書が
        # 2つのIDで閉包へ入り得る。同じ辺の診断を2件返さないよう、文書の実体で判定する（診断レジストリ: 同じ原因から同義の診断を複数生成しない）。
        covered = {id(id_index[d]) for d in context_ids if "::" not in d and d in id_index}
        found: list[dict] = []
        for doc_id in sorted(extra_ids):
            entry = id_index.get(doc_id)
            if entry is None or id(entry) in covered:
                continue
            covered.add(id(entry))
            found.extend(_adr_requires_type_errors(doc_id, id_index, statement_index))
        return found

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
            successors = _successors(owning_id, id_index, statement_index, canonical)
            if len(successors) > 1:
                result.traversed_documents = sorted(
                    set(context_order) | set(successors) | _superseded_documents(context_order, id_index, statement_index)
                )
                result.errors = [
                    {
                        "code": "CTX-STATE-SUPERSEDED-002",
                        "severity": "error",
                        "resultStatus": "failed",
                        "summary": messages.state_superseded_multiple(_display_id(owning_id)),
                        "doc_id": owning_id,
                    }
                ]
                result.errors += _adr_type_errors(context_order, set(context_order))
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
        result.errors = _adr_type_errors(context_order, set(context_order))
        result.traversed_documents = sorted(
            set(result.context_documents) | _superseded_documents(result.context_documents, id_index, statement_index)
        )
        return result

    # --- implement／verify: 対象規範文の決定と、TASKを起点にした場合／状態検査の追加の規則。 -------

    errors: list[dict] = []
    #: 状態の検査で`supersedes`により見つけた後継（コンテキストへは含めないが、閉包を作るときに辿る）。
    successor_ids: set[str] = set()

    def _check_state(doc_id: str, *, is_root: bool) -> None:
        entry = id_index[doc_id]
        if entry.kind in ("REQ", "TECH"):
            successors = _successors(doc_id, id_index, statement_index, canonical)
            successor_ids.update(successors)
            if len(successors) > 1:
                errors.append(
                    {
                        "code": "CTX-STATE-SUPERSEDED-002",
                        "severity": "error",
                        "resultStatus": "failed",
                        "summary": messages.state_superseded_multiple(_display_id(doc_id)),
                        "doc_id": doc_id,
                    }
                )
                return
            if len(successors) == 1:
                summary = (
                    messages.state_superseded_origin(_display_id(doc_id), _display_id(successors[0]))
                    if is_root
                    else messages.state_superseded_dependency(_display_id(doc_id), _display_id(successors[0]))
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
                        "summary": messages.state_inapplicable(_display_id(doc_id), entry.status, purpose),
                        "doc_id": doc_id,
                    }
                )
        elif entry.kind == "TASK":
            if entry.status == "cancelled":
                errors.append(
                    {
                        "code": "CTX-STATE-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": messages.state_inapplicable(_display_id(doc_id), entry.status, purpose),
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
                        "summary": messages.state_inapplicable(_display_id(doc_id), entry.status, purpose),
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
        # `implement`は閉包（`addresses`の参照先の所有文書とその具体化文書、それらの上方向の閉包、起点のTASKの`requires`の上方向の閉包。
        # すべて``context_order``にある）、`verify`は`requires`を除く同じ閉包（``context_order``）に加え、コンテキストへ含めない
        # 起点の`requires`の上方向の範囲（``check_only``。ADRを除く）を対象とする（ADR-034の`Decision`の5番目の項目、ADR-071）。
        # 起点以外のTASKの状態は検査しない。先行TASKは下の`CTX-TASK-DEPENDENCY-001`が直接の参照先だけを扱い（ADR-029、ADR-036の
        # `Decision`の8番目の項目）、推移的に到達したTASKは対象にしない。
        dep_ids: set[str] = set()
        addressed_owning: set[str] = set()
        for ref in _addresses_targets(root_entry, id_index, statement_index):
            _target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
            if target_doc_id is not None:
                addressed_owning.add(target_doc_id)
        dep_ids |= addressed_owning
        dep_ids |= {d for d in context_order if d != owning_id}
        if purpose == "verify":
            # ADRは除く。状態が`accepted`でないADRへの強い関係は§4の型制約（`CTX-RELATION-TYPE-001`）で扱う（関係の検査）。
            dep_ids |= {d for d in check_only if d in id_index and id_index[d].kind != "ADR"}
        for dep_id in sorted(dep_ids):
            if dep_id == owning_id:
                continue
            dep_entry = id_index.get(dep_id)
            if dep_entry is None or dep_entry.kind == "TASK":
                continue
            _check_state(dep_id, is_root=False)

    if root_entry.kind == "TASK" and purpose in ("implement", "verify"):
        # ADR-029 Decision 1、`verify` §4の手順2: 目的`implement`と`verify`では、起点のTASKの`requires`が指すTASKがすべて`done`であることを
        # 要求する。`verify`では`requires`の上方向の範囲をコンテキストへ含めない（関係・トレースモデル §6.3）が、この検査は行う。
        for target_id in _requires_targets(root_entry, id_index, statement_index):
            target_entry = id_index.get(target_id)
            if target_entry is not None and target_entry.kind == "TASK" and target_entry.status != "done":
                errors.append(
                    {
                        "code": "CTX-TASK-DEPENDENCY-001",
                        "severity": "error",
                        "resultStatus": "blocked",
                        "summary": messages.task_dependency_incomplete(_display_id(target_id), target_entry.status),
                        "suggestedAction": messages.task_dependency_suggested_action(_display_id(target_id)),
                        "doc_id": owning_id,
                        "key": "relations.requires",
                    }
                )

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

    def _applicable_refinement_statements(stmt_ids: list[str], *, origin_doc: str | None = None) -> list[str]:
        """``stmt_ids``の具体化文書の規範文を、推移的な具体化を終端まで辿って、ID順・発見順で返す（§6.4）。

        具体化文書は「選択した文書または規範文を`refines`する適用可能な文書」（用語集、§6.4）である。規範文を規範文IDで
        `refines`する文書を見つけたら、その文書の規範文と、その文書自身を次の選択とし、規範文IDの`refines`と文書IDの`refines`の
        両方で辿る（確認事項C54。どの起点でも同じ）。``origin_doc``は規則1（文書を起点にした場合）の起点の文書で、
        起点の文書を文書IDで`refines`する文書も含める。規則2・3の起点の文書は、文書IDの`refines`の起点にしない。

        `refines`する文書はカタログ全体（``id_index``）から探す。見つけた`refines`する文書は、閉包の下方向（:func:`_closure`の2.）で
        すでにコンテキストにあるはずだが、念のため :func:`_ensure_in_context` で（なければ）追加する。
        """

        out: list[str] = []
        seen_statements: set[str] = set()
        seen_documents: set[str] = set()
        # ``frontier``の要素は``("statement", 規範文ID)``または``("document", 文書ID)``。
        frontier: list[tuple[str, str]] = [("statement", stmt_id) for stmt_id in stmt_ids]
        if origin_doc is not None:
            seen_documents.add(origin_doc)
            frontier.append(("document", origin_doc))
        while frontier:
            kind, target = frontier.pop(0)
            candidates = refiners.by_statement.get(target, []) if kind == "statement" else refiners.by_document.get(target, [])
            # ``cand_id``は``id_index``の索引のキー（複合ワークスペースでは他のワークスペースの候補が`ws::local`の
            # 修飾形式）であり、``cand_entry.doc_id``（常に修飾なし）ではなくこちらをコンテキストの追跡のキーに使う
            # （単一ワークスペースでは両者が一致するため挙動を変えない）。
            for cand_id in sorted(candidates):
                cand_entry = id_index[cand_id]
                _ensure_in_context(cand_id, "refines", cand_id, pred=_owner(target) if kind == "statement" else target)
                ws_prefix = cand_id.partition("::")[0] if "::" in cand_id else None
                for stmt in cand_entry.statements:
                    sid = f"{ws_prefix}::{stmt['id']}" if ws_prefix is not None else stmt["id"]
                    if sid not in seen_statements:
                        seen_statements.add(sid)
                        out.append(sid)
                        frontier.append(("statement", sid))
                if cand_id not in seen_documents:
                    seen_documents.add(cand_id)
                    frontier.append(("document", cand_id))
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
            # 規範文IDかどうかは索引で判定する（複合ワークスペースの修飾ID`ws::TECH-010`も`:`を含むため）。規範文のないTECHの文書IDは
            # 対象規範文を増やさず、`verify`の文書単位のテスト割当てとする（§6.4の規則3）。
            if ref in statement_index:
                _add_target(ref)
                for s in _applicable_refinement_statements([ref]):
                    _add_target(s)
    elif root_entry.statements:
        if ":" in root:
            # 2. 規範文を起点にした場合: 指定した規範文とその具体化文書の規範文。ほかの規範文は隣接規範文（`adjacentStatements`）。
            _add_target(root)
            for s in _applicable_refinement_statements([root]):
                _add_target(s)
            for stmt in root_entry.statements:
                if stmt["id"] != root:
                    adjacent_statements.append(stmt["id"])
        else:
            # 1. 文書を起点にした場合（規範文あり）: 所有するすべての規範文とその具体化文書の規範文。
            for stmt in root_entry.statements:
                _add_target(stmt["id"])
            for s in _applicable_refinement_statements([stmt["id"] for stmt in root_entry.statements], origin_doc=owning_id):
                _add_target(s)
    # 5. 規範文のないTECHを起点にした場合は`targetStatements`を空のままとする。

    result.target_statements = target_statements
    result.adjacent_statements = adjacent_statements

    # --- implement: 対象規範文を`addresses`する、状態`open`のTASKを追加する（役割`work`。そのTASKはSに入れず、そのTASKからは辿らない）。
    # 起点がTASKのときは加えない。起点のTASKの`addresses`の参照先と`requires`の上方向の閉包は、すでに閉包に含まれている（ADR-071 Decision 2の4.）。
    if purpose == "implement" and root_entry.kind != "TASK":
        addressing_tasks: list[str] = []
        for cand_id, cand_entry in canonical:
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
    # 呼び出し側の関係の検査が見ない文書の`requires`の型制約は、`_adr_type_errors`が検査する。
    result.relation_scope = sorted(set(context_order))
    extra = set(context_order) | check_only
    errors.extend(_adr_type_errors(context_order, extra))
    result.errors = errors
    result.traversed_documents = sorted(extra | successor_ids | _superseded_documents(extra, id_index, statement_index))
    return result


def _adr_requires_type_errors(doc_id: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[dict]:
    """``doc_id``の`requires`のうち、状態が`accepted`でないADRを指すものを`CTX-RELATION-TYPE-001`の候補として返す。

    診断の形は関係の検査（`relations.check_relations`）と同じにする。発生元は関係を宣言した文書の`relations.requires`、
    ``evidence``は宣言どおりの参照先（結果・診断・終了コード §4）。複合ワークスペースの他のメンバーの文書は、解決のために
    参照先を修飾したビューを索引へ置くため、修飾する前の宣言（``declared_requires``）の綴りを返す
    （そのメンバー自身のワークスペースを修飾して書いた参照も、非修飾で書いた参照も、書いたとおりになる）。
    """

    entry = id_index.get(doc_id)
    if entry is None:
        return []
    refs = (entry.frontmatter.get("relations") or {}).get("requires") or []
    declared = entry.declared_requires if entry.declared_requires is not None else refs
    out: list[dict] = []
    for ref, evidence in zip(refs, declared):
        if not isinstance(ref, str):
            continue
        target_entry, _target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None or target_entry.kind != "ADR" or target_entry.status == "accepted":
            continue
        out.append(
            {
                "code": "CTX-RELATION-TYPE-001",
                "severity": "error",
                "resultStatus": "failed",
                "summary": relations_mod.type_mismatch_summary(entry, "requires", target_entry),
                "doc_id": doc_id,
                "key": "relations.requires",
                "evidence": evidence,
            }
        )
    return out


def _superseded_documents(
    doc_ids, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> set[str]:
    """``doc_ids``の文書が`supersedes`で置き換える旧文書（置換の参照先）のIDの集合（解決できたものだけ）。

    旧文書はコンテキストへは含めないが、閉包を作るときに辿る。重複したIDが旧文書のとき、仮の索引（:mod:`bitz.dupclosure`）で解決できるので辿るIDに入る。
    """

    found: set[str] = set()
    for doc_id in doc_ids:
        entry = id_index.get(doc_id)
        if entry is None:
            continue
        for ref in ((entry.frontmatter or {}).get("relations") or {}).get("supersedes") or []:
            _target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
            if target_doc_id is not None:
                found.add(target_doc_id)
    return found


def _successors(
    doc_id: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict], canonical: list[tuple[str, DocEntry]]
) -> list[str]:
    """``doc_id``を`supersedes`する有効な（適用可能な）後継のID一覧を辞書順で返す。"""

    entry = id_index[doc_id]
    kind = entry.kind
    out: set[str] = set()
    for cand_id, cand_entry in canonical:
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
