"""Reviewed non-success Context vectors: stale Digest, out-of-set expand, closure limits.

No Core operation is implemented or emulated here. These fixtures share the
Digest corpus so that the reported Digest, where one exists, is the committed
golden value rather than a separately invented constant.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
GOLDEN = digest_reference.digest(
    digest_reference.canonical_bytes(digest_reference.reviewed_digest_input("SINGLE-042")))
WRONG_DIGEST = "sha256:" + "0" * 64
ROOT_DOCUMENT = ".spec/requirements/REQ-001.md"
EMPTY_COVERAGE = {
    **{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
       for modality in ("must", "should", "may")},
    "adjacent": [],
}
# 4 KiB is the lowest configurable context.maxBytes, so the padding only has to
# push the standard presentation past it, not past the 128 KiB default.
PADDING_LINE = "この段落は標準提示のbyte数を上限検査のために増やす固定文である。\n"
PADDING = PADDING_LINE * 40

# id: (option tail, extra config, REQ body, status, exit code, complete, documentCount,
#      digest, Diagnostic code, source, summary)
CASES = {
    "SINGLE-046": (
        ["--expect-digest", WRONG_DIGEST], "", digest_reference.REQ_BODY,
        "blocked", 2, True, 2, GOLDEN, "CTX-STALE-001",
        {"kind": "invocation", "argument": "--expect-digest"},
        "期待Digestが現在のContext Digestと一致しません"),
    "SINGLE-047": (
        ["--expand", "ADR-001"], "", digest_reference.REQ_BODY,
        "failed", 1, True, 2, GOLDEN, "CTX-PROJECTION-001",
        {"kind": "invocation", "argument": "ADR-001"},
        "expand対象ADR-001は完全解決集合にありません"),
    "SINGLE-048-01": (
        [], "context:\n  maxDocuments: 1\n", digest_reference.REQ_BODY,
        "blocked", 2, False, 0, None, "CTX-LIMIT-001",
        {"kind": "file", "workspaceId": "root", "path": ROOT_DOCUMENT},
        "完全Context閉包が文書数上限を超過しました"),
    "SINGLE-048-02": (
        [], "context:\n  maxBytes: 4096\n",
        digest_reference.REQ_BODY.replace(
            "Digest goldenの固定要求を定義する。\n", "Digest goldenの固定要求を定義する。\n\n" + PADDING, 1),
        "blocked", 2, False, 0, None, "CTX-LIMIT-001",
        {"kind": "file", "workspaceId": "root", "path": ROOT_DOCUMENT},
        "完全Context閉包がbyte上限を超過しました"),
}
DESCRIPTIONS = {
    "SINGLE-046": "expect-digest不一致でstaleを検出し新しい仕様を暗黙受諾しない",
    "SINGLE-047": "解決集合外のexpandを拒否し依存へ追加しない",
    "SINGLE-048-01": "完全閉包の文書数上限超過で部分Bundleを返さない",
    "SINGLE-048-02": "完全閉包のbyte上限超過で部分Bundleを返さない",
}


def reviewed_inputs(identifier):
    _, extra_config, req_body, *_ = CASES[identifier]
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = (digest_reference.CONFIG + extra_config).encode()
    inputs[digest_reference.REQ_PATH] = (digest_reference.REQ_HEAD + "\n" + req_body).encode()
    return inputs


def reviewed_manifest(identifier):
    tail, _, _, status, exit_code, *_ = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", "REQ-001", "--purpose", "verify", *tail, "--format", "json"],
                       "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/context.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    (_, _, _, status, _, complete, count, digest, code, source, summary) = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "context", "status": status, "purpose": "verify",
        "workspace": {"id": "root", "path": "."},
        "roots": ["REQ-001"],
        "contextDigest": digest,
        "revision": None,
        "resolution": {"complete": complete, "documentCount": count, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [],
        "constraintLedger": {"statements": []},
        "coverage": json.loads(json.dumps(EMPTY_COVERAGE)),
        "durationMs": 0,
        "diagnostics": [{"code": code, "severity": "error", "resultStatus": status,
                         "summary": summary, "source": source}],
    }


def check_presentation_size(identifier, inputs):
    """The configured limit must actually be crossed by the fixture's own input,
    so the expectation does not depend on how generously bytes are counted."""
    _, extra_config, *_ = CASES[identifier]
    if identifier == "SINGLE-048-01":
        documents = [name for name in inputs if name.startswith(".spec/") and name.endswith(".md")]
        if len(documents) <= 1:
            raise ValueError("document-count case needs more documents than the configured limit")
    if identifier == "SINGLE-048-02":
        presented = len(inputs[digest_reference.REQ_PATH]) + len(inputs[digest_reference.TECH_PATH])
        if presented <= 4096:
            raise ValueError("byte-limit case does not exceed the configured maxBytes")
    if identifier in {"SINGLE-046", "SINGLE-047"} and extra_config:
        raise ValueError("stale and projection cases must keep the golden configuration")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/context.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("invocation or complete result differs from reviewed expectation")
            if result["documents"] or result["constraintLedger"]["statements"]:
                raise ValueError("a non-success Context must not deliver Bundle material")
            if (result["contextDigest"] is None) is result["resolution"]["complete"]:
                raise ValueError("Digest presence must follow complete resolution")
            inputs = reviewed_inputs(identifier)
            check_presentation_size(identifier, inputs)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("input differs from the reviewed corpus")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-context-limit-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
