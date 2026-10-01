"""`bitz.compat` — 外形の判定（`consumer`）と、複合ワークスペースへの移行の検証（`migration`）。

`00_共通契約/04_適合fixture仕様.md` §3の``runner: consumer``・``runner: migration``が
``python -m bitz.compat <runner> <argv...>``として起動するモジュール。公開CLI `bitz` には
コマンドを追加しない（Coreの配布物の一部として同梱するだけの、独立したエントリポイント）。

標準出力は``{"outcome": "<値>"}``のJSON 1件とLFだけを書く（`accepted`／`rejected`／`passed`／
`rejected`）。終了コードは``accepted``・``passed``が0、``rejected``が1。読取り専用（ファイルを書かない）。

## consumer result-shape <path>

指定したJSONを、結果・診断・終了コード §2の排他的な外形で判定する（`workspace`を持つ単一ワークスペースの外形と、
`multiWorkspace`と`workspaces`を持つ複合ワークスペースの外形は、互いに排他）。

## migration to-multi-workspace / rollback

`複合ワークスペース仕様`の、複合ワークスペース化とロールバックが原子的に完了しているかどうかを検証する。
Coreは移行そのものを実行しない（運用手順は`18_互換性・移行・運用review.md`のFED-MIG-003・005が
定める、「移行用のブランチ上で、すべてのメンバーの設定とルートワークスペースのカタログを同じ変更集合へ加える」手作業）。
この`consumer`は、その変更集合が既に一貫した終端状態かどうかだけを、読取り専用で判定する。

- ``to-multi-workspace``: 現在のスナップショットにある複合ワークスペースのカタログ（`複合ワークスペース仕様 §2〜§5`）と
  修飾関係（同 §5・関係・トレースモデル §5.1）を検証する。Gitの基準版との比較（`SPEC-STATE-TRANSITION-001`
  など）は行わない。複合ワークスペース化は、文書を別のワークスペースへ再配置する操作であり、旧単一ワークスペースの時点の
  基準版と比較すると、移動先が別のワークスペースであることを理由に「削除」と誤検出するため
  （`check --all-workspaces`の既定の経路とは異なる。`check._run_all_workspaces_members`を
  ``resolved_base=None``で直接呼び、事前検査の後は、文書の一覧・関係・所有境界の検査だけを使う）。
- ``rollback``: 単一ワークスペースへ戻った現在のスナップショットに対して、通常の`check --full`（Gitの基準版との比較を含む）を
  行う。ロールバックの後は、文書が単一ワークスペースの`root`直下だけに存在し、旧複合ワークスペースの時点の基準版には
  同じ文書が別のワークスペース（メンバー）の配下にあったため、ロールバックの後の文書の一覧と、基準版のルートワークスペースの
  文書の一覧を比較しても、同一文書の重複や誤った削除の検出は起きない（基準版のルートワークスペースの
  文書の一覧は、そのワークスペース自身の`.spec/`だけを見るため、旧メンバーの配下にあった文書は、基準版のルート側の
  文書の一覧に最初から含まれない）。修飾参照（``workspace::id``）が残っていれば、単一ワークスペースの索引では
  解決できず、`SPEC-RELATION-MISSING-001`／`SPEC-TEST-COVERAGE-001`として`failed`になり、
  「修飾参照が残る、部分的なロールバックの拒否」を実現する。まだ`multiWorkspace`を宣言したままなら、
  ロールバックが未完了として拒否する。
"""

from __future__ import annotations

import json
import os
import sys

from . import check as check_op
from . import gitutil
from . import multiws
from .cliargs import ParsedArgs, parse_argv
from .errors import CliArgError
from .resultmodel import sort_diagnostics, status_from_diagnostics

_PASS_STATUSES = frozenset({"passed", "passed_with_warnings"})


def _emit_outcome(outcome: str) -> None:
    sys.stdout.write(json.dumps({"outcome": outcome}, ensure_ascii=False) + "\n")


def _result_shape_outcome(obj: object) -> str:
    """結果・診断・終了コード §2の、排他的な外形の判定（`workspace`だけを持つか、`multiWorkspace`と`workspaces`の組を持つかの、どちらか一方）。"""

    if not isinstance(obj, dict):
        return "rejected"
    has_single = "workspace" in obj
    has_multi = "multiWorkspace" in obj and "workspaces" in obj
    if has_single and not has_multi:
        return "accepted"
    if has_multi and not has_single:
        return "accepted"
    return "rejected"


def _run_consumer(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "result-shape":
        sys.stderr.write("bitz.compat consumer: result-shape <path>を指定してください\n")
        return 2
    path = argv[1]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"bitz.compat consumer: 読み取りに失敗しました: {path}: {exc}\n")
        return 2
    outcome = _result_shape_outcome(obj)
    _emit_outcome(outcome)
    return 0 if outcome == "accepted" else 1


def _to_multi_workspace_status(cwd: str, env: dict[str, str]) -> str | None:
    """複合ワークスペース化した現在のスナップショットを、Gitの基準版との比較なしで検証する。判定できなければ``None``。"""

    git = gitutil.detect_git(cwd, env)
    pre = multiws.precheck(cwd, git, env, extra_config_revs=[])
    if pre.discovery_failed:
        return None
    if not pre.ok:
        diags = sort_diagnostics([d.to_dict() for d in pre.diagnostics])
        return status_from_diagnostics(diags)
    if not pre.members:
        # まだメンバーが登録されていない＝複合ワークスペース化が完了していない。
        return None
    parsed = ParsedArgs(operation="check", flags=set())
    dummy_revision = {"base": "0" * 40, "commit": "0" * 40, "dirty": False}
    result, _exit_code = check_op._run_all_workspaces_members(  # noqa: SLF001（同package内の意図的な再利用）
        parsed, cwd, env, git, pre, dummy_revision, None, 0
    )
    return result["status"]


def _rollback_status(cwd: str, env: dict[str, str]) -> str | None:
    """完全なロールバックの後の単一ワークスペースのスナップショットを`check --full`で検証する。判定できなければ``None``。"""

    parsed = parse_argv(["check", "--full"])
    result, _exit_code = check_op.run(parsed, cwd, env)
    if "multiWorkspace" in result:
        # まだ複合ワークスペースのまま＝ロールバックが完了していない。
        return None
    return result["status"]


def _run_migration(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("to-multi-workspace", "rollback"):
        sys.stderr.write(
            "bitz.compat migration: to-multi-workspaceまたはrollbackを指定してください\n"
        )
        return 2
    cwd = os.getcwd()
    env = dict(os.environ)
    case = argv[0]
    try:
        if case == "to-multi-workspace":
            status = _to_multi_workspace_status(cwd, env)
        else:
            status = _rollback_status(cwd, env)
    except CliArgError as exc:
        sys.stderr.write(f"bitz.compat migration: {exc.context}: {exc.reason}\n")
        return 2
    outcome = "passed" if status in _PASS_STATUSES else "rejected"
    _emit_outcome(outcome)
    return 0 if outcome == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        sys.stderr.write("bitz.compat: runnerを指定してください\n")
        return 2
    runner, rest = argv[0], argv[1:]
    if runner == "consumer":
        return _run_consumer(rest)
    if runner == "migration":
        return _run_migration(rest)
    sys.stderr.write(f"bitz.compat: 未知のrunnerです: {runner}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
