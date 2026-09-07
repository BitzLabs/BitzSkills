#!/usr/bin/env python3
"""Generate deterministic Core 1.0 performance fixture trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


GENERATOR_VERSION = "1.0"


def req_id(number: int) -> str:
    return f"REQ-{number:06d}"


def add_relation(relations: dict[tuple[str, int], list[str]], owner: tuple[str, int], target: str) -> None:
    if target in relations[owner]:
        raise ValueError(f"duplicate relation: {owner} -> {target}")
    relations[owner].append(target)


def single_model(manifest: dict) -> tuple[list[str], dict[tuple[str, int], int], dict[tuple[str, int], list[str]]]:
    workspace_ids = ["root"]
    statement_counts = {("root", number): 4 if number <= 100 else 3 for number in range(1, 301)}
    relations: dict[tuple[str, int], list[str]] = defaultdict(list)

    for target in range(2, 21):
        add_relation(relations, ("root", 1), req_id(target))

    remaining = manifest["counts"]["relations"] - 19
    for source in range(22, 301):
        for target in range(21, source):
            if remaining == 0:
                break
            add_relation(relations, ("root", source), req_id(target))
            remaining -= 1
        if remaining == 0:
            break
    if remaining:
        raise ValueError(f"cannot allocate {remaining} single-workspace relations")
    return workspace_ids, statement_counts, relations


def federation_model(manifest: dict) -> tuple[list[str], dict[tuple[str, int], int], dict[tuple[str, int], list[str]]]:
    workspace_ids = ["root"] + [f"ws{number:02d}" for number in range(1, 20)]
    statement_counts = {(workspace_id, number): 1 for workspace_id in workspace_ids for number in range(1, 51)}
    relations: dict[tuple[str, int], list[str]] = defaultdict(list)

    for target in range(2, 8):
        add_relation(relations, ("root", 1), req_id(target))
    for target in range(1, 8):
        add_relation(relations, ("root", 1), f"ws01::{req_id(target)}")
    for target in range(1, 7):
        add_relation(relations, ("root", 1), f"ws02::{req_id(target)}")

    reserved_origins = {
        "root": set(range(1, 8)),
        "ws01": set(range(1, 8)),
        "ws02": set(range(1, 7)),
    }
    remaining = manifest["counts"]["relations"] - 19
    for workspace_id in workspace_ids:
        reserved = reserved_origins.get(workspace_id, set())
        for source in range(2, 51):
            if source in reserved:
                continue
            for target in range(1, source):
                if remaining == 0:
                    break
                add_relation(relations, (workspace_id, source), req_id(target))
                remaining -= 1
            if remaining == 0:
                break
        if remaining == 0:
            break
    if remaining:
        raise ValueError(f"cannot allocate {remaining} federation relations")
    return workspace_ids, statement_counts, relations


def workspace_path(root: Path, workspace_id: str) -> Path:
    return root if workspace_id == "root" else root / "workspaces" / workspace_id


def yaml_string_list(values: list[str], indent: int) -> list[str]:
    prefix = " " * indent
    return [f'{prefix}- "{value}"' for value in values]


def render_config(kind: str, workspace_ids: list[str], workspace_id: str) -> bytes:
    lines = [
        'schemaVersion: "1.0"',
        "language: ja",
        'earsAi: "1.0"',
        "workspace:",
        f"  id: {workspace_id}",
        "context:",
        "  maxDocuments: 20",
        "  maxBytes: 131072",
    ]
    if kind == "single":
        lines.extend([
            "verify:",
            "  timeoutSeconds: 300",
            "  commands:",
            "    default:",
            '      argv: [python3, .perf/noop_command.py, "{tests}"]',
            "      cwd: .",
        ])
    elif workspace_id == "root":
        lines.extend(["monorepo:", "  maxMembers: 20", "  members:"])
        for member_id in workspace_ids[1:]:
            lines.extend([f"    - id: {member_id}", f"      path: workspaces/{member_id}"])
    return ("\n".join(lines) + "\n").encode()


def render_requirement(
    workspace_id: str,
    number: int,
    statement_count: int,
    relation_targets: list[str],
    seed: int,
    include_verify: bool,
) -> bytes:
    identifier = req_id(number)
    title = f"Performance requirement {number:06d}"
    lines = ["---", f"id: {identifier}", f'title: "{title}"', "status: approved"]
    if relation_targets:
        lines.extend(["relations:", "  requires:"])
        lines.extend(yaml_string_list(relation_targets, 4))
    if include_verify:
        lines.extend(["tests:", "  - path: tests/perf_noop.test", "    covers:"])
        lines.extend(yaml_string_list([f"{identifier}:AC-{index:02d}" for index in range(1, statement_count + 1)], 6))
        lines.append("    command: default")
    lines.extend([
        "---",
        "",
        f"# {identifier} {title}",
        "",
        "## Intent",
        "",
        f"Seed {seed} deterministic performance input for workspace {workspace_id}.",
        "",
        "## Acceptance Criteria",
        "",
    ])
    for index in range(1, statement_count + 1):
        lines.append(
            f"- [{identifier}:AC-{index:02d}] [ACTOR:Core] [WHEN] performance fixture input {number:06d}-{index:02d} is processed "
            f"[MUST] [THEN] deterministic result {workspace_id}-{number:06d}-{index:02d} is produced."
        )
    lines.extend(["", "## Verification", "", "Validated by the performance fixture harness.", ""])
    return "\n".join(lines).encode()


def write_tree(root: Path, manifest: dict) -> tuple[dict, dict[tuple[str, int], list[str]]]:
    kind = manifest["kind"]
    if kind == "single":
        workspace_ids, statement_counts, relations = single_model(manifest)
    elif kind == "federation":
        workspace_ids, statement_counts, relations = federation_model(manifest)
    else:
        raise ValueError(f"unsupported kind: {kind}")

    for workspace_id in workspace_ids:
        base = workspace_path(root, workspace_id)
        (base / ".spec" / "requirements").mkdir(parents=True, exist_ok=True)
        (base / ".spec" / "bitz.yaml").write_bytes(render_config(kind, workspace_ids, workspace_id))
        maximum = 300 if kind == "single" else 50
        for number in range(1, maximum + 1):
            include_verify = kind == "single" and number == 300
            content = render_requirement(
                workspace_id,
                number,
                statement_counts[(workspace_id, number)],
                relations[(workspace_id, number)],
                manifest["seed"],
                include_verify,
            )
            path = base / ".spec" / "requirements" / f"{req_id(number)}.md"
            path.write_bytes(content)

    if kind == "single":
        (root / ".perf").mkdir()
        (root / ".perf" / "noop_command.py").write_bytes(
            b"#!/usr/bin/env python3\nimport sys\nraise SystemExit(0 if len(sys.argv) >= 1 else 1)\n"
        )
        (root / "tests").mkdir()
        (root / "tests" / "perf_noop.test").write_bytes(b"fixed no-op performance test input\n")

    stats = {
        "workspaces": len(workspace_ids),
        "specs": len(statement_counts),
        "statements": sum(statement_counts.values()),
        "relations": sum(len(values) for values in relations.values()),
    }
    return stats, relations


def canonical_target(owner: str, target: str) -> tuple[str, int]:
    if "::" in target:
        workspace_id, local_id = target.split("::", 1)
    else:
        workspace_id, local_id = owner, target
    return workspace_id, int(local_id.removeprefix("REQ-"))


def validate_model(manifest: dict, stats: dict, relations: dict[tuple[str, int], list[str]], root: Path) -> None:
    if stats != manifest["counts"]:
        raise ValueError(f"count mismatch: expected {manifest['counts']}, got {stats}")
    observed_shape = measure_shape(root, stats)
    if observed_shape != manifest["shape"]:
        raise ValueError(f"shape mismatch: expected {manifest['shape']}, got {observed_shape}")

    nodes = set(relations)
    for owner, targets in relations.items():
        for target in targets:
            resolved = canonical_target(owner[0], target)
            if resolved not in nodes:
                raise ValueError(f"missing relation target: {owner} -> {target}")

    visiting: set[tuple[str, int]] = set()
    visited: set[tuple[str, int]] = set()

    def visit(node: tuple[str, int]) -> None:
        if node in visiting:
            raise ValueError(f"relation cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for target in relations[node]:
            visit(canonical_target(node[0], target))
        visiting.remove(node)
        visited.add(node)

    for node in nodes:
        visit(node)

    start_text = manifest["benchmark"]["contextRoot"]
    start = canonical_target("root", start_text)
    reached: set[tuple[str, int]] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in reached:
            continue
        reached.add(node)
        stack.extend(canonical_target(node[0], target) for target in relations[node])
    expected_docs = manifest["benchmark"]["contextDocuments"]
    expected_workspaces = manifest["benchmark"]["contextWorkspaces"]
    if len(reached) != expected_docs or len({node[0] for node in reached}) != expected_workspaces:
        raise ValueError(f"context shape mismatch: documents={len(reached)}, workspaces={len({node[0] for node in reached})}")

    context_input_bytes = 0
    for workspace_id, number in reached:
        path = workspace_path(root, workspace_id) / ".spec" / "requirements" / f"{req_id(number)}.md"
        context_input_bytes += path.stat().st_size
    if context_input_bytes > manifest["benchmark"]["maxPresentationBytes"]:
        raise ValueError(f"context input exceeds presentation budget: {context_input_bytes}")


def measure_shape(root: Path, stats: dict) -> dict:
    spec_bytes = sum(path.stat().st_size for path in root.rglob(".spec/requirements/REQ-*.md"))
    count = stats["specs"]
    return {
        "specBytes": spec_bytes,
        "meanSpecBytes": {"numerator": spec_bytes, "denominator": count},
        "statementsPerSpec": {"numerator": stats["statements"], "denominator": count},
        "edgeDensity": {"numerator": stats["relations"], "denominator": count * (count - 1)},
    }


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted((path for path in root.rglob("*") if path.is_file()), key=lambda path: path.relative_to(root).as_posix())
    for path in files:
        relative = path.relative_to(root).as_posix().encode()
        content = path.read_bytes()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--print-digest", action="store_true", help="print a new digest without enforcing expectedTreeDigest")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("generatorVersion") != GENERATOR_VERSION:
        raise ValueError("generatorVersion mismatch")
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError(f"output must be absent or empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    stats, relations = write_tree(args.output, manifest)
    validate_model(manifest, stats, relations, args.output)
    digest = tree_digest(args.output)
    if not args.print_digest and digest != manifest["expectedTreeDigest"]:
        raise ValueError(f"tree digest mismatch: expected {manifest['expectedTreeDigest']}, got {digest}")
    result = {"datasetId": manifest["datasetId"], "treeDigest": digest, "counts": stats, "shape": measure_shape(args.output, stats)}
    json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
