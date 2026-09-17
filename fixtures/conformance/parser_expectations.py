"""review済みの内部Parserの証拠を検証する。CoreのParserは実行しない。

Gate Bのadapterは、実際の完全なIRをこれらのfileと比べなければならない。この限定した
読取り処理は、Step 0Bの間、固定したescape・reasonのcorpusを照合するだけである。
"""
import json
from pathlib import Path
from . import digest_crosscheck


def files(fixture, manifest):
    """参照をたどる前に検証する（symlinkによる脱出を含む）。"""
    seen_paths, seen_results = set(), set()
    for check in manifest.get("parserChecks", []):
        relative, expected = check["path"], check["resultFile"]
        if relative in seen_paths or expected in seen_results:
            raise ValueError("Parserの入力または期待値が重複しています")
        seen_paths.add(relative)
        seen_results.add(expected)
        for value in (relative, expected):
            parts = value.split("/")
            if value.startswith("/") or any(part in ("", ".", "..") for part in parts) or "\x00" in value:
                raise ValueError("安全でないParserの参照です")
        path = fixture / expected
        if (not expected.startswith("expected/") or path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to((fixture / "expected").resolve())):
            raise ValueError("Parserの期待値が存在しないか安全ではありません")
        yield relative, path


def validate_checks(fixture, manifest, repository):
    for relative, path in files(fixture, manifest):
        source = repository / relative
        if (source.is_symlink() or not source.is_file()
                or not source.resolve().is_relative_to(repository.resolve())):
            raise ValueError("Parserの入力が存在しないか安全ではありません")
        text = source.read_bytes().decode("utf-8")
        fm, _ = digest_crosscheck.split_document(text)
        actual = []
        for number, raw in enumerate(text.splitlines(), 1):
            # 承認済みのこれらの正例corpusは、通常のlistの規範文だけを持つ。
            if not raw.startswith("- ["):
                continue
            parsed = digest_crosscheck.read_statements(raw)
            if len(parsed) != 1:
                raise ValueError("sourceの1行にはreview済みの規範文がちょうど1件必要です")
            semantic = parsed[0]
            if semantic["activation"]["text"] is None:
                del semantic["activation"]["text"]
            actual.append({"schemaVersion": "1.0", **semantic, "documentId": fm["id"],
                           "localId": semantic["id"].split(":")[1],
                           "source": {"path": relative, "line": number, "column": raw.index("[") + 1},
                           "unknownExtensions": [dict(entry) for entry in semantic["extensions"]], "untrustedText": True, "raw": raw})
        expected = json.loads(path.read_text())
        if expected != actual:
            raise ValueError("完全なParser IRがreview済みのsource・意味の証拠と異なります")
