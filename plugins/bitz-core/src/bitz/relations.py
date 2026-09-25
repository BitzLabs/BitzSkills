"""関係・path・coverageの検査（Step 2 Phase C）。

`02_SPECモデル/04_関係・トレースモデル.md` §3〜§5・§9、`02_文書・Frontmatter・状態仕様.md` §5、
`00_共通契約/05_Diagnostic-registry.md` §4 を実装する。単一workspaceだけを対象とし、複合workspace
（修飾ID、`SPEC-MULTI-REF-*`）はPhase Cの範囲外とする（存在すれば`::`を含む非修飾解決に失敗させ、
単に「不在」として扱う）。

本moduleはPhase Bが構築した:class:`~bitz.document.CatalogResult`の``entries``（``DocEntry``）だけを
入力とする。呼び出し側（`check.py`）が``entry.hard is None and not entry.duplicate``の文書だけを
解決対象索引に含める、という前提をここでも守る（構文・読取り不正で索引を作れないfileから
relation missingを派生させない、関係・トレースモデル §5.1）。
"""

from __future__ import annotations

import os

from . import messages
from .config import Diagnostic
from .document import DocEntry

#: 関係・トレースモデル §4「型制約」。`related`は任意種別のため表に含めない。
#: 表にない``(source kind, relation)``の組は許可target種別なし（空集合）として扱う。
RELATION_ALLOWED_TARGET_KINDS: dict[tuple[str, str], set[str]] = {
    ("REQ", "requires"): {"REQ", "TECH", "ADR"},
    ("REQ", "refines"): {"REQ"},
    ("REQ", "supersedes"): {"REQ"},
    ("TECH", "requires"): {"REQ", "TECH", "ADR"},
    ("TECH", "refines"): {"REQ", "TECH"},
    ("TECH", "supersedes"): {"TECH"},
    ("ADR", "requires"): {"REQ", "TECH", "ADR"},
    ("ADR", "supersedes"): {"ADR"},
    ("TASK", "requires"): {"REQ", "TECH", "TASK", "ADR"},
    ("TASK", "addresses"): {"REQ", "TECH"},
}

#: 循環検査の対象relation（関係・トレースモデル §4「requiresとrefinesを合わせた意味依存graph」）。
_CYCLE_STRONG_RELATIONS = ("requires", "refines")
_STRONG_RELATIONS = ("requires", "refines", "addresses", "supersedes")
_ALL_RELATIONS = (*_STRONG_RELATIONS, "related")


def _mk(code, severity, status, summary, path, workspace_id, *, key=None, evidence=None) -> Diagnostic:
    src: dict = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if key is not None:
        src["key"] = key
    return Diagnostic(code=code, severity=severity, resultStatus=status, summary=summary, source=src, evidence=evidence)


def valid_entries(entries: list[DocEntry]) -> list[DocEntry]:
    """索引化・解決対象にできる文書（skip-documentでも重複でもない）だけを返す。"""

    return [e for e in entries if e.hard is None and not e.duplicate]


def _source_entries(entries: list[DocEntry], source_ids: set[str] | None) -> list[DocEntry]:
    """Diagnosticを生成する（＝完全検査対象の）source文書を返す。

    ``source_ids``が``None``なら制限なし（`scope: full`。catalog全体が完全検査対象）。
    非``None``なら``source_ids``に含まれる文書IDだけへ絞る（`scope: selected`。
    `check.md §3`の「明示対象: TargetExpansion(root, interpret)のcontextDocumentsと直接逆参照」）。
    target解決（`id_index`/`statement_index`）自体は常にcatalog全体から行い、ここで絞るのは
    「どの文書についてDiagnosticを生成するか」だけである。
    """

    docs = valid_entries(entries)
    if source_ids is None:
        return docs
    return [e for e in docs if e.doc_id in source_ids]


def build_id_index(entries: list[DocEntry]) -> dict[str, DocEntry]:
    return {e.doc_id: e for e in valid_entries(entries) if e.doc_id is not None}


