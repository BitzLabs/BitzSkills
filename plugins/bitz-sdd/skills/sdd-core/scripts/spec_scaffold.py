#!/usr/bin/env python3
"""spec_scaffold.py — BitzSDD（sdd-core スキル）の採番付き雛形生成ツール（stdlib のみ）

要件 / spec-issue / タスク / 設計ノート(DSN) の新規起票時に、プレフィックスごとの次番号を
決定的に採番し、spec_inspect.py の検証を PASS する frontmatter 付き雛形を生成する。
エージェントが毎回手書きしていた採番・雛形生成を機械化し、書式ブレと採番衝突を構造的に防ぐ
（CORE-FR-004）。あわせて生成時に統制語彙（verification_method / domain / status）を検証し、
語彙外の値は生成前に非ゼロで失敗させて承認後の手戻りを防ぐ（CORE-FR-010）。

副作用は指定ワークスペースの .spec/ 配下への新規ファイル生成のみ。既存ファイルは上書きしない。

使い方:
  python spec_scaffold.py <workspace> requirement --prefix CORE-FR [--domain tooling] [--title T]
  python spec_scaffold.py <workspace> spec-issue  --prefix SI-CORE [--target T] [--raised-by R]
  python spec_scaffold.py <workspace> task --implements CORE-FR-004 --prefix CORE-TSK [--boundary B]
  python spec_scaffold.py <workspace> design --prefix DSN [--title T] [--status draft] [--implements ID]
  python spec_scaffold.py <workspace> gate --prefix SDD-GATE --gate promotion --arbiter hide \
      --scope "SDD-FR-001,SDD-FR-002" --decision-ref .spec/reports/decision-YYYY-MM-DD-....md
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

# 統制語彙は spec_inspect.py を単一の正として共有する（scaffold 側で二重定義しない。CORE-FR-010）。
# spec_inspect はモジュールレベルで定数・関数を定義するだけで __main__ ガード下でのみ実行するため
# import に副作用はない。スクリプト直実行時もラッパー経由でも解決できるよう自ディレクトリを追加。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_inspect import (  # noqa: E402
    RECURSIVE_ARTIFACT_DIRS,
    STATUSES,
    VMETHODS,
    load_domains,
    parse_frontmatter,
)
from spec_transaction import (  # noqa: E402
    FileChange,
    MutationError,
    TransactionPlan,
    mutate,
)

KIND_DIR = {
    "requirement": "requirements",
    "spec-issue": "spec-issues",
    "task": "tasks",
    "design": "design",
    "gate": "gates",
}


def next_number(directory: Path, prefix: str, recursive: bool = False) -> int:
    """directory 配下の成果物を走査し「最大番号 + 1」を返す（無ければ 1）。

    番号の根拠は **frontmatter の `id:`** であり、ファイル名ではない（SDD-FR-162）。
    `domain-model.md`（`id: SDD-DSN-009`）や `stories/story-p1-*.md` のように ID を
    ファイル名に持たない成果物が採番から見えず、既存 ID を再度払い出したためである
    （SI-SDD-036。`SI-SDD-006` 提案2 の実装）。frontmatter に `id:` を持たない成果物は
    ファイル名からの番号抽出へフォールバックする — `DSN-001-delegation-registry.md` のような
    説明的サフィックス付きの慣行を落とさないため（`SI-SDD-006` 提案1 の維持）。
    `recursive` は spec_inspect のレジストリ走査と範囲を揃えるために使う（design 配下）。
    """
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)(-.*)?\.md$")
    id_pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    nums = []
    if directory.exists():
        for f in directory.glob("**/*.md" if recursive else "*.md"):
            if f.name.startswith("_"):
                continue
            rid = ""
            try:
                rid = parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore")).get("id", "")
            except OSError:
                pass
            m = id_pat.match(rid.strip()) or pat.match(f.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def render_requirement(rid: str, args) -> str:
    return (
        f"---\n"
        f"id: {rid}\n"
        f"version: 1.0\n"
        f"status: draft\n"
        f"domain: {args.domain or ''}\n"
        f"priority: {args.priority or 'medium'}\n"
        f"origin: {args.origin or 'TODO（起票の由来を記入）'}\n"
        f"verification_method: {args.verification_method or 'example-test'}\n"
        f"derived_from:\n"
        f"supersedes:\n"
        f"superseded_by:\n"
        f"confidence: high\n"
        f"---\n\n"
        f"### {rid} {args.title or 'TODO タイトル'}\n\n"
        f"- **説明**: TODO（この要件が保証する振る舞いを記述）\n"
        f"- **受入基準 (EARS)**:\n"
        f"  - WHEN TODO の条件 THEN TODO の振る舞いを満たすこと SHALL\n"
        f"- **検証手段**: TODO（{args.verification_method or 'example-test'} での検証方法）\n"
        f"- **Revision History**:\n"
        f"  - 1.0 ({date.today().isoformat()}) 初版（draft 起票）\n"
    )


def render_spec_issue(iid: str, args) -> str:
    # 委託フィールド（SDD-FR-132）は指定時のみ出力する（既存書式の後方互換を保つ。
    # 委託フローの規定は sdd-core references/lifecycle.md の「ワークスペース間委託」節が正）
    delegation = ""
    if args.origin:
        delegation += f"origin: {args.origin}\n"
    if args.delegated_to:
        delegation += f"delegated_to: {args.delegated_to}\n"
    return (
        f"---\n"
        f"id: {iid}\n"
        f"raised_by: {args.raised_by or 'TODO（発見元）'}\n"
        f"target: {args.target or 'TODO（変更対象）'}\n"
        f"proposed_change_type: {args.change_type or 'new'}\n"
        f"status: open\n"
        f"{delegation}"
        f"---\n"
        f"- **目的**: TODO\n"
        f"- **提案する修正**: TODO\n"
        f"- **対象ファイル**: TODO\n"
        f"- **確認観点**: TODO\n"
        f"- **影響推定・ロールバック**: TODO\n"
        f"- **依存**: TODO\n"
    )


def render_task(tid: str, args) -> str:
    return (
        f"---\n"
        f"implements: {args.implements}\n"
        f"depends_on: {args.depends_on or '[]'}\n"
        f"boundary: {args.boundary or 'TODO（触れてよいパス）'}\n"
        f"status: pending\n"
        f"---\n\n"
        f"### {args.title or 'TODO タスク（タスク ID はファイル名が正）'}\n\n"
        f"- **作業内容**: TODO\n"
        f"- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として"
        f"検出するため記載しない（SI-CORE-002 参照）。\n"
    )


def render_design(did: str, args) -> str:
    # DSN の書式は公開契約 assets/artifact-frontmatter.md が正（id/title/status/version/updated/owner）。
    # 追跡用に implements / origin も持たせる（DSN-001 の先例）。status 既定は DSN 有効語彙の draft。
    return (
        f"---\n"
        f"id: {did}\n"
        f"title: \"{args.title or 'TODO タイトル'}\"\n"
        f"status: {args.status or 'draft'}\n"
        f"version: 1.0\n"
        f"updated: {date.today().isoformat()}\n"
        f"owner: {args.owner or 'TODO（担当者ハンドル）'}\n"
        f"implements: {args.implements or ''}\n"
        f"origin: {args.origin or ''}\n"
        f"---\n\n"
        f"# {did} {args.title or 'TODO タイトル'}\n\n"
        f"- **背景 / 課題**: TODO\n"
        f"- **設計判断**: TODO\n"
        f"- **代替案と却下理由**: TODO\n"
        f"- **影響範囲・ロールバック**: TODO\n"
    )


GATE_CHECKLIST_REF = {
    "discovery": "skills/sdd-core/references/gates.md#1-discovery-gatemap--discovery-の出口",
    "design": "skills/sdd-core/references/gates.md#2-design-gateproposed--active",
    "promotion": "skills/sdd-core/references/gates.md#3-promotion-gateverified--promoted",
}


def render_gate(gid: str, args) -> str:
    """GatePassage の雛形（SDD-FR-155）。

    裁定の理由と経緯は `.spec/reports/decision-*.md` が持つため、本文は薄くし
    `confirmed_decision_refs` で参照する（二重管理しない）。status 遷移は持たない。
    """
    scope = [s.strip() for s in (args.scope or "").split(",") if s.strip()]
    refs = "".join(f"  - {ref}\n" for ref in (args.decision_ref or []))
    return (
        f"---\n"
        f"id: {gid}\n"
        f"gate: {args.gate}\n"
        f"date: {date.today().isoformat()}\n"
        f"arbiter: {args.arbiter}\n"
        f"scope: [{', '.join(scope)}]\n"
        f"confirmed_decision_refs:\n"
        f"{refs}"
        f"checklist_ref: {args.checklist_ref or GATE_CHECKLIST_REF[args.gate]}\n"
        f"---\n\n"
        f"# {gid} {args.title or (args.gate + ' Gate 通過記録')}\n\n"
        f"- **裁定者**: {args.arbiter}\n"
        f"- **対象**: 上記 `scope` の {len(scope)} 件\n"
        f"- **確認した裁定記録**: 上記 `confirmed_decision_refs`\n"
        f"- **チェックリスト**: `{args.checklist_ref or GATE_CHECKLIST_REF[args.gate]}`\n"
        f"- **備考**: TODO（チェックリストの消化で特記があれば記す）\n"
    )


def validate_vocab(args, req_dir: Path) -> "str | None":
    """統制語彙を生成前に検証する。語彙外ならエラーメッセージを返す（正常なら None）。

    語彙は spec_inspect と共有（VMETHODS / STATUSES）。domain はワークスペース固有のため
    domains.md を実行時に読む。domains.md が無ければ domain 検証はスキップ（縮退挙動）。
    """
    if args.verification_method is not None and args.verification_method not in VMETHODS:
        return (f"verification_method '{args.verification_method}' は語彙外です"
                f"（有効: {sorted(VMETHODS)}）")
    if args.domain:
        domains = load_domains(req_dir)
        if domains is not None and args.domain not in domains:
            return (f"domain '{args.domain}' は {req_dir / 'domains.md'} の語彙にありません"
                    f"（有効: {sorted(domains)}）")
    if getattr(args, "status", None) is not None and args.status not in STATUSES:
        return f"status '{args.status}' は語彙外です（有効: {sorted(STATUSES)}）"
    return None


def main():
    parser = argparse.ArgumentParser(description="BitzSDD 採番付き雛形生成ツール")
    parser.add_argument("workspace", help="ワークスペースルート（.spec/ を含む）")
    parser.add_argument("kind", choices=sorted(KIND_DIR), help="生成する成果物の種別")
    parser.add_argument("--prefix", required=True, help="ID プレフィックス（例: CORE-FR / SI-CORE / CORE-TSK）")
    parser.add_argument("--number", type=int, help="番号を明示指定（省略時は最大+1 を自動採番）")
    parser.add_argument("--title", help="タイトル")
    # requirement 用
    parser.add_argument("--domain", help="ドメイン（requirement）")
    parser.add_argument("--priority", help="優先度（requirement）")
    parser.add_argument("--origin", help="起票の由来（requirement）/ 起票ワークスペース（spec-issue）")
    parser.add_argument("--verification-method", dest="verification_method",
                        help="検証手段（requirement）")
    # spec-issue 用
    parser.add_argument("--target", help="変更対象（spec-issue）")
    parser.add_argument("--raised-by", dest="raised_by", help="発見元（spec-issue）")
    parser.add_argument("--change-type", dest="change_type", help="proposed_change_type（spec-issue）")
    parser.add_argument("--delegated-to", dest="delegated_to",
                        help="委託先（spec-issue。`<ws>:<ID>` カンマ区切り。SDD-FR-132）")
    # task 用（design でも implements を任意で使える）
    parser.add_argument("--implements", help="実装対象の要件 ID（task では必須 / design では任意）")
    parser.add_argument("--depends-on", dest="depends_on", help="依存タスク（task。例: [] や [CORE-TSK-001]）")
    parser.add_argument("--boundary", help="触れてよいパス（task）")
    # design(DSN) 用
    parser.add_argument("--status", help="status（design。既定 draft。STATUSES 語彙で検証）")
    parser.add_argument("--owner", help="担当者ハンドル（design）")
    # gate(GatePassage) 用
    parser.add_argument("--gate", choices=sorted(GATE_CHECKLIST_REF),
                        help="Gate 種別（gate。discovery / design / promotion）")
    parser.add_argument("--arbiter", help="裁定者（gate）")
    parser.add_argument("--scope", help="対象成果物 ID のカンマ区切り（gate）")
    parser.add_argument("--decision-ref", dest="decision_ref", action="append",
                        help="確認した裁定記録の所在（gate。複数回指定可）")
    parser.add_argument("--checklist-ref", dest="checklist_ref",
                        help="チェックリストの所在（gate。既定は gate 種別ごとの gates.md アンカー）")
    args = parser.parse_args()

    if args.kind == "task" and not args.implements:
        print("ERROR: task の生成には --implements <要件ID> が必須です", file=sys.stderr)
        return 2
    if args.kind == "gate":
        # GatePassage は必須項目が揃わないと spec_inspect を PASS しない。
        # 空の雛形を作って FAIL させるより、生成前に不足を告げる（CORE-FR-004 の雛形契約）
        missing = [flag for flag, value in (
            ("--gate", args.gate), ("--arbiter", args.arbiter), ("--scope", args.scope),
            ("--decision-ref", args.decision_ref),
        ) if not value]
        if missing:
            print(f"ERROR: gate の生成には {' / '.join(missing)} が必須です", file=sys.stderr)
            return 2

    root = Path(args.workspace).resolve()

    # 統制語彙の検証（CORE-FR-010）: ファイル書き込み前に fail させ承認後の手戻りを防ぐ
    vocab_error = validate_vocab(args, root / ".spec" / "requirements")
    if vocab_error is not None:
        print(f"ERROR: {vocab_error}", file=sys.stderr)
        return 2

    directory = root / ".spec" / KIND_DIR[args.kind]
    # 採番の走査範囲は spec_inspect のレジストリ走査と一致させる（SDD-FR-162）
    recursive = KIND_DIR[args.kind] in RECURSIVE_ARTIFACT_DIRS

    provisional_num = (args.number if args.number is not None
                       else next_number(directory, args.prefix, recursive))
    provisional = directory / f"{args.prefix}-{provisional_num:03d}.md"
    selected = {}

    def prepare(_owner):
        # SDD-FR-144: workspace lock取得後に採番候補を必ず再計算する。
        num = (args.number if args.number is not None
               else next_number(directory, args.prefix, recursive))
        ident = f"{args.prefix}-{num:03d}"
        dest = directory / f"{ident}.md"
        if dest.exists():
            raise MutationError(
                "mutation-conflict",
                f"{dest} は既に存在します（上書き・自動再採番しません）",
                1,
            )
        if args.kind == "requirement":
            body = render_requirement(ident, args)
        elif args.kind == "spec-issue":
            body = render_spec_issue(ident, args)
        elif args.kind == "design":
            body = render_design(ident, args)
        elif args.kind == "gate":
            body = render_gate(ident, args)
        else:
            body = render_task(ident, args)
        selected.update({"ident": ident, "dest": dest})
        return TransactionPlan(
            changes=(FileChange(dest, None, body.encode("utf-8")),),
            metadata={"kind": args.kind, "artifact_id": ident},
        )

    try:
        mutate(
            root,
            f"scaffold {args.kind} {args.prefix}",
            (provisional,),
            prepare,
        )
    except MutationError as error:
        print(f"ERROR [{error.code}]: {error}", file=sys.stderr)
        return error.exit_code

    print(f"生成: {selected['ident']} → {selected['dest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
