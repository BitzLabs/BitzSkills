"""全体操作が各ワークスペースの設定の警告を返すことの単体試験（確認事項 C22）。

欠陥: `doctor --all-workspaces`は各ワークスペースの設定の警告（未知のキーなど）を`workspaces[].diagnostics`へ返すが、
`check --all-workspaces`と`verify --all-workspaces`は1件も返さず、状態も`passed`になっていた。単独の操作は返していた。

規範:
- 診断レジストリ: `INPUT-BOM-CONFIG`、`CONFIG-SCHEMA-MINOR-NEWER`、`CONFIG-KEY-PROFILES`、`CONFIG-KEY-UNKNOWN`の返しうる操作は`all`で、継続単位は`continue`。
- 結果・診断・終了コード §2: 全体事前検査を通過した各ワークスペースの設定の警告は、`doctor`、`check`、`verify`のどの全体操作でも、
  そのワークスペースの`diagnostics`へ置く。最上位の`diagnostics`へ複製しない。

この試験の対象:
1. 3つの全体操作で、設定の警告（未知のキー、`profiles`、BOM）が同じ形で、所有するワークスペースの`diagnostics`に置かれ、最上位には置かれない。
2. 警告だけのワークスペースと全体の状態は`passed_with_warnings`、終了コードは0。警告のないワークスペースは`passed`のまま。
3. 結果は`result.schema.json`に適合する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

BASE = 'language: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"doctor": doctor_mod, "check": check_mod, "verify": verify_mod}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str, *, bom: bool = False) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes((b"\xef\xbb\xbf" if bom else b"") + content.encode("utf-8"))


def _req(doc_id: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n"
        f"tests:\n  - path: tests/t.py\n    covers: [{doc_id}:AC-01]\n    command: t\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {doc_id}:AC-01を守る。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _validate_against_schema(results: list[dict]) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise unittest.SkipTest("uvがないためスキーマ適合を確認できません")
    script = (
        "import json, sys\n"
        "from jsonschema import Draft202012Validator\n"
        "schema = json.load(open(sys.argv[1], encoding='utf-8'))\n"
        "validator = Draft202012Validator(schema)\n"
        "for index, result in enumerate(json.load(sys.stdin)):\n"
        "    errors = sorted(validator.iter_errors(result), key=lambda e: list(e.path))\n"
        "    if errors:\n"
        "        print(index, errors[0].message, list(errors[0].path))\n"
        "        sys.exit(1)\n"
    )
    proc = subprocess.run(
        [uv, "run", "--no-project", "--with", "jsonschema==4.23.0", "python", "-c", script, str(RESULT_SCHEMA)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"スキーマに適合しません: {proc.stdout}{proc.stderr}")


class AllWorkspacesConfigWarningTests(unittest.TestCase):
    """ルート`platform`（未知のキー）、メンバー`web`（BOM、`profiles`）、メンバー`api`（警告なし）。

    `CONFIG-SCHEMA-MINOR-NEWER`はCoreが実装していないので、この試験では扱わない（確認事項C93）。
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.results: list[dict] = []
        _write(
            self.root, ".spec/bitz.yaml",
            'schemaVersion: "1.0"\n' + BASE + "workspace:\n  id: platform\nunknownRoot: 1\nmultiWorkspace:\n  members:\n"
            "    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n" + VERIFY,
        )
        _write(
            self.root, "apps/web/.spec/bitz.yaml",
            'schemaVersion: "1.0"\n' + BASE + "workspace:\n  id: web\nprofiles: {}\n" + VERIFY, bom=True,
        )
        _write(self.root, "services/api/.spec/bitz.yaml", 'schemaVersion: "1.0"\n' + BASE + "workspace:\n  id: api\n" + VERIFY)
        for base, doc_id in (("", "REQ-001"), ("apps/web/", "REQ-002"), ("services/api/", "REQ-003")):
            _write(self.root, f"{base}tests/t.py", "def test_t():\n    assert True\n")
            _write(self.root, f"{base}.spec/requirements/{doc_id}.md", _req(doc_id))
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def run_all(self, op: str):
        parsed = parse_argv([op, "--all-workspaces", "--format", "json"])
        result, code = _OPERATIONS[op].run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def config_warnings(diagnostics: list[dict]) -> list[tuple[str, str | None]]:
        return sorted(
            (d["code"], d["source"].get("key"))
            for d in diagnostics
            if d["code"] in ("SPEC-INPUT-BOM-001", "SPEC-CONFIG-UNKNOWN-001")
        )

    def test_every_all_workspaces_operation_places_config_warnings_in_the_owning_workspace(self):
        expected = {
            "platform": [("SPEC-CONFIG-UNKNOWN-001", "unknownRoot")],
            "web": [("SPEC-CONFIG-UNKNOWN-001", "profiles"), ("SPEC-INPUT-BOM-001", None)],
            "api": [],
        }
        shapes = {}
        for op in ("doctor", "check", "verify"):
            with self.subTest(op=op):
                result, code = self.run_all(op)
                self.assertEqual((result["status"], code), ("passed_with_warnings", 0), (op, result))
                self.assertEqual(self.config_warnings(result["diagnostics"]), [], op)
                by_id = {ws["id"]: ws for ws in result["workspaces"]}
                self.assertEqual({wid: self.config_warnings(ws["diagnostics"]) for wid, ws in by_id.items()}, expected, op)
                self.assertEqual(
                    (by_id["platform"]["status"], by_id["web"]["status"], by_id["api"]["status"]),
                    ("passed_with_warnings", "passed_with_warnings", "passed"),
                    op,
                )
                shapes[op] = {
                    wid: sorted(
                        json.dumps(d, ensure_ascii=False, sort_keys=True)
                        for d in ws["diagnostics"]
                        if d["code"] in ("SPEC-INPUT-BOM-001", "SPEC-CONFIG-UNKNOWN-001")
                    )
                    for wid, ws in by_id.items()
                }
        # 3つの操作で、警告の診断そのもの（コード、重大度、文言、発生元）が同じ。
        self.assertEqual(shapes["check"], shapes["doctor"])
        self.assertEqual(shapes["verify"], shapes["doctor"])


if __name__ == "__main__":
    unittest.main()