def build_statement_index(entries: list[DocEntry]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for e in valid_entries(entries):
        for stmt in e.statements:
            index[stmt["id"]] = stmt
    return index


def resolve_ref(ref: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]):
    """``ref``（文書IDまたはstatement ID）を解決する。`targetexpand.py`からも再利用する公開API。"""

    return _resolve_ref(ref, id_index, statement_index)


def _resolve_ref(ref: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]):
    """``ref``（文書IDまたはstatement ID）を解決する。

    複合workspace修飾子（``workspace::``）を含む参照は、修飾子を含めた完全な文字列を索引keyとして
    そのまま引く（Step 5B。呼び出し側が``id_index``／``statement_index``へ``"ws::local"``形式の
    keyを用意していれば横断解決できる。単一workspaceのIDには``::``を含まないため、この分岐は
    単一workspace専用の索引に対しては常に不一致になり、挙動を変えない）。statement suffixの``:``は
    修飾子部分の``::``を除いた残りだけで判定する（``ws::DOC-001:AC-01``のように修飾子と statement
    suffixが両方存在する形を正しく扱う）。

    戻り値は``(target_entry, target_doc_id)``。解決できなければ``(None, None)``。``target_doc_id``は
    複合workspace正規表現の統合索引で解決できるよう、``ref``自体が修飾済み（``"::"``を含む）文書ID
    参照のときは``ref``をそのまま返す（``entry.doc_id``は常にDocEntry自身のbareなlocal IDであり、
    修飾aliasを経由して解決した他workspaceの文書では、それをcontext追跡keyに使うと同じbare local ID
    を持つ別workspaceの文書と衝突する。単一workspace／active workspace自身の非修飾refでは
    ``entry.doc_id``のまま＝挙動を変えない）。
    """

    if "::" in ref:
        _ws, _, local = ref.partition("::")
        has_stmt_suffix = ":" in local
    else:
        has_stmt_suffix = ":" in ref
    if has_stmt_suffix:
        stmt = statement_index.get(ref)
        if stmt is None:
            return None, None
        doc_id = stmt["documentId"]
        return id_index.get(doc_id), doc_id
    entry = id_index.get(ref)
    if entry is None:
        return None, None
    return entry, (ref if "::" in ref else entry.doc_id)


def _target_kind_ok(entry: DocEntry, relation: str, ref: str, target_entry: DocEntry) -> bool:
    """target種別（＋関係・トレースモデル §4が型表へ織り込む状態条件）が妥当かを判定する。

    - `requires`のtargetがADRの場合、型表は``accepted ADR``とだけ状態込みで許可target型を
      定義しているため、``accepted``でなければkind不適合として扱う（`draft` REQなど他の適用可能性は
      `context`の`CTX-STATE-*`が扱い、`check`のrelation型検査はここで表現できる状態条件だけを見る）。
    - `addresses`（TASK専用）のtargetが文書ID形式（statement接尾辞なし）の場合、本文template §5
      「規範文を持つREQ/TECHを文書IDだけで暗黙に全句対象にしない」により、targetが規範文を持たない
      TECHであることを要求する。targetがstatement ID形式なら、既に`_resolve_ref`で実在するstatementへ
      解決済みなのでkindだけを見る。
    """

    allowed = RELATION_ALLOWED_TARGET_KINDS.get((entry.kind, relation), set())
    if target_entry.kind not in allowed:
        return False
    if relation == "requires" and target_entry.kind == "ADR" and target_entry.status != "accepted":
        return False
    if relation == "addresses" and ":" not in ref:
        if target_entry.kind != "TECH" or target_entry.statement_count > 0:
            return False
    return True


