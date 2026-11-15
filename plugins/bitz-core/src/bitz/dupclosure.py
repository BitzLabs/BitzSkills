"""閉包を作るときに辿る文書IDの重複（`SPEC-ID-DUPLICATE-001`）を求める（関係・トレースモデル §5.1、確認事項C96）。

文書IDが重複したファイルは、どちらも索引に入らない（`skip-document`）。そのため閉包の計算は、重複したIDを黙って辿らない。
規範は、`context`・`verify`・`check`のどれでも、閉包を作るときに辿るID（起点、`requires`、`refines`、`addresses`、置換の参照先、
逆参照で閉包に入る文書のID。`related`の参照先は含めない）が重複していれば、その結果（`verify`は当該の検証対象）へ重複の診断を返す。
起点のIDが重複している場合は、`CTX-ROOT-MISSING-001`へ併記する。閉包と無関係な重複は返さない（`check`の完全検査が返す）。

辿るかどうかは、閉包を作る実装そのものに問う。重複した文書の写しのうち1つを索引に置いた仮の索引で閉包を作り直し、そのIDが閉包に入れば
辿るIDとする（写しのどれか1つでも入れば辿る）。前方の参照（`requires`・`refines`・`addresses`）も、逆参照（`refines`する文書、
`supersedes`する後継、`implement`で`addresses`するTASK）も、閉包の規則を複製せずに同じ判定になる。重複が2つ以上あるときは、1つずつ仮に置く
（重複した別の文書を経由して到達するものは、その文書の重複を解消した後に辿るIDになる）。

重複は例外的な状態なので、仮の索引で閉包を作り直す前に、IDを参照する文書も、関係を宣言する写しもない重複を除く
（閉包に入り得ない重複を、閉包の計算で調べない）。さらに、起点から閉包と同じ到達可能性（ADR-071 Decision 2。下方向の出発点から下方向へ具体化を辿り、
そこから上方向へ依存を辿る。置換の参照先と、`implement`で対象規範文を`addresses`するTASKを加える）で辿り着けない重複を除く。共通の文書を多数の文書が
`refines`する構成でも、起点から兄弟の文書へ逆戻りして調べない。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from . import document as document_mod
from . import multirelate
from . import relations as relations_mod
from . import targetexpand
from .document import DocEntry

_STRONG_RELATIONS = ("requires", "refines", "addresses", "supersedes")
#: 上方向に辿る関係（ADR-071 Decision 2の1.）。閉包は、下方向の出発点から下方向（`refines`の逆向き）に具体化を辿り、そこから上方向に依存を辿る。
_UPWARD_RELATIONS = ("requires", "refines", "addresses")
#: 辿り着き得る文書を求めるときに前方へ辿る関係。上方向の関係に加え、`supersedes`を前方へ辿る（`check`の変更・全体のスコープが使う強い関係の閉包は、`supersedes`も前方へ推移的に辿る）。
_FORWARD_RELATIONS = (*_UPWARD_RELATIONS, "supersedes")

#: 文書の``(ワークスペースID, 文書ID)``。
Node = tuple[str, str]

IndexPair = tuple[dict[str, DocEntry], dict[str, dict]]


@dataclass(frozen=True, eq=False)
class DuplicateGroup:
    """同じ文書IDを宣言する、重複した文書の写し（パスの辞書順）。"""

    workspace_id: str
    doc_id: str
    entries: tuple[DocEntry, ...]

    @property
    def first_path(self) -> str:
        return self.entries[0].path


class DuplicateTracker:
    """作業ワークスペース（複合ワークスペースでは到達し得る全ワークスペース）の重複の文書IDを持ち、閉包を作るときに辿るものを求める。"""

    def __init__(self, entries_by_ws: dict[str, list[DocEntry]], active_ws_id: str, multi_active: bool) -> None:
        self._entries_by_ws = entries_by_ws
        self._active = active_ws_id
        self._multi = multi_active
        groups: dict[tuple[str, str], list[DocEntry]] = {}
        for ws_id, entries in entries_by_ws.items():
            for entry in entries:
                if entry.duplicate and entry.hard is None and entry.doc_id is not None:
                    groups.setdefault((ws_id, entry.doc_id), []).append(entry)
        self._groups = {
            key: DuplicateGroup(key[0], key[1], tuple(sorted(copies, key=lambda e: e.path)))
            for key, copies in sorted(groups.items())
        }
        self._referenced: set[tuple[str, str]] | None = None
        self._candidate_groups: list[DuplicateGroup] | None = None
        self._adjacent: dict[str, dict[Node, set[Node]]] | None = None
        self._upward: dict[Node, set[Node]] | None = None
        self._variants: dict[tuple[str, str, int], IndexPair] = {}

    def __bool__(self) -> bool:
        return bool(self._groups)

    # --- 起点 -----------------------------------------------------------------------------

    def origin_group(self, raw: str) -> DuplicateGroup | None:
        """索引で解決できなかった起点（文書ID、規範文ID、修飾ID、`.spec/`配下のパス）の所有文書が重複していれば、その重複を返す。"""

        if "/" in raw or raw.endswith(".md"):
            for (ws_id, _doc_id), group in self._groups.items():
                if ws_id == self._active and any(entry.path == raw for entry in group.entries):
                    return group
            return None
        ws_id, local = self._active, raw
        if self._multi:
            qualified = multirelate.parse_qualified(raw)
            if qualified is not None:
                ws_id, local = qualified
        return self._groups.get((ws_id, local.partition(":")[0]))

    # --- 閉包を作るときに辿るID -------------------------------------------------------------

    def traversed(
        self,
        closure_ids: Callable[[dict[str, DocEntry], dict[str, dict]], Iterable[str]],
        roots: Iterable[str] | None = None,
    ) -> list[DuplicateGroup]:
        """``closure_ids(id_index, statement_index)``が返す閉包のID（索引のキーの表現）に入る重複を返す。

        ``closure_ids``は、重複した文書の写しのうち1つを索引に置いた仮の索引で呼ばれる。``roots``（索引のキーの表現の起点）を渡すと、
        閉包を作る起点から強い関係でつながらない重複を、閉包を作り直さずに除く（閉包は起点から、閉包を作る辺の向きにだけ辿って得るので、辿り着けない文書は入らない。
        :meth:`_reachable`）。
        """

        found: list[DuplicateGroup] = []
        for group in self._candidates(roots):
            key = self.index_key(group)
            for position in range(len(group.entries)):
                if key in set(closure_ids(*self._variant(group, position))):
                    found.append(group)
                    break
        return found

    def traversed_by_roots(self, roots: list[str], purpose: str) -> list[DuplicateGroup]:
        """索引で解決できた起点``roots``の、目的``purpose``の`TargetExpansion`が辿る文書のID（`traversedDocuments`）に入る重複を返す。"""

        if not roots:
            return []
        active = self._active if self._multi else None

        def closure_ids(id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> set[str]:
            ids: set[str] = set()
            for root in roots:
                expansion = targetexpand.target_expansion(root, purpose, id_index, statement_index, active_ws_id=active)
                if expansion is not None:
                    ids.update(expansion.traversed_documents)
            return ids

        return self.traversed(closure_ids, roots)

    def index_key(self, group: DuplicateGroup) -> str:
        """統合索引でのキー。作業ワークスペースの文書は修飾のないID、他のワークスペースの文書は``ws::ID``。"""

        if self._multi and group.workspace_id != self._active:
            return f"{group.workspace_id}::{group.doc_id}"
        return group.doc_id

    def diagnostics(self, groups: Iterable[DuplicateGroup]) -> list[dict]:
        """``groups``の重複の診断。`check`の完全検査（:func:`bitz.document.build_catalog`）と同じ診断（文言・発生元）を、重複ごとに1件返す。"""

        unique = {(g.workspace_id, g.doc_id): g for g in groups}
        return [
            document_mod.duplicate_diagnostic(
                g.doc_id, g.first_path, g.workspace_id, qualify_summary_ids=self._multi
            ).to_dict()
            for _key, g in sorted(unique.items())
        ]

    # --- 内部 ------------------------------------------------------------------------------

    def _referenced_documents(self) -> set[tuple[str, str]]:
        """強い関係で参照される``(ワークスペースID, 文書ID)``（宣言する写しを含むすべての文書が宣言する関係から集める）。"""

        if self._referenced is None:
            referenced: set[tuple[str, str]] = set()
            for ws_id, entries in self._entries_by_ws.items():
                for entry in entries:
                    relations = (entry.frontmatter or {}).get("relations")
                    if not isinstance(relations, dict):
                        continue
                    for relation in _STRONG_RELATIONS:
                        for ref in relations.get(relation) or []:
                            if not isinstance(ref, str):
                                continue
                            target_ws, local = ws_id, ref
                            if self._multi:
                                qualified = multirelate.parse_qualified(ref)
                                if qualified is not None:
                                    target_ws, local = qualified
                            referenced.add((target_ws, local.partition(":")[0]))
            self._referenced = referenced
        return self._referenced

    def _candidates(self, roots: Iterable[str] | None = None) -> list[DuplicateGroup]:
        if self._candidate_groups is None:
            referenced = self._referenced_documents()
            self._candidate_groups = [
                group
                for key, group in self._groups.items()
                if key in referenced or any(_declares_strong_relation(entry) for entry in group.entries)
            ]
        if roots is None:
            return self._candidate_groups
        reached = self._reachable([self._node_of(root) for root in roots])
        return [group for group in self._candidate_groups if (group.workspace_id, group.doc_id) in reached]

    def _node_of(self, key: str) -> Node:
        """索引のキー（文書ID、規範文ID、修飾ID）の所有文書を``(ワークスペースID, 文書ID)``にする。"""

        ws_id, local = self._active, key
        if self._multi:
            qualified = multirelate.parse_qualified(key)
            if qualified is not None:
                ws_id, local = qualified
        return ws_id, local.partition(":")[0]

    def _edges(self) -> dict[str, dict[Node, set[Node]]]:
        """強い関係の辺を、辺の向きごとに``{関係の名前: {宣言した文書: {参照先}}}``と``{関係の名前: {参照先: {宣言した文書}}}``で持つ（重複した写しの宣言も含む）。

        閉包を作る辺の向きの上位の集合を作るための索引で、実際の閉包の規則は複製しない。キーは、前方の辺が``<関係>``、逆向きの辺が``<関係>^``。
        """

        if self._adjacent is None:
            edges: dict[str, dict[Node, set[Node]]] = {}
            for ws_id, entries in self._entries_by_ws.items():
                for entry in entries:
                    relations = (entry.frontmatter or {}).get("relations")
                    if entry.doc_id is None or not isinstance(relations, dict):
                        continue
                    source = (ws_id, entry.doc_id)
                    for relation in _STRONG_RELATIONS:
                        for ref in relations.get(relation) or []:
                            if not isinstance(ref, str):
                                continue
                            target_ws, local = ws_id, ref
                            if self._multi:
                                qualified = multirelate.parse_qualified(ref)
                                if qualified is not None:
                                    target_ws, local = qualified
                            target = (target_ws, local.partition(":")[0])
                            edges.setdefault(relation, {}).setdefault(source, set()).add(target)
                            edges.setdefault(relation + "^", {}).setdefault(target, set()).add(source)
            self._adjacent = edges
        return self._adjacent

    def _reachable(self, nodes: Iterable[Node]) -> set[Node]:
        """``nodes``（起点の文書）から、閉包を作る辺の向きに辿って到達し得る文書（``nodes``自身を含む）。実際の閉包の上位の集合。

        閉包と同じく、(1) 下方向の出発点（起点。起点がTASKなら`addresses`の参照先）から`refines`を逆向きに終端まで辿り、(2) そこから上方向（`requires`・`refines`・`addresses`の前方）を
        終端まで辿る（`supersedes`の参照先の旧文書も前方に辿る）。(3) 閉包の文書を置換する後継と、`implement`で対象規範文を`addresses`するTASK
        （下方向の文書を`addresses`する文書）を1段だけ加える。上方向で着いた文書からは、下方向（兄弟の具体化文書）へ辿らない。
        (4) 加えた後継とTASKからは、置換の参照先の旧文書だけを前方に1段辿る（実際の閉包は、後継をコンテキストへ加えた後に、その後継が`supersedes`する別の旧文書も辿る
        IDに入れる。:func:`bitz.targetexpand._superseded_documents`）。後継とTASKからは、それ以外の関係を辿らない。
        """

        edges = self._edges()
        roots = set(nodes)
        starts = set(roots)
        for root in roots:
            starts |= edges.get("addresses", {}).get(root, set())
        downward = _walk(starts, edges.get("refines^", {}))
        if self._upward is None:
            self._upward = _merge(edges, _FORWARD_RELATIONS)
        closure = _walk(downward | roots, self._upward)
        extra: set[Node] = set()
        for node in closure:
            extra |= edges.get("supersedes^", {}).get(node, set())
        for node in downward:
            extra |= edges.get("addresses^", {}).get(node, set())
        superseded: set[Node] = set()
        for node in extra:
            superseded |= edges.get("supersedes", {}).get(node, set())
        return closure | extra | superseded

    def _variant(self, group: DuplicateGroup, position: int) -> IndexPair:
        cache_key = (group.workspace_id, group.doc_id, position)
        cached = self._variants.get(cache_key)
        if cached is not None:
            return cached
        chosen = group.entries[position]
        entries_by_ws = dict(self._entries_by_ws)
        entries_by_ws[group.workspace_id] = [
            replace(entry, duplicate=False) if entry is chosen else entry
            for entry in self._entries_by_ws[group.workspace_id]
        ]
        if self._multi:
            id_index, statement_index, *_rest = multirelate.merge_indices(self._active, entries_by_ws)
        else:
            entries = entries_by_ws[self._active]
            id_index = relations_mod.build_id_index(entries)
            statement_index = relations_mod.build_statement_index(entries)
        self._variants[cache_key] = (id_index, statement_index)
        return id_index, statement_index


def _declares_strong_relation(entry: DocEntry) -> bool:
    relations = (entry.frontmatter or {}).get("relations")
    if not isinstance(relations, dict):
        return False
    return any(relations.get(relation) for relation in _STRONG_RELATIONS)


def _walk(starts: Iterable[Node], adjacent: dict[Node, set[Node]]) -> set[Node]:
    """``starts``から``adjacent``の辺を終端まで辿って到達する文書（``starts``自身を含む）。"""

    reached: set[Node] = set()
    stack = list(starts)
    while stack:
        node = stack.pop()
        if node in reached:
            continue
        reached.add(node)
        stack.extend(adjacent.get(node, ()))
    return reached


def _merge(edges: dict[str, dict[Node, set[Node]]], relations: Iterable[str]) -> dict[Node, set[Node]]:
    """``relations``の辺を1つの隣接にまとめる（辺の種類を区別せずに辿るため）。"""

    merged: dict[Node, set[Node]] = {}
    for relation in relations:
        for source, targets in edges.get(relation, {}).items():
            merged.setdefault(source, set()).update(targets)
    return merged


def tracker_for(entries_by_ws: dict[str, list[DocEntry]], active_ws_id: str, multi_active: bool) -> DuplicateTracker | None:
    """重複した文書IDがなければ``None``（通常の経路には何も足さない）。"""

    tracker = DuplicateTracker(entries_by_ws, active_ws_id, multi_active)
    return tracker if tracker else None
