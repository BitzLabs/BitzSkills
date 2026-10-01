"""ワークスペースの探索。

ワークスペース・設定仕様 §1に従い、現在のディレクトリから親の方向へ ``.spec/bitz.yaml`` を探す。
Gitを利用できるときは、リポジトリの境界を越えない。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .gitutil import GitInfo, show_toplevel


@dataclass
class WorkspaceLocation:
    root: str | None  # ワークスペースのルート（絶対パス）。見つからなければNone。
    config_path: str | None  # 見つかった`.spec/bitz.yaml`の絶対パス。


def locate_workspace(start_dir: str, git: GitInfo, env: dict[str, str]) -> WorkspaceLocation:
    start = os.path.abspath(start_dir)
    boundary: str | None = None
    if git.available and git.executable:
        boundary = show_toplevel(git.executable, start, env)
        if boundary:
            boundary = os.path.abspath(boundary)

    current = start
    while True:
        candidate = os.path.join(current, ".spec", "bitz.yaml")
        if os.path.isfile(candidate) and not os.path.islink(os.path.join(current, ".spec")):
            return WorkspaceLocation(root=current, config_path=candidate)
        if boundary is not None and os.path.normpath(current) == os.path.normpath(boundary):
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return WorkspaceLocation(root=None, config_path=None)