def _resolved_valid_targets(
    entry: DocEntry, relation: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> list[str]:
    """``relation``の参照のうち、存在しkindが妥当な（＝循環検査へ加えてよい）target doc IDを返す。"""

    refs = (entry.frontmatter.get("relations") or {}).get(relation) or []
    out: list[str] = []
    for ref in refs:
        target_entry, target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None:
            continue
        if not _target_kind_ok(entry, relation, ref, target_entry):
            continue
        if target_doc_id not in out:
            out.append(target_doc_id)
    return out


def _field_diagnostics(
    entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict], workspace_id: str
) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    relations = entry.frontmatter.get("relations") or {}
    for relation in _ALL_RELATIONS:
        refs = relations.get(relation) or []
        if not refs:
            continue
        is_related = relation == "related"
        # 関係・トレースモデル §5.1「1つのrelation edgeは…primaryを1件だけ返す」は、1つのtarget
        # 参照（＝1 edge）についての規則である。Diagnostic registry「独立したraw原因はそれぞれ
        # primaryを持つ」のとおり、同じfield内の複数edge（配列の複数要素）は互いに独立したraw原因
        # であり、それぞれ自分のprimaryを返す（fieldの最初の1件だけに丸めない）。
        for ref in refs:
            target_entry, _target_doc_id = _resolve_ref(ref, id_index, statement_index)
            if target_entry is None:
                if is_related:
                    diags.append(
                        _mk(
                            "SPEC-RELATION-ADVISORY-MISSING-001",
                            "warning",
                            "passed_with_warnings",
                            messages.RELATION_ADVISORY_MISSING,
                            entry.path,
                            workspace_id,
                            key=f"relations.{relation}",
                            evidence=ref,
                        )
                    )
                else:
                    diags.append(
                        _mk(
                            "SPEC-RELATION-MISSING-001",
                            "error",
                            "failed",
                            messages.relation_missing_strong(entry.path),
                            entry.path,
                            workspace_id,
                            key=f"relations.{relation}",
                            evidence=ref,
                        )
                    )
                continue
            if not is_related and not _target_kind_ok(entry, relation, ref, target_entry):
                diags.append(
                    _mk(
                        "CTX-RELATION-TYPE-001",
                        "error",
                        "failed",
                        messages.relation_type_mismatch(entry.kind, target_entry.kind, relation),
                        entry.path,
                        workspace_id,
                        key=f"relations.{relation}",
                        evidence=ref,
                    )
                )

    if "refs" in entry.frontmatter:
        diags.append(
            _mk(
                "SPEC-RELATION-LEGACY-001",
                "error",
                "failed",
                messages.RELATION_LEGACY_REFS,
                entry.path,
                workspace_id,
                key="refs",
            )
        )
    return diags


def _find_cyclic_edges(adjacency: dict[str, list[tuple[str, str]]]) -> set[tuple[str, str]]:
    """``adjacency[u] = [(relation, v), ...]``のうち、循環へ参加するedgeの``(u, relation)``を返す。

    edge ``(u, v)``が循環へ参加する条件は、``v``から``u``へ到達可能（またはself loop）であること。
    """

    plain: dict[str, set[str]] = {u: {v for _, v in vs} for u, vs in adjacency.items()}
    reach_cache: dict[str, set[str]] = {}

    def reachable_from(start: str) -> set[str]:
        seen: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in plain.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    cyclic: set[tuple[str, str]] = set()
    for u, edges in adjacency.items():
        for relation, v in edges:
            if v == u:
                cyclic.add((u, relation))
                continue
            if v not in reach_cache:
                reach_cache[v] = reachable_from(v)
            if u in reach_cache[v]:
                cyclic.add((u, relation))
    return cyclic


def _cycle_diagnostics(
    id_index: dict[str, DocEntry],
    adjacency: dict[str, list[tuple[str, str]]],
    workspace_id: str,
    source_ids: set[str] | None,
) -> list[Diagnostic]:
    """``adjacency``（catalog全体で計算した到達可能性）のうち、``source_ids``内の文書についてだけ
    Diagnosticを生成する（``None``なら制限なし）。循環の到達可能性判定自体はcatalog全体を対象に
    行い（circularはgraph全体の性質のため）、生成するDiagnosticの対象文書だけを絞る。"""

    cyclic_pairs = _find_cyclic_edges(adjacency)
    diags = []
    for doc_id, relation in sorted(cyclic_pairs):
        if source_ids is not None and doc_id not in source_ids:
            continue
        entry = id_index[doc_id]
        diags.append(
            _mk(
                "CTX-CYCLE-001",
                "error",
                "failed",
                messages.relation_cycle(relation),
                entry.path,
                workspace_id,
                key=f"relations.{relation}",
            )
        )
    return diags


