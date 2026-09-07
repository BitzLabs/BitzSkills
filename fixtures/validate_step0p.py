#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""Validate Step 0-P inputs without a Core executable. Run with uv run."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    schemas = sorted(ROOT.glob("performance/schemas/*.json")) + sorted(ROOT.glob("comparison/*.schema.json"))
    for path in schemas:
        Draft202012Validator.check_schema(read(path))
    pairs = [
        ("performance/datasets/*.json", "performance/schemas/dataset.schema.json"),
        ("performance/environments/*.json", "performance/schemas/environment.schema.json"),
        ("performance/benchmark-plan.json", "performance/schemas/benchmark-plan.schema.json"),
        ("comparison/tasks/*.json", "comparison/task.schema.json"),
        ("comparison/protocol.json", "comparison/protocol.schema.json"),
        ("comparison/answer-key.json", "comparison/answer-key.schema.json"),
    ]
    validated = 0
    for pattern, schema in pairs:
        paths = sorted(ROOT.glob(pattern))
        assert paths, pattern
        validator = Draft202012Validator(read(ROOT / schema))
        for path in paths:
            validator.validate(read(path))
            validated += 1
    datasets = {read(p)["datasetId"]: p for p in ROOT.glob("performance/datasets/*.json")}
    plan = read(ROOT / "performance/benchmark-plan.json")
    assert (ROOT / "performance" / plan["environment"]).is_file()
    assert len({case["id"] for case in plan["cases"]}) == len(plan["cases"])
    assert all(case["dataset"] in datasets for case in plan["cases"])
    protocol = read(ROOT / "comparison/protocol.json")
    assert sorted(protocol["taskIds"]) == sorted(p.stem for p in ROOT.glob("comparison/tasks/*.json"))
    results = []
    with tempfile.TemporaryDirectory(prefix="bitz-step0p-") as temporary:
        for identifier, manifest in sorted(datasets.items()):
            runs = []
            for index in range(2):
                command = [sys.executable, str(ROOT / "performance/scripts/generate_fixture.py"), str(manifest), str(Path(temporary) / f"{identifier}-{index}")]
                runs.append(subprocess.check_output(command, text=True))
            assert runs[0] == runs[1], identifier
            results.append(json.loads(runs[0]))
            # A corrupted shape must be rejected even when the original digest is retained.
            mutated = copy.deepcopy(read(manifest))
            mutated["shape"]["specBytes"] += 1
            bad_manifest = Path(temporary) / f"{identifier}-bad.json"
            bad_manifest.write_text(json.dumps(mutated), encoding="utf-8")
            command = [sys.executable, str(ROOT / "performance/scripts/generate_fixture.py"), str(bad_manifest), str(Path(temporary) / f"{identifier}-bad")]
            rejected = subprocess.run(command, capture_output=True, text=True)
            assert rejected.returncode != 0 and "shape mismatch" in rejected.stderr
    print(json.dumps({"status": "Passed", "schemas": len(schemas), "inputs": validated, "generationRunsPerDataset": 2, "shapeRejectionChecks": len(datasets), "datasets": results}, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
