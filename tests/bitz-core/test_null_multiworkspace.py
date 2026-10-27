"""値が空の`multiWorkspace:`の宣言を、メンバー0件の設定不適合とし、メンバーの宣言も拒否することの単体試験（確認事項 C58・C63）。

欠陥:
- C58: ルートの設定が`multiWorkspace:`（キーだけで値が空）を持ち`workspace.id`を明示すると、カタログの形の検査が値の空を「不備なし・メンバー0件」とみなし、
  メンバー0件の複合ワークスペースとして成功していた。
- C63: メンバーの設定が`multiWorkspace:`（値が空）だけを持つと、「メンバーは`multiWorkspace`を宣言できない」の診断にならず通っていた。

規範:
- 複合ワークスペース仕様 §2.1: 設定が`multiWorkspace`を宣言するかは、キー`multiWorkspace`の有無で判定する。
- 同 §2: メンバーが0件の`multiWorkspace`は設定不適合。メンバーは`multiWorkspace`を宣言できない。
- 診断レジストリ`MULTI-CONFIG`（`SPEC-MULTI-CONFIG-001`、900）、`MULTI-MEMBER`（`SPEC-MULTI-MEMBER-001`、910）。
- ユーザーの決定（2026-10-26）: 値が空の宣言は`members: []`と同じ「設定キーmultiWorkspace.membersは1件以上指定してください」で止める。

この試験の対象:
1. ルートの空の宣言は、全体操作と単独操作（`check`、`verify`、`doctor`、`context`）のすべてで`SPEC-MULTI-CONFIG-001`の1件だけで止め、`members: []`と同じ結果になる。`doctor`の`catalog`は`failed`。
2. 未登録のメンバーの設定があっても、設定不適合（900）が未登録（960）より先に1件だけ返る。
3. ルートが`workspace.id`も省略していれば、ルートのIDの省略（C42）で止まる（先に判定する）。
4. メンバーの空の宣言は`SPEC-MULTI-MEMBER-001`（メンバーは宣言できない）。
5. 対照: キー`multiWorkspace`のない設定は単一ワークスペースとして動く。
6. 基準版（`--base`）のルートの設定の値が空の宣言も、現在版と同じく`members: []`と同じに扱う（基準版の未登録の比較、§4.1の写像に当たらないこと）。
7. 入れ子の複合ワークスペース（外側の除外した範囲の中）の値が空の宣言も、メンバー0件の設定不適合。
8. 結果は`result.schema.json`に適合する。
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
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
REQ = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: approved\ntests:\n  - path: tests/t.py\n    covers: [REQ-001:AC-01]\n    command: t\n---\n\n"
    "# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)
MEMBERS_REQUIRED = "設定キーmultiWorkspace.membersは1件以上指定してください"
MEMBER_NESTED = "メンバーは設定キーmultiWorkspaceを宣言できません"
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


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
    root_yaml = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + VERIFY
    extra: dict[str, str] = {}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _write(self.root, ".spec/bitz.yaml", self.root_yaml)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        for rel, content in self.extra.items():
            _write(self.root, rel, content)
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def run_op(self, module, name: str, cwd: Path, *argv: str):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(cwd), dict(os.environ))
        self.results.append(result)
        return result, code

    def all_runs(self, cwd: Path):
        return (
            ("check-all", self.run_op(check_mod, "check", cwd, "--all-workspaces")),
            ("verify-all", self.run_op(verify_mod, "verify", cwd, "--all-workspaces")),
            ("doctor-all", self.run_op(doctor_mod, "doctor", cwd, "--all-workspaces")),
            ("check", self.run_op(check_mod, "check", cwd, "--full")),
            ("verify", self.run_op(verify_mod, "verify", cwd)),
            ("doctor", self.run_op(doctor_mod, "doctor", cwd)),
            ("context", self.run_op(context_mod, "context", cwd, "REQ-001", "--purpose", "implement")),
        )

    @staticmethod
    def diags(result):
        return [(d["code"], d["summary"], d["source"].get("key")) for d in result["diagnostics"]]


class RootNullDeclarationTests(_Base):
    def test_every_operation_stops_with_members_required(self):
        for name, (result, code) in self.all_runs(self.root):
            self.assertEqual((result["status"], code), ("failed", 1), (name, result["diagnostics"]))
            self.assertEqual(
                self.diags(result), [("SPEC-MULTI-CONFIG-001", MEMBERS_REQUIRED, "multiWorkspace.members")], name
            )
            self.assertEqual(result["diagnostics"][0]["source"]["workspaceId"], "platform", name)
            if name.startswith("doctor"):
                self.assertIn({"name": "catalog", "status": "failed"}, result["checks"], name)

    def test_result_is_the_same_as_empty_members(self):
        null_results = [(n, r["status"], c, self.diags(r)) for n, (r, c) in self.all_runs(self.root)]
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members: []\n" + VERIFY)
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "empty members")
        empty_results = [(n, r["status"], c, self.diags(r)) for n, (r, c) in self.all_runs(self.root)]
        self.assertEqual(null_results, empty_results)


class RootNullWithUnregisteredMemberTests(_Base):
    extra = {"apps/web/.spec/bitz.yaml": CONFIG + "workspace:\n  id: web\n"}

    def test_config_defect_precedes_the_unregistered_config(self):
        for cwd in (self.root, self.root / "apps" / "web"):
            for name, (result, code) in self.all_runs(cwd):
                self.assertEqual((result["status"], code), ("failed", 1), (str(cwd), name, result["diagnostics"]))
                self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-CONFIG-001"], (str(cwd), name))


class RootNullWithoutIdTests(_Base):
    root_yaml = CONFIG + "multiWorkspace:\n" + VERIFY

    def test_root_id_omission_is_checked_first(self):
        result, code = self.run_op(check_mod, "check", self.root, "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(
            self.diags(result), [("SPEC-MULTI-CONFIG-001", "ルートワークスペースの設定キーworkspace.idがありません", "workspace.id")]
        )
        self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."})


class MemberNullDeclarationTests(_Base):
    root_yaml = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n" + VERIFY
    extra = {"apps/web/.spec/bitz.yaml": CONFIG + "workspace:\n  id: web\nmultiWorkspace:\n"}

    def test_member_null_declaration_is_rejected(self):
        for name, (result, code) in self.all_runs(self.root):
            self.assertEqual((result["status"], code), ("failed", 1), (name, result["diagnostics"]))
            self.assertEqual(
                self.diags(result), [("SPEC-MULTI-MEMBER-001", MEMBER_NESTED, "multiWorkspace.members")], name
            )


class NoDeclarationControlTests(_Base):
    root_yaml = CONFIG + "workspace:\n  id: platform\n" + VERIFY

    def test_single_workspace_without_the_key_passes(self):
        result, code = self.run_op(check_mod, "check", self.root, "--full")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
        self.assertNotIn("multiWorkspace", result)


class BaseNullDeclarationTests(unittest.TestCase):
    """基準版のルートの設定が値の空の宣言を持つとき、`members: []`の基準版と同じ結果になる（基準版の比較、§2.1・§4.1・§8）。"""

    def setUp(self):
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def build(self, base_root_yaml: str, base_files: dict[str, str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        _write(root, ".spec/bitz.yaml", base_root_yaml)
        _write(root, "tests/t.py", "def test_t():\n    assert True\n")
        for rel, content in base_files.items():
            _write(root, rel, content)
        _git(root, "init", "-q", "--initial-branch=main")
        _git(root, "add", ".")
        _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
        _write(
            root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n" + VERIFY,
        )
        _write(root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        _git(root, "add", ".")
        _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "current")
        return root

    def check_base(self, root: Path):
        parsed = parse_argv(["check", "--all-workspaces", "--base", "HEAD~1", "--format", "json"])
        result, code = check_mod.run(parsed, str(root), dict(os.environ))
        self.results.append(result)
        return result["status"], code, [(d["code"], d["source"].get("path")) for d in result["diagnostics"]]

    def compare(self, base_head: str, base_files: dict[str, str]):
        null_root = self.build(base_head + "multiWorkspace:\n" + VERIFY, base_files)
        empty_root = self.build(base_head + "multiWorkspace:\n  members: []\n" + VERIFY, base_files)
        return self.check_base(null_root), self.check_base(empty_root)

    def test_unregistered_config_in_the_base_is_compared(self):
        null_result, empty_result = self.compare(
            CONFIG + "workspace:\n  id: platform\n",
            {".spec/requirements/REQ-001.md": REQ, "apps/web/.spec/bitz.yaml": CONFIG + "workspace:\n  id: web\n"},
        )
        self.assertEqual(null_result, empty_result)
        self.assertEqual(null_result[:2], ("blocked", 2))
        self.assertIn(("SPEC-MULTI-UNREGISTERED-001", "apps/web/.spec/bitz.yaml"), null_result[2])

    def test_base_without_root_id_is_not_mapped_as_a_single_workspace(self):
        null_result, empty_result = self.compare(CONFIG, {".spec/requirements/REQ-001.md": REQ})
        self.assertEqual(null_result, empty_result)
        self.assertEqual(null_result[:2], ("failed", 1))
        self.assertIn("SPEC-STATE-TRANSITION-001", [code for code, _path in null_result[2]])


class NestedNullDeclarationTests(_Base):
    """外側の除外した範囲の中の入れ子の複合ワークスペースの値が空の宣言（複合ワークスペース仕様 §2.1）。"""

    root_yaml = (
        CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
        + "  exclude:\n    - vendor\n" + VERIFY
    )
    extra = {
        "apps/web/.spec/bitz.yaml": CONFIG + "workspace:\n  id: web\n",
        "vendor/.spec/bitz.yaml": CONFIG + "workspace:\n  id: vend\nmultiWorkspace:\n",
    }

    def test_nested_null_declaration_stops_with_members_required(self):
        result, code = self.run_op(check_mod, "check", self.root / "vendor", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
        self.assertEqual(self.diags(result), [("SPEC-MULTI-CONFIG-001", MEMBERS_REQUIRED, "multiWorkspace.members")])
        self.assertEqual(result["diagnostics"][0]["source"]["workspaceId"], "vend")


if __name__ == "__main__":
    unittest.main()