def check_relations(
    entries: list[DocEntry], workspace_id: str, *, source_ids: set[str] | None = None
) -> list[Diagnostic]:
    """relation edgeの存在・型・legacy `refs`・循環を検査する（`related`はweakとして扱う）。

    ``source_ids``を渡すと、Diagnosticを生成するsource文書をその集合へ絞る（`scope: selected`。
    `check.md §3`）。target解決は常にcatalog全体（``entries``）から行う。``None``（既定）なら
    `scope: full`と同じくcatalog全体をsourceにする。
    """

    id_index = build_id_index(entries)
    statement_index = build_statement_index(entries)

    diags: list[Diagnostic] = []
    for entry in _source_entries(entries, source_ids):
        diags.extend(_field_diagnostics(entry, id_index, statement_index, workspace_id))

    # requires + refinesを合わせた意味依存graphの循環（関係・トレースモデル §4）。
    # 到達可能性はcatalog全体（valid_entries）で計算し、生成するDiagnosticだけをsource_idsへ絞る。
    combined_adjacency: dict[str, list[tuple[str, str]]] = {}
    for entry in valid_entries(entries):
        edges: list[tuple[str, str]] = []
        for relation in _CYCLE_STRONG_RELATIONS:
            for target_doc_id in _resolved_valid_targets(entry, relation, id_index, statement_index):
                edges.append((relation, target_doc_id))
        if edges:
            combined_adjacency[entry.doc_id] = edges
    diags.extend(_cycle_diagnostics(id_index, combined_adjacency, workspace_id, source_ids))

    # supersedes連鎖の循環（同種別のみ。TASKにはsupersedesがない）。
    supersedes_adjacency: dict[str, list[tuple[str, str]]] = {}
    for entry in valid_entries(entries):
        targets = _resolved_valid_targets(entry, "supersedes", id_index, statement_index)
        if targets:
            supersedes_adjacency[entry.doc_id] = [("supersedes", t) for t in targets]
    diags.extend(_cycle_diagnostics(id_index, supersedes_adjacency, workspace_id, source_ids))

    return diags


def _path_exists_as_file(workspace_root: str, rel_path: str) -> bool:
    abs_path = os.path.join(workspace_root, rel_path)
    return os.path.isfile(abs_path) and not os.path.islink(abs_path)


def _skip_path_and_coverage(entry: DocEntry) -> bool:
    """文書種別・本文template §6: rejected REQ/TECHとcancelled TASKはpath存在検査・coverageから除く。"""

    return entry.status in ("rejected", "cancelled")


def check_paths(
    entries: list[DocEntry], workspace_root: str, workspace_id: str, *, source_ids: set[str] | None = None
) -> list[Diagnostic]:
    """`implements`と`tests[].path`の存在を検査する（関係・トレースモデル §9）。

    ``source_ids``の意味は :func:`check_relations` と同じ（`scope: selected`の絞り込み）。
    """

    diags: list[Diagnostic] = []
    for entry in _source_entries(entries, source_ids):
        if _skip_path_and_coverage(entry):
            continue
        is_draft = entry.status == "draft"
        severity = "warning" if is_draft else "error"
        status = "passed_with_warnings" if is_draft else "failed"

        implements = entry.frontmatter.get("implements") or []
        for p in implements:
            if not _path_exists_as_file(workspace_root, p):
                diags.append(
                    _mk(
                        "SPEC-PATH-INVALID-001",
                        severity,
                        status,
                        messages.IMPLEMENTS_PATH_DRAFT if is_draft else messages.IMPLEMENTS_PATH_MISSING,
                        entry.path,
                        workspace_id,
                        key="implements",
                    )
                )
                break

        tests = entry.frontmatter.get("tests") or []
        for idx, t in enumerate(tests):
            p = t.get("path") if isinstance(t, dict) else None
            if p and not _path_exists_as_file(workspace_root, p):
                diags.append(
                    _mk(
                        "SPEC-PATH-INVALID-001",
                        severity,
                        status,
                        messages.TEST_PATH_DRAFT if is_draft else messages.TEST_PATH_MISSING,
                        entry.path,
                        workspace_id,
                        key=f"tests[{idx}].path",
                    )
                )
    return diags


