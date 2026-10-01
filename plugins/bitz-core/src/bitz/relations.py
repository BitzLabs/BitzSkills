"""関係・パス・カバレッジの検査（Step 2 フェーズC）。

関係・トレースモデル §3〜§5・§9、文書・フロントマター・状態仕様 §5、
診断レジストリ §4 を実装する。単一ワークスペースだけを対象とし、複合ワークスペース
（修飾ID、`SPEC-MULTI-REF-*`）はフェーズCの範囲外とする（存在すれば`::`を含む非修飾の解決に失敗させ、
単に「不在」として扱う）。

本モジュールはフェーズBが構築した:class:`~bitz.document.CatalogResult`の``entries``（``DocEntry``）だけを
入力とする。呼び出し側（`check.py`）が``entry.hard is None and not entry.duplicate``の文書だけを
解決対象の索引に含める、という前提をここでも守る（構文・読取りの不正で索引を作れないファイルから
関係の不在を派生させない、関係・トレースモデル §5.1）。
"""

from __future__ import annotations

import os

from . import messages
from .config import Diagnostic
from .document import DocEntry

#: 関係・トレースモデル §4「型制約」。`related`は任意の種別のため表に含めない。
#: 表にない（参照元の種別、関係型）の組は、許可する参照先の種別なし（空集合）として扱う。
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

#: 循環検査の対象の関係（関係・トレースモデル §4「`requires`と`refines`を合わせた意味上の依存グラフ」）。
_CYCLE_STRONG_RELATIONS = ("requires", "refines")
_STRONG_RELATIONS = ("requires", "refines", "addresses", "supersedes")
_ALL_RELATIONS = (*_STRONG_RELATIONS, "related")


def _mk(code, severity, status, summary, path, workspace_id, *, key=None, evidence=None) -> Diagnostic:
    src: dict = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if key is not None:
        src["key"] = key
    return Diagnostic(code=code, severity=severity, resultStatus=status, summary=summary, source=src, evidence=evidence)


def valid_entries(entries: list[DocEntry]) -> list[DocEntry]:
    """索引化・解決の対象にできる文書（`skip-document`でも重複でもない）だけを返す。"""

    return [e for e in entries if e.hard is None and not e.duplicate]


