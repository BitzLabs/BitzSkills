"""workspace探索。

`workspace・設定仕様 §1` に従い、current directoryから親方向へ ``.spec/bitz.yaml`` を探す。
Git利用時はrepository境界を越えない。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .gitutil import GitInfo, show_toplevel


@dataclass
class WorkspaceLocation:
    root: str | None  # workspace root（絶対path）。見つからなければNone。
    config_path: str | None  # 見つかった`.spec/bitz.yaml`の絶対path。


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