def _covers_allowed_refs(
    entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> tuple[set[str], set[str]]:
    """``entry``の`tests[].covers`が指してよいstatement IDの集合と文書IDの集合を返す。

    文書・Frontmatter・状態仕様 §5は原則として次の2形を定義する。

    - (a) REQまたは規範文ありTECH: 「`covers`へ同じ文書の規範文IDを指定する」。
    - (b) 規範文を持たないTECH: 「文書IDを指定できる」（自身のID）。

    しかしGate A認定済みfixture（例: SINGLE-042、SINGLE-070-02等の「statementless TECHが
    `relations.refines`するREQのAC群をcoverする」構成）はこの原則だけでは表せない、TECHが
    直接refinesするREQのstatementをcoverする形を正例として要求する。これは関係・トレースモデル
    §9「複合workspaceで文書が…直接`refines`する場合だけ、そのtargetを修飾IDで`covers`に指定できる」
    の単一workspace版（修飾なしで同じ直接refines原理を適用したもの）として一貫的に説明できるため、
    次の(c)を単一workspaceでも常に許可する。

    - (c) 宣言文書が`relations.refines`で直接参照する文書の規範文（refines先が文書ID形式の場合）、
      または直接参照する規範文そのもの（refines先がstatement ID形式の場合）。

    「workspace内で解決できれば可」という緩い判定はしない。(a)〜(c)のいずれにも該当しない
    statement ID／文書IDはすべて無効とする。
    """

    allowed_statement_ids: set[str] = set()
    allowed_doc_ids: set[str] = set()

    # (a) 自身の規範文。
    for stmt in entry.statements:
        allowed_statement_ids.add(stmt["id"])

    # (b) 規範文を持たない場合の自身の文書ID。
    if not entry.statements:
        allowed_doc_ids.add(entry.doc_id)

    # (c) `relations.refines`で直接参照する文書の規範文、または直接参照する規範文そのもの。
    refines_refs = (entry.frontmatter.get("relations") or {}).get("refines") or []
    for ref in refines_refs:
        target_entry, _target_doc_id = _resolve_ref(ref, id_index, statement_index)
        if target_entry is None:
            continue
        if ":" in ref:
            allowed_statement_ids.add(ref)
        else:
            for stmt in target_entry.statements:
                allowed_statement_ids.add(stmt["id"])

    return allowed_statement_ids, allowed_doc_ids


def check_coverage(
    entries: list[DocEntry], workspace_id: str, *, source_ids: set[str] | None = None
) -> list[Diagnostic]:
    """`tests[].covers`が妥当なstatementまたは文書IDを参照することを検査する（:func:`_covers_allowed_refs`）。

    ``source_ids``の意味は :func:`check_relations` と同じ（`scope: selected`の絞り込み）。
    """

    id_index = build_id_index(entries)
    statement_index = build_statement_index(entries)

    diags: list[Diagnostic] = []
    for entry in _source_entries(entries, source_ids):
        if _skip_path_and_coverage(entry):
            continue
        allowed_statement_ids, allowed_doc_ids = _covers_allowed_refs(entry, id_index, statement_index)
        tests = entry.frontmatter.get("tests") or []
        for idx, t in enumerate(tests):
            if not isinstance(t, dict):
                continue
            covers = t.get("covers") or []
            # covers要素を単位とするDiagnostic（結果契約 §4）。独立した原因（配列の各要素）は
            # それぞれprimaryを持つため、最初の不正参照で打ち切らず全要素を検査する。
            for ref in covers:
                if ":" in ref:
                    valid = ref in allowed_statement_ids
                else:
                    valid = ref in allowed_doc_ids
                if not valid:
                    diags.append(
                        _mk(
                            "SPEC-TEST-COVERAGE-001",
                            "error",
                            "failed",
                            messages.TEST_COVERAGE_INVALID,
                            entry.path,
                            workspace_id,
                            key=f"tests[{idx}].covers",
                            evidence=ref,
                        )
                    )
    return diags
