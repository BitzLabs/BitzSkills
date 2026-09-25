"""`bitz.compat` — 外形判定（consumer）と複合workspace移行検証（migration）。

`00_共通契約/04_適合fixture仕様.md` §3の``runner: consumer``・``runner: migration``が
``python -m bitz.compat <runner> <argv...>``として起動するmodule。公開CLI `bitz` には
commandを追加しない（Core配布物の一部として同梱するだけの独立entrypoint）。

標準出力は``{"outcome": "<値>"}``のJSON 1件とLFだけを書く（`accepted`／`rejected`／`passed`／
`rejected`）。終了コードは``accepted``・``passed``が0、``rejected``が1。読取り専用（fileを書かない）。

## consumer result-shape <path>

指定JSONを共通結果契約 §2の排他的外形で判定する（`workspace`を持つ単一workspace外形と、
`multiWorkspace`＋`workspaces`を持つ複合workspace外形は互いに排他）。

## migration to-multi-workspace / rollback

`複合workspace仕様`の複合workspace化・rollbackが原子的に完了しているかどうかを検証する。
Coreは移行そのものを実行しない（運用手順は`18_互換性・移行・運用review.md`のFED-MIG-003・005が
定める「migration branch上で全member設定とroot catalogを同じ変更集合へ加える」手作業）。
このconsumerは、その変更集合が既に一貫した終端状態かどうかだけを読取り専用で判定する。

- ``to-multi-workspace``: 現在snapshotの複合workspace catalog（`複合workspace仕様 §2〜§5`）と
  修飾関係（同 §5・関係・トレースモデル §5.1）を検証する。Git基準版比較（`SPEC-STATE-TRANSITION-001`
  等）は行わない。複合workspace化は文書を別workspaceへ再配置する操作であり、旧単一workspace時点の
  基準版と比較すると、移動先が別workspaceであることを理由に「削除」と誤検出するため
  （`check --all-workspaces`の既定経路とは異なる。`check._run_all_workspaces_members`を
  ``resolved_base=None``で直接呼び、事前検査後のcatalog・関係・所有境界検査だけを使う）。
- ``rollback``: 単一workspaceへ戻った現在snapshotに対して通常の`check --full`（Git基準版比較込み）を
  行う。rollback後は文書が単一workspaceの`root`直下だけに存在し、旧複合workspace時点の基準版には
  同じ文書が別workspace（member）配下にあったため、rollback後のcatalogと基準版のroot workspace
  catalogを比較しても同一文書の重複や誤った削除検出は起きない（基準版のroot workspace catalogは
  そのworkspace自身の`.spec/`だけを見るため、旧member配下にあった文書は基準版のroot側catalogに
  最初から含まれない）。修飾参照（``workspace::id``）が残っていれば、単一workspaceの索引では
  解決できず`SPEC-RELATION-MISSING-001`／`SPEC-TEST-COVERAGE-001`として`failed`になり、
  「修飾参照が残る部分rollbackの拒否」を実現する。まだ`multiWorkspace`を宣言したままなら
  rollback未完了として拒否する。
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
    """結果契約 §2の排他的外形判定（`workspace`単独 xor `multiWorkspace`＋`workspaces`）。"""

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
    """複合workspace化の現在snapshotをGit基準版比較なしで検証する。判定不能なら``None``。"""

    git = gitutil.detect_git(cwd, env)
    pre = multiws.precheck(cwd, git, env, extra_config_revs=[])
    if pre.discovery_failed:
        return None
    if not pre.ok:
        diags = sort_diagnostics([d.to_dict() for d in pre.diagnostics])
        return status_from_diagnostics(diags)
    if not pre.members:
        # まだmemberが登録されていない＝複合workspace化が完了していない。
        return None
    parsed = ParsedArgs(operation="check", flags=set())
    dummy_revision = {"base": "0" * 40, "commit": "0" * 40, "dirty": False}
    result, _exit_code = check_op._run_all_workspaces_members(  # noqa: SLF001（同package内の意図的な再利用）
        parsed, cwd, env, git, pre, dummy_revision, None, 0
    )
    return result["status"]


def _rollback_status(cwd: str, env: dict[str, str]) -> str | None:
    """完全rollback後の単一workspace snapshotを`check --full`で検証する。判定不能なら``None``。"""

    parsed = parse_argv(["check", "--full"])
    result, _exit_code = check_op.run(parsed, cwd, env)
    if "multiWorkspace" in result:
        # まだ複合workspaceのまま＝rollbackが完了していない。
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
