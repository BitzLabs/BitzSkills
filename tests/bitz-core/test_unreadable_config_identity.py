"""設定を読めずに止まった結果が、ワークスペースの同一性を`null`にすることの単体試験（確認事項 C59）。

欠陥: 設定ファイルが64 KiBの上限を超えたとき（`SPEC-INPUT-LIMIT-001`）と、読み取れないとき（`SPEC-INPUT-READ-001`）は、設定の読み込みが既定値`root`を
ワークスペースのIDとして補い、単独結果の`workspace.id`、全体結果の`multiWorkspace.id`、診断の`source.workspaceId`に`root`を返していた。
構文の誤りや文字コードの不正で読めないときは`null`を返しており、設定を読めない原因によって扱いが分かれていた。

規範:
- 結果・診断・終了コード §2・§5、複合ワークスペース仕様 §9: 設定を読めないこと（上限の超過、読取りの失敗、文字コードの不正）、構文、型、ID不正により
  同一性を構成する前に止まった結果は、`workspace.id`・`multiWorkspace.id`・`source.workspaceId`を`null`とする（ユーザーの決定 2026-10-26）。

この試験の対象:
1. 単一ワークスペースの上限の超過と読取りの失敗で、単独操作の`workspace.id`と`source.workspaceId`が`null`（`workspace.id`を明示していても）。
2. 複合ワークスペースのルートの上限の超過で、全体操作の`multiWorkspace.id`と`source.workspaceId`が`null`。
3. メンバーの設定の上限の超過と読取りの失敗で、メンバーの設定の診断の`source.workspaceId`が`null`（全体操作と、メンバーで実行する単独操作）。
   ルートの設定の読取りの失敗でも、全体操作の`multiWorkspace.id`が`null`。
4. 対照: 上限ちょうどの設定は読めて、明示したIDを使う。構文の誤りは今までどおり`null`。
5. 結果は`result.schema.json`に適合する。
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
from bitz import config as config_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
REQ = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: approved\n---\n\n# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _padded(text: str, size: int) -> str:
    """``text``の後ろにYAMLのコメントを足し、UTF-8で``size``バイトちょうどにする。"""

    filler = size - len(text.encode("utf-8")) - 3
    return text + "# " + "x" * filler + "\n"


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


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def commit(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def run_op(self, module, name: str, cwd: Path, *argv: str):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(cwd), dict(os.environ))
        self.results.append(result)
        return result, code

    def single_runs(self, cwd: Path):
        return (
            ("check", self.run_op(check_mod, "check", cwd, "--full")),
            ("verify", self.run_op(verify_mod, "verify", cwd)),
            ("context", self.run_op(context_mod, "context", cwd, "REQ-001")),
            ("doctor", self.run_op(doctor_mod, "doctor", cwd)),
        )

    def assert_null_identity(self, result, name, code: str):
        self.assertEqual(result["workspace"]["id"], None, name)
        sources = [d["source"] for d in result["diagnostics"] if d["code"] == code]
        self.assertEqual([src["workspaceId"] for src in sources], [None], (name, result["diagnostics"]))


class SingleWorkspaceLimitTests(_Base):
    def test_oversized_config_has_null_identity(self):
        _write(self.root, ".spec/bitz.yaml", _padded(CONFIG, config_mod.CONFIG_LIMIT_BYTES + 1))
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        self.commit()
        for name, (result, _code) in self.single_runs(self.root):
            self.assert_null_identity(result, name, "SPEC-INPUT-LIMIT-001")

    def test_config_at_the_limit_is_read_with_its_explicit_id(self):
        _write(self.root, ".spec/bitz.yaml", _padded(CONFIG, config_mod.CONFIG_LIMIT_BYTES))
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        self.commit()
        result, code = self.run_op(check_mod, "check", self.root, "--full")
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."}, result["diagnostics"])
        self.assertNotIn("SPEC-INPUT-LIMIT-001", [d["code"] for d in result["diagnostics"]])

    def test_syntax_error_keeps_null_identity(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + "  bad: [unterminated\n")
        self.commit()
        result, _ = self.run_op(check_mod, "check", self.root, "--full")
        self.assertEqual(result["workspace"]["id"], None)


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "rootでは読取り権限を外せない")
class SingleWorkspaceReadErrorTests(_Base):
    def test_unreadable_config_has_null_identity(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        self.commit()
        config_path = self.root / ".spec" / "bitz.yaml"
        config_path.chmod(0)
        self.addCleanup(config_path.chmod, 0o644)
        for name, (result, _code) in self.single_runs(self.root):
            self.assert_null_identity(result, name, "SPEC-INPUT-READ-001")


class MultiWorkspaceLimitTests(_Base):
    ROOT = CONFIG + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
    WEB = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: web\n'

    def test_oversized_root_config_has_null_multi_workspace_id(self):
        _write(self.root, ".spec/bitz.yaml", _padded(self.ROOT, config_mod.CONFIG_LIMIT_BYTES + 1))
        _write(self.root, "apps/web/.spec/bitz.yaml", self.WEB)
        self.commit()
        for name in ("check", "verify", "doctor"):
            module = {"check": check_mod, "verify": verify_mod, "doctor": doctor_mod}[name]
            result, _ = self.run_op(module, name, self.root, "--all-workspaces")
            self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."}, name)
            sources = [d["source"] for d in result["diagnostics"] if d["code"] == "SPEC-INPUT-LIMIT-001"]
            self.assertEqual([src["workspaceId"] for src in sources], [None], (name, result["diagnostics"]))

    def test_oversized_member_config_in_single_operations_of_the_member(self):
        _write(self.root, ".spec/bitz.yaml", self.ROOT)
        _write(self.root, "apps/web/.spec/bitz.yaml", _padded(self.WEB, config_mod.CONFIG_LIMIT_BYTES + 1))
        _write(self.root, "apps/web/.spec/requirements/REQ-001.md", REQ)
        self.commit()
        for name, (result, _code) in self.single_runs(self.root / "apps" / "web"):
            self.assertEqual(result["workspace"], {"id": None, "path": "apps/web"}, name)
            sources = [d["source"] for d in result["diagnostics"] if d["code"] == "SPEC-INPUT-LIMIT-001"]
            self.assertEqual([src["workspaceId"] for src in sources], [None], (name, result["diagnostics"]))

    def test_oversized_member_config_has_null_source_workspace_id(self):
        _write(self.root, ".spec/bitz.yaml", self.ROOT)
        _write(self.root, "apps/web/.spec/bitz.yaml", _padded(self.WEB, config_mod.CONFIG_LIMIT_BYTES + 1))
        self.commit()
        result, _ = self.run_op(check_mod, "check", self.root, "--all-workspaces")
        sources = [d["source"] for d in result["diagnostics"] if d["code"] == "SPEC-INPUT-LIMIT-001"]
        self.assertEqual([src["workspaceId"] for src in sources], [None], result["diagnostics"])


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "rootでは読取り権限を外せない")
class MultiWorkspaceReadErrorTests(_Base):
    ROOT = MultiWorkspaceLimitTests.ROOT
    WEB = MultiWorkspaceLimitTests.WEB

    def unreadable(self, rel: str) -> None:
        path = self.root / rel
        path.chmod(0)
        self.addCleanup(path.chmod, 0o644)

    def test_unreadable_root_config_has_null_multi_workspace_id(self):
        _write(self.root, ".spec/bitz.yaml", self.ROOT)
        _write(self.root, "apps/web/.spec/bitz.yaml", self.WEB)
        self.commit()
        self.unreadable(".spec/bitz.yaml")
        result, _ = self.run_op(check_mod, "check", self.root, "--all-workspaces")
        self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."})
        sources = [d["source"] for d in result["diagnostics"] if d["code"] == "SPEC-INPUT-READ-001"]
        self.assertEqual([src["workspaceId"] for src in sources], [None], result["diagnostics"])

    def test_unreadable_member_config_has_null_source_workspace_id(self):
        _write(self.root, ".spec/bitz.yaml", self.ROOT)
        _write(self.root, "apps/web/.spec/bitz.yaml", self.WEB)
        self.commit()
        self.unreadable("apps/web/.spec/bitz.yaml")
        result, _ = self.run_op(check_mod, "check", self.root, "--all-workspaces")
        self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})
        sources = [d["source"] for d in result["diagnostics"] if d["code"] == "SPEC-INPUT-READ-001"]
        self.assertEqual([src["workspaceId"] for src in sources], [None], result["diagnostics"])


if __name__ == "__main__":
    unittest.main()
