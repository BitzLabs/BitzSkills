"""Validate reviewed internal-Parser evidence, never run a Core parser.

Gate B adapters must compare their actual full IR with these files. This narrow
reader only cross-checks the fixed escape/reason corpus during Step 0B.
"""
import json
from pathlib import Path
from . import digest_crosscheck


def files(fixture, manifest):
    """Validate the references before following them (including symlink escapes)."""
    seen_paths, seen_results = set(), set()
    for check in manifest.get("parserChecks", []):
        relative, expected = check["path"], check["resultFile"]
        if relative in seen_paths or expected in seen_results:
            raise ValueError("duplicate Parser input or expectation")
        seen_paths.add(relative)
        seen_results.add(expected)
        for value in (relative, expected):
            parts = value.split("/")
            if value.startswith("/") or any(part in ("", ".", "..") for part in parts) or "\x00" in value:
                raise ValueError("unsafe Parser reference")
        path = fixture / expected
        if (not expected.startswith("expected/") or path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to((fixture / "expected").resolve())):
            raise ValueError("missing or unsafe Parser expectation")
        yield relative, path


def validate_checks(fixture, manifest, repository):
    for relative, path in files(fixture, manifest):
        source = repository / relative
        if (source.is_symlink() or not source.is_file()
                or not source.resolve().is_relative_to(repository.resolve())):
            raise ValueError("missing or unsafe Parser input")
        text = source.read_bytes().decode("utf-8")
        fm, _ = digest_crosscheck.split_document(text)
        actual = []
        for number, raw in enumerate(text.splitlines(), 1):
            # These approved positive corpora contain only ordinary list statements.
            if not raw.startswith("- ["):
                continue
            parsed = digest_crosscheck.read_statements(raw)
            if len(parsed) != 1:
                raise ValueError("expected exactly one reviewed statement on a source line")
            semantic = parsed[0]
            if semantic["activation"]["text"] is None:
                del semantic["activation"]["text"]
            actual.append({"schemaVersion": "1.0", **semantic, "documentId": fm["id"],
                           "localId": semantic["id"].split(":")[1],
                           "source": {"path": relative, "line": number, "column": raw.index("[") + 1},
                           "unknownExtensions": [], "untrustedText": True, "raw": raw})
        expected = json.loads(path.read_text())
        if expected != actual:
            raise ValueError("complete Parser IR differs from reviewed source/semantic evidence")