def _source_entries(entries: list[DocEntry], source_ids: set[str] | None) -> list[DocEntry]:
    """診断を生成する（＝完全検査の対象の）参照元の文書を返す。

    ``source_ids``が``None``なら制限なし（`scope: full`。カタログ全体が完全検査の対象）。
    非``None``なら``source_ids``に含まれる文書IDだけへ絞る（`scope: selected`。
    `bitz check`仕様 §3の「明示対象: `TargetExpansion(root, interpret)`の`contextDocuments`と直接の逆参照」）。
    参照先の解決（`id_index`/`statement_index`）自体は常にカタログ全体から行い、ここで絞るのは
    「どの文書について診断を生成するか」だけである。
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
    """``ref``（文書IDまたは規範文ID）を解決する。`targetexpand.py`からも再利用する公開API。"""

    return _resolve_ref(ref, id_index, statement_index)


def _resolve_ref(ref: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict]):
    """``ref``（文書IDまたは規範文ID）を解決する。

    複合ワークスペースの修飾子（``workspace::``）を含む参照は、修飾子を含めた完全な文字列を索引のキーとして
    そのまま引く（Step 5B。呼び出し側が``id_index``／``statement_index``へ``"ws::local"``形式の
    キーを用意していれば横断して解決できる。単一ワークスペースのIDには``::``を含まないため、この分岐は
    単一ワークスペース専用の索引に対しては常に不一致になり、挙動を変えない）。規範文の接尾辞の``:``は
    修飾子の部分の``::``を除いた残りだけで判定する（``ws::DOC-001:AC-01``のように修飾子と規範文の
    接尾辞が両方存在する形を正しく扱う）。

    戻り値は``(target_entry, target_doc_id)``。解決できなければ``(None, None)``。``target_doc_id``は
    複合ワークスペースの正規の表現の統合索引で解決できるよう、``ref``自体が修飾済み（``"::"``を含む）の文書ID
    参照のときは``ref``をそのまま返す（``entry.doc_id``は常にDocEntry自身の修飾のないローカルIDであり、
    修飾エイリアスを経由して解決した他のワークスペースの文書では、それをコンテキストの追跡のキーに使うと、
    同じ修飾のないローカルIDを持つ別のワークスペースの文書と衝突する。単一ワークスペース／作業ワークスペース
    自身の非修飾の``ref``では``entry.doc_id``のまま＝挙動を変えない）。
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
    """参照先の種別（＋関係・トレースモデル §4が型表へ織り込む状態の条件）が妥当かを判定する。

    - `requires`の参照先がADRの場合、型表は``accepted``のADRとだけ、状態を含めて許可する参照先の型を
      定義しているため、``accepted``でなければ種別の不適合として扱う（`draft`のREQなど他の適用可能性は
      `context`の`CTX-STATE-*`が扱い、`check`の関係の型検査はここで表現できる状態の条件だけを見る）。
    - `addresses`（TASK専用）の参照先が文書ID形式（規範文の接尾辞なし）の場合、文書種別・本文テンプレート §5
      「規範文を持つREQまたはTECHは、文書IDだけを指定して、暗黙にそのすべての規範文を対象にしない」により、
      参照先が規範文を持たないTECHであることを要求する。参照先が規範文ID形式なら、すでに`_resolve_ref`で
      実在する規範文へ解決済みなので、種別だけを見る。
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
    """``relation``の参照のうち、存在し種別が妥当な（＝循環検査へ加えてよい）参照先の文書IDを返す。"""

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
        # 関係・トレースモデル §5.1「1つの関係のエッジは…最初に成立した主診断を1件だけ返す」は、
        # 1つの参照先への参照（＝1エッジ）についての規則である。診断レジストリ「独立した元の原因は
        # それぞれ主診断を持つ」のとおり、同じフィールド内の複数のエッジ（配列の複数の要素）は互いに独立した
        # 元の原因であり、それぞれ自分の主診断を返す（フィールドの最初の1件だけに丸めない）。
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
    """``adjacency[u] = [(relation, v), ...]``のうち、循環へ参加するエッジの``(u, relation)``を返す。

    エッジ ``(u, v)``が循環へ参加する条件は、``v``から``u``へ到達可能（または自己ループ）であること。
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
    """``adjacency``（カタログ全体で計算した到達可能性）のうち、``source_ids``内の文書についてだけ
    診断を生成する（``None``なら制限なし）。循環の到達可能性の判定自体はカタログ全体を対象に
    行い（循環はグラフ全体の性質のため）、生成する診断の対象の文書だけを絞る。"""

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
    """関係のエッジの存在・型・旧形式の`refs`・循環を検査する（`related`は弱い関係として扱う）。

    ``source_ids``を渡すと、診断を生成する参照元の文書をその集合へ絞る（`scope: selected`。
    `bitz check`仕様 §3）。参照先の解決は常にカタログ全体（``entries``）から行う。``None``（既定）なら
    `scope: full`と同じくカタログ全体を参照元にする。
    """

    id_index = build_id_index(entries)
    statement_index = build_statement_index(entries)

    diags: list[Diagnostic] = []
    for entry in _source_entries(entries, source_ids):
        diags.extend(_field_diagnostics(entry, id_index, statement_index, workspace_id))

    # `requires`と`refines`を合わせた意味上の依存グラフの循環（関係・トレースモデル §4）。
    # 到達可能性はカタログ全体（valid_entries）で計算し、生成する診断だけをsource_idsへ絞る。
    combined_adjacency: dict[str, list[tuple[str, str]]] = {}
    for entry in valid_entries(entries):
        edges: list[tuple[str, str]] = []
        for relation in _CYCLE_STRONG_RELATIONS:
            for target_doc_id in _resolved_valid_targets(entry, relation, id_index, statement_index):
                edges.append((relation, target_doc_id))
        if edges:
            combined_adjacency[entry.doc_id] = edges
    diags.extend(_cycle_diagnostics(id_index, combined_adjacency, workspace_id, source_ids))

    # `supersedes`の連鎖の循環（同じ種別だけ。TASKには`supersedes`がない）。
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
    """文書種別・本文テンプレート §6: `rejected`のREQ/TECHと`cancelled`のTASKは、パスの存在検査とカバレッジから除く。"""

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
    """``entry``の`tests[].covers`が指してよい規範文IDの集合と文書IDの集合を返す。

    文書・フロントマター・状態仕様 §5は、原則として次の2形を定義する。

    - (a) REQまたは規範文を持つTECH: `covers`へ同じ文書の規範文IDを指定する。
    - (b) 規範文を持たないTECH: 文書IDを指定できる（自身のID）。

    しかしGate Aの認定済みのfixture（例: SINGLE-042、SINGLE-070-02など、「規範文を持たないTECHが
    `relations.refines`するREQの受入条件の規範文群をカバーする」構成）はこの原則だけでは表せない、TECHが
    直接`refines`するREQの規範文をカバーする形を、正例として要求する。これは関係・トレースモデル
    §9「別のワークスペースの規範文を`tests[].covers`へ指定できるのは、宣言する文書が、その規範文または
    それを所有する文書を直接`refines`する場合に限る」
    の単一ワークスペース版（修飾なしで同じ直接の`refines`の原理を適用したもの）として一貫して説明できるため、
    次の(c)を単一ワークスペースでも常に許可する。

    - (c) 宣言する文書が`relations.refines`で直接参照する文書の規範文（`refines`の参照先が文書ID形式の場合）、
      または直接参照する規範文そのもの（`refines`の参照先が規範文ID形式の場合）。

    「ワークスペース内で解決できれば可」という緩い判定はしない。(a)〜(c)のいずれにも該当しない
    規範文ID／文書IDはすべて無効とする。
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
    """`tests[].covers`が妥当な規範文または文書IDを参照することを検査する（:func:`_covers_allowed_refs`）。

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
            # `covers`の要素を単位とする診断（結果・診断・終了コード §4）。独立した原因（配列の各要素）は
            # それぞれ主診断を持つため、最初の不正な参照で打ち切らず、すべての要素を検査する。
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
