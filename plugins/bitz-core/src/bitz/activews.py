"""単独操作の作業ワークスペースの決定（複合ワークスペース仕様 §3）。

`check`、`context`、`verify`、`doctor`が同じ規則で作業ワークスペースを決める。リポジトリのルートの設定が
複合ワークスペースを宣言している（:func:`bitz.multiws.is_declared`）場合は、全体事前検査（:func:`bitz.multiws.precheck`）の
結果のカタログを使い、作業ワークスペースを次の順で決める。

1. 位置引数の修飾IDの所有ワークスペース
2. `--workspace`（カタログ内のルートまたはメンバーのID）
3. 現在のディレクトリの最寄りの設定のID

1.と2.が食い違えば引数不正（終了コード4）。単一ワークスペースは従来の軽量な経路のままで、事前検査を行わない。

探索の開始位置が除外した範囲（``multiWorkspace.exclude``）にあるときは、複合ワークスペース仕様 §2.1に従う
（:func:`bitz.multiws.resolve_scope`）。経路の上に``multiWorkspace``を宣言した設定があれば、そのディレクトリを入れ子の
複合ワークスペースのルートとして、上の規則をそのルートについて適用する（:func:`bitz.multiws.precheck`の``repo_root``が入れ子のルート）。
宣言した設定がなければ単一ワークスペースの経路（``pre``は``None``）で、外側の全体事前検査は行わない。

全体事前検査が非成功のときは、作業ワークスペースを置き換えず、``stop``（:class:`StoppedSelection`）を持つ
:class:`ActiveSelection` を返す。呼び出し側は作業ワークスペースの処理、コンテキストの解決、テストコマンドの実行を始めず、
全体事前検査の診断を最上位の``diagnostics``に置いた単独結果を返す（複合ワークスペース仕様 §7、ADR-063）。
``--workspace``のIDがカタログになくても、全体事前検査が非成功ならこの結果を返す（終了コード4にしない）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import config as config_mod
from . import gitutil
from . import lex
from . import multirelate
from . import multiws
from . import reportio
from .errors import CliArgError
from .resultmodel import sort_diagnostics, status_from_diagnostics
from .workspace import WorkspaceLocation


@dataclass
class StoppedSelection:
    """複合ワークスペースの単独操作が全体事前検査で停止した結果の材料（結果・診断・終了コード §2）。"""

    #: 全体事前検査の診断（``to_dict``済み。並べ替えは呼び出し側）。
    diagnostics: list[dict]
    #: 選択した最も近い設定がカタログに登録されていて、その設定自身が有効なIDを持つときだけ、そのID。それ以外は``None``。
    workspace_id: str | None
    #: 選択した設定のディレクトリの複合ワークスペースのルートからの相対パス（ルートは``.``）。
    rel_path: str
    #: 選択した設定のディレクトリ（絶対パス）。停止結果のレポートの保存先（``.spec/reports/``）の基準。
    workspace_root: str
    #: Gitの境界を確定できずに停止したか（``SPEC-MULTI-GIT-001``）。真なら``revision``は``null``。
    git_boundary_unknown: bool


@dataclass
class ActiveSelection:
    loc: WorkspaceLocation
    #: 作業ワークスペースの複合ワークスペースのルートからの相対パス（ルートワークスペースと単一ワークスペースは``.``）。
    rel_path: str
    #: 複合ワークスペースを宣言していれば全体事前検査の結果（失敗していることもある）。宣言していなければ``None``。
    pre: multiws.PrecheckResult | None
    #: 全体事前検査が非成功のときの停止結果の材料。それ以外は``None``。
    stop: StoppedSelection | None = None

    @property
    def multi_active(self) -> bool:
        return self.pre is not None and self.pre.ok


def _stopped_selection(pre: multiws.PrecheckResult, loc: WorkspaceLocation, ears_version_code: str) -> StoppedSelection:
    """停止した単独結果の``workspace``と``revision``の材料を求める（ADR-063の6）。"""

    assert loc.root is not None and pre.repo_root is not None
    rel_path = os.path.relpath(os.path.realpath(loc.root), os.path.realpath(pre.repo_root)).replace(os.sep, "/")
    workspace_id: str | None = None
    if loc.config_path is not None and multiws.selected_is_registered(pre, rel_path):
        selected = config_mod.read_config(loc.config_path, ears_version_code=ears_version_code)
        if selected.stop_stage != "config":
            # 複合ワークスペースでは`workspace.id`を必須とする（複合ワークスペース仕様 §2）ため、省略時の既定値`root`は
            # 有効なIDではない。設定が有効な`workspace.id`を明示し、メンバーではカタログのIDとも一致するときだけ、そのIDを返す
            # （カタログと食い違うIDでは同一性を構成できない。結果・診断・終了コード §2）。
            raw = selected.config if selected.config is not None else selected.parsed
            workspace_block = raw.get("workspace") if isinstance(raw, dict) else None
            explicit = workspace_block.get("id") if isinstance(workspace_block, dict) else None
            if isinstance(explicit, str) and lex.WORKSPACE_ID_RE.match(explicit) and (
                rel_path == "." or explicit == multiws.catalog_member_id(pre, rel_path)
            ):
                workspace_id = explicit
    return StoppedSelection(
        diagnostics=[d.to_dict() for d in pre.diagnostics],
        workspace_id=workspace_id,
        rel_path=rel_path,
        workspace_root=loc.root,
        git_boundary_unknown=any(d.code == "SPEC-MULTI-GIT-001" for d in pre.diagnostics),
    )


def current_revision(
    git: gitutil.GitInfo, cwd: str, env: dict[str, str], stop: StoppedSelection
) -> dict | None:
    """停止した``context``・``verify``の``revision``（``commit``と``dirty``）。Gitの境界を確定できずに停止したときは``None``。"""

    if stop.git_boundary_unknown or not (git.available and git.executable):
        return None
    head_commit = gitutil.resolve_commit(git.executable, cwd, env, "HEAD")
    if head_commit is None:
        return None
    return {"commit": head_commit, "dirty": gitutil.is_dirty(git.executable, cwd, env)}


def save_stop_report(stop: StoppedSelection, operation: str, result: dict) -> None:
    """``--report``が指定された停止結果を、選択した設定のディレクトリの``.spec/reports/``へ保存する（結果・診断・終了コード §8）。

    保存に失敗したときは``SPEC-REPORT-WRITE-001``を``result``の診断へ加え、状態を診断の最悪値で更新する。
    """

    failure = reportio.write_report(stop.workspace_root, stop.workspace_id, operation, result)
    if failure is not None:
        diagnostics = sort_diagnostics(list(result["diagnostics"]) + [failure.to_dict()])
        result["diagnostics"] = diagnostics
        result["status"] = status_from_diagnostics(diagnostics)


def select_active(
    operation: str,
    positionals: list[str],
    requested_workspace: str | None,
    cwd: str,
    git: gitutil.GitInfo,
    env: dict[str, str],
    loc: WorkspaceLocation,
    *,
    subject: str = "起点",
    extra_config_revs: list[str] | None = None,
    compare_git_configs: bool = False,
    ears_version_code: str = "SPEC-EARS-VERSION-001",
) -> ActiveSelection:
    """作業ワークスペースを決める。``subject``は引数不正のメッセージの「起点」「対象」の呼び方。

    ``compare_git_configs``は、全体事前検査でGitが認識する設定の列挙と比較するか（単独の`doctor`だけ真。
    単独の`context`・`check`・`verify`は、選択した最も近い設定だけをカタログと照合する。複合ワークスペース仕様 §7）。
    """

    qualified_prefixes = {q[0] for t in positionals if (q := multirelate.parse_qualified(t)) is not None}
    if qualified_prefixes:
        if len(qualified_prefixes) > 1:
            raise CliArgError(operation, f"複数の{subject}が異なるワークスペースに属しています")
        target_ws_id: str | None = next(iter(qualified_prefixes))
        if requested_workspace is not None and requested_workspace != target_ws_id:
            raise CliArgError(operation, f"{subject}のワークスペースと--workspaceが一致しません: {target_ws_id}")
    else:
        target_ws_id = requested_workspace

    if loc.config_path is None or loc.root is None or not multiws.is_declared(cwd, git, env, loc.config_path):
        return ActiveSelection(loc, ".", None)

    pre = multiws.precheck(
        cwd, git, env,
        extra_config_revs=list(extra_config_revs or []),
        ears_version_code=ears_version_code,
        nearest_config_path=loc.config_path,
        selected_dir=loc.root,
        compare_git_configs=compare_git_configs,
    )
    if pre.discovery_failed:
        return ActiveSelection(loc, ".", None)
    if not pre.ok:
        stop = _stopped_selection(pre, loc, ears_version_code)
        return ActiveSelection(loc, stop.rel_path, pre, stop)
    rel_path = "."
    if target_ws_id is None:
        target_ws_id = config_mod.read_config(loc.config_path).workspace_id
    if target_ws_id == pre.root_id:
        assert pre.repo_root is not None
        loc = WorkspaceLocation(
            root=pre.repo_root, config_path=os.path.join(pre.repo_root, ".spec", "bitz.yaml")
        )
    else:
        member = next((m for m in pre.members if m.id == target_ws_id), None)
        if member is not None:
            loc = WorkspaceLocation(
                root=member.root, config_path=os.path.join(member.root, ".spec", "bitz.yaml")
            )
            rel_path = member.path
    return ActiveSelection(loc, rel_path, pre)
