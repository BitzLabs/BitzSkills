"""`TargetExpansion(root, purpose)`（`02_SPECモデル/04_関係・トレースモデル.md` §6.1・§6.4）。

起点から対象を展開する唯一の契約。`context`、明示対象`check`、`verify`はこの関数を再利用する
（同 §6.4）。Step 2 Phase Cは`check`の明示対象検査が使う`purpose=interpret`だけを完全実装する。
`implement`／`verify`はStep 3のcontext実装時に同じ関数へ追加する（現時点では`interpret`と同じ
閉包規則をbest-effortで適用し、`targetStatements`は§6.4の規則どおり本関数の範囲では計算しない
— test対象義務の展開はStep 3で追加する）。

入力`root`は索引で解決済みの文書IDまたはstatement ID。出力は`rootDocuments`、`contextDocuments`、
`targetStatements`、`adjacentStatements`の4集合（すべて正規IDの重複なしlist）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

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


def _requires_closure(
    start_ids: list[str], id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[str]:
    seen: list[str] = []
    seen_set: set[str] = set()
    frontier = list(start_ids)
    while frontier:
        cur = frontier.pop(0)
        entry = id_index.get(cur)
        if entry is None:
            continue
        for target_id in _requires_targets(entry, id_index, statement_index):
            if target_id not in seen_set:
                seen_set.add(target_id)
                seen.append(target_id)
                frontier.append(target_id)
    return seen


def _applicable_refinements_closure(
    root_id: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[str]:
    """§6.1「4.」: targetをrefineするapplicable文書を逆参照で含め、そのrequiresを辿る（推移的）。"""

    included: list[str] = []
    included_set: set[str] = set()
    frontier = [root_id]
    while frontier:
        target = frontier.pop(0)
        for cand_id, cand_entry in id_index.items():
            if cand_id in included_set or cand_id == root_id:
                continue
            if cand_entry.kind not in ("REQ", "TECH") or not _is_applicable(cand_entry):
                continue
            if target in _refines_targets(cand_entry, id_index, statement_index):
                included_set.add(cand_id)
                included.append(cand_id)
                frontier.append(cand_id)
    return included


def _draft_refinements(
    context_ids: set[str], id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[str]:
    """§6.1「6.」: 閉包内のapplicable文書またはそのstatementをrefinesするdraft文書をadvisoryで含める。

    draft refinementの`requires`とそれをrefinesする文書は辿らない（advisoryは規範として適用しない）。
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


def target_expansion(
    root: str,
    purpose: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
) -> TargetExpansionResult | None:
    """単一起点への`TargetExpansion(root, purpose)`。起点を解決できなければ``None``を返す。

    ``purpose="implement"``／``"verify"``（`関係・トレースモデル §6.2`・`§6.3`）は未実装である。
    `interpret`の閉包をそのまま返すと、`targetStatements`（test義務展開）やTASK `requires`
    完了判定など、`implement`/`verify`だけが必要とする規則が欠けたまま黙って動いてしまう
    （安全側に倒すため実装するまで明示的に例外にする）。呼び出し側（`check.py`の明示対象check）は
    現状`interpret`だけを渡す。
    """

    if purpose != "interpret":
        raise NotImplementedError(
            f"target_expansion: purpose={purpose!r}はStep 3で実装する（現状はinterpretだけ対応）"
        )

    owning_id = _owning_document_id(root, id_index, statement_index)
    if owning_id is None:
        return None
    root_entry = id_index[owning_id]

    context_set: set[str] = {owning_id}
    context_order: list[str] = [owning_id]

    def _add(doc_id: str) -> None:
        if doc_id not in context_set:
            context_set.add(doc_id)
            context_order.append(doc_id)

    # 2. requiresを終端まで辿る。
    for doc_id in _requires_closure([owning_id], id_index, statement_index):
        _add(doc_id)

    # 3. refines targetを含める（起点自身のrefines）。
    for doc_id in _refines_targets(root_entry, id_index, statement_index):
        _add(doc_id)

    # 4. targetをrefineするapplicable文書を逆参照で含め、そのrequiresを辿る。
    refiners = _applicable_refinements_closure(owning_id, id_index, statement_index)
    for doc_id in refiners:
        _add(doc_id)
    for doc_id in _requires_closure(refiners, id_index, statement_index):
        _add(doc_id)

    # 6. draft refinementをadvisoryとして含める（requires・逆refinesは辿らない）。
    for doc_id in _draft_refinements(context_set, id_index, statement_index):
        _add(doc_id)

    return TargetExpansionResult(
        root_documents=[owning_id],
        context_documents=sorted(context_order),
        target_statements=[],
        adjacent_statements=[],
    )
