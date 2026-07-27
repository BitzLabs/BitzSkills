#!/usr/bin/env python3
"""SDD-FR-143: local workspace task-binding index shared by update/inspect."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TaskBinding:
    path: Path
    status: str
    implements: tuple[str, ...]


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def parse_ids(value: str) -> tuple[str, ...]:
    value = value.strip()
    if not value:
        return ()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return tuple(item.strip() for item in value.split(",") if item.strip())


def build_task_index(workspace: Path) -> dict[tuple[Path, str], list[TaskBinding]]:
    root = workspace.resolve()
    index: dict[tuple[Path, str], list[TaskBinding]] = {}
    task_dir = root / ".spec" / "tasks"
    if not task_dir.exists():
        return index
    for path in sorted(task_dir.glob("*.md")):
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        implements = parse_ids(meta.get("implements", ""))
        binding = TaskBinding(
            path=path,
            status=meta.get("status", ""),
            implements=implements,
        )
        for requirement_id in implements:
            index.setdefault((root, requirement_id), []).append(binding)
    return index


def tasks_for_requirement(workspace: Path, requirement_id: str) -> list[TaskBinding]:
    root = workspace.resolve()
    return build_task_index(root).get((root, requirement_id), [])
