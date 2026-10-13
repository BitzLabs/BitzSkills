"""単独操作の作業ワークスペースの決定（複合ワークスペース仕様 §3）。

`check`、`context`、`verify`、`doctor`が同じ規則で作業ワークスペースを決める。リポジトリのルートの設定が
複合ワークスペースを宣言している（:func:`bitz.multiws.is_declared`）場合は、全体事前検査（:func:`bitz.multiws.precheck`）の
結果のカタログを使い、作業ワークスペースを次の順で決める。

1. 位置引数の修飾IDの所有ワークスペース
2. `--workspace`（カタログ内のルートまたはメンバーのID）
3. 現在のディレクトリの最寄りの設定のID

1.と2.が食い違えば引数不正（終了コード4）。単一ワークスペースは従来の軽量な経路のままで、事前検査を行わない。
事前検査が失敗したときの扱いは各操作の従来のまま（この関数は作業ワークスペースを置き換えず、``pre.ok``が偽の
``pre``を返す。呼び出し側は``multi_active``で判定する）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import config as config_mod
from . import gitutil
from . import multirelate
from . import multiws
from .errors import CliArgError
from .workspace import WorkspaceLocation


@dataclass
class ActiveSelection:
    loc: WorkspaceLocation
    #: 作業ワークスペースのリポジトリのルートからの相対パス（ルートワークスペースと単一ワークスペースは``.``）。
    rel_path: str
    #: 複合ワークスペースを宣言していれば全体事前検査の結果（失敗していることもある）。宣言していなければ``None``。
    pre: multiws.PrecheckResult | None

    @property
    def multi_active(self) -> bool:
        return self.pre is not None and self.pre.ok


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
    ears_version_code: str = "SPEC-EARS-VERSION-001",
) -> ActiveSelection:
    """作業ワークスペースを決める。``subject``は引数不正のメッセージの「起点」「対象」の呼び方。"""

    qualified_prefixes = {q[0] for t in positionals if (q := multirelate.parse_qualified(t)) is not None}
    if qualified_prefixes:
        if len(qualified_prefixes) > 1:
            raise CliArgError(operation, f"複数の{subject}が異なるワークスペースに属しています")
        target_ws_id: str | None = next(iter(qualified_prefixes))
        if requested_workspace is not None and requested_workspace != target_ws_id:
            raise CliArgError(operation, f"{subject}のワークスペースと--workspaceが一致しません: {target_ws_id}")
    else:
        target_ws_id = requested_workspace

    if not multiws.is_declared(cwd, git, env):
        return ActiveSelection(loc, ".", None)

    pre = multiws.precheck(
        cwd, git, env, extra_config_revs=list(extra_config_revs or []), ears_version_code=ears_version_code
    )
    rel_path = "."
    if pre.ok:
        if target_ws_id is None and loc.config_path is not None:
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
