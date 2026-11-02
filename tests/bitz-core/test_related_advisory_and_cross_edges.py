"""`related`の参照切れの警告と、`related`の横断のエッジの単体試験（確認事項 C78・C79）。

欠陥（C78）: `check`は`related`の参照切れを`SPEC-RELATION-ADVISORY-MISSING-001`（`warning`）で返すが、`context`と`verify`は関係の診断から
エラーだけを残し、この警告を捨てていた。診断レジストリの`RELATION-TARGET-MISSING-RELATED`の対象の操作は`context`、`check`、`verify`である。

規範:
- 関係・トレースモデル §3: `related`は閉包を増やさず、参照切れは`SPEC-RELATION-ADVISORY-MISSING-001`（`warning`）とする。
- `context` §10・`verify` §9: この警告はコンテキストまたは検証対象を失敗させず、通過状態の結果と、関係・状態・依存の診断による非成功の結果に加える。
- 複合ワークスペース仕様 §6（C79）: `related`は閉包を増やさないので、解決できても横断のエッジ（`resolution.crossWorkspaceEdges`）として収録しない。

この試験の対象:
1. 単一ワークスペースの`context`（目的`interpret`と`implement`）と`verify`が、成功の結果に警告を返し、状態は`passed_with_warnings`、終了コードは0。
2. 強い関係の参照切れもある失敗の結果にも、同じ警告を並べる。`verify`は、MUSTとSHOULDの未テスト、テスト割当ての不足、
   状態による展開の失敗、テストの失敗のどの経路でも、検証対象に警告を1件だけ加える。ハッシュ値の不一致で止まる`context`の結果には加えない。
3. 複合ワークスペースの`context`と`verify`も同じ警告を返す。
4. 解決できる横断の`related`は`crossWorkspaceEdges`に入らず、横断の`requires`は入る。
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

from bitz import context as context_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n'
ADVISORY = "SPEC-RELATION-ADVISORY-MISSING-001"
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"context": context_mod, "verify": verify_mod}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str, relations: str = "") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n{relations}"
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

    def run_op(self, op: str, *argv: str, cwd: Path | None = None):
        parsed = parse_argv([op, *argv, "--format", "json"])
        result, code = _OPERATIONS[op].run(parsed, str(cwd or self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def codes(result) -> list[tuple[str, str | None]]:
        diags = list(result["diagnostics"])
        for target in result.get("targetResults", []):
            diags.extend(target["diagnostics"])
        return sorted((d["code"], d.get("evidence") if isinstance(d.get("evidence"), str) else None) for d in diags)


class SingleWorkspaceAdvisoryTests(_Base):
    def write(self, relations: str):
        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", relations))
        self.commit()

    def test_success_results_return_the_related_warning(self):
        self.write("relations:\n  related: [REQ-099]\n")
        for op, argv in (
            ("context", ("REQ-001", "--purpose", "interpret")),
            ("context", ("REQ-001", "--purpose", "implement")),
            ("verify", ("REQ-001",)),
        ):
            with self.subTest(op=op, argv=argv):
                result, code = self.run_op(op, *argv)
                self.assertEqual((result["status"], code), ("passed_with_warnings", 0), result)
                self.assertIn((ADVISORY, "REQ-099"), self.codes(result))
                diags = list(result["diagnostics"]) + [d for t in result.get("targetResults", []) for d in t["diagnostics"]]
                self.assertEqual({d["severity"] for d in diags}, {"warning"})

    def test_verify_target_carries_the_warning(self):
        self.write("relations:\n  related: [REQ-099]\n")
        result, _code = self.run_op("verify", "REQ-001")
        (target,) = result["targetResults"]
        self.assertEqual(target["status"], "passed_with_warnings")
        self.assertEqual([d["code"] for d in target["diagnostics"]], [ADVISORY])
        self.assertEqual(target["bindingRefs"], ["root::t"])

    def test_failure_results_also_return_the_related_warning(self):
        self.write("relations:\n  related: [REQ-099]\n  requires: [REQ-098]\n")
        for op, argv in (("context", ("REQ-001", "--purpose", "interpret")), ("verify", ("REQ-001",))):
            with self.subTest(op=op):
                result, code = self.run_op(op, *argv)
                self.assertEqual((result["status"], code), ("failed", 1), result)
                self.assertEqual(self.codes(result), [(ADVISORY, "REQ-099"), ("SPEC-RELATION-MISSING-001", "REQ-098")])


class VerifyPathTests(_Base):
    """`verify`の検証対象のどの経路の結果にも、`related`の参照切れの警告を1件だけ加える（`verify` §9）。"""

    RELATED = "relations:\n  related: [REQ-099]\n"

    def write(self, req: str, config: str = VERIFY):
        _write(self.root, ".spec/bitz.yaml", CONFIG + config)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, ".spec/requirements/REQ-001.md", req)
        self.commit()

    def target(self):
        result, code = self.run_op("verify", "REQ-001")
        (target,) = result["targetResults"]
        return result, code, target

    def assert_one_advisory(self, target):
        self.assertEqual([d["evidence"] for d in target["diagnostics"] if d["code"] == ADVISORY], ["REQ-099"])

    def test_must_untested(self):
        req = _req("REQ-001", self.RELATED).replace("tests:\n  - path: tests/t.py\n    covers: [REQ-001:AC-01]\n    command: t\n", "")
        self.write(req)
        result, code, target = self.target()
        self.assertEqual((result["status"], code, target["status"]), ("blocked", 2, "blocked"), result)
        self.assertEqual(sorted(d["code"] for d in target["diagnostics"]), ["CTX-COVERAGE-TEST-001", ADVISORY])
        self.assert_one_advisory(target)

    def test_should_untested(self):
        req = _req("REQ-001", self.RELATED).replace(
            "## Verification", "- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [SHOULD] [CONSTRAINT] REQ-001:AC-02を守る。\n\n## Verification"
        )
        self.write(req)
        result, code, target = self.target()
        self.assertEqual((result["status"], code, target["status"]), ("passed_with_warnings", 0, "passed_with_warnings"), result)
        self.assertEqual(sorted(d["code"] for d in target["diagnostics"]), ["CTX-COVERAGE-TEST-001", ADVISORY])
        self.assert_one_advisory(target)

    def test_binding_missing(self):
        self.write(_req("REQ-001", self.RELATED).replace("command: t", "command: absent"))
        result, code, target = self.target()
        self.assertEqual((result["status"], code, target["status"]), ("blocked", 2, "blocked"), result)
        self.assertEqual(sorted(d["code"] for d in target["diagnostics"]), [ADVISORY, "SPEC-VERIFY-BLOCKED-001"])
        self.assertEqual(target["bindingRefs"], [])
        self.assert_one_advisory(target)

    def test_expansion_failure_by_state(self):
        self.write(_req("REQ-001", self.RELATED).replace("status: approved", "status: draft"))
        result, code, target = self.target()
        self.assertEqual((result["status"], code, target["status"]), ("blocked", 2, "blocked"), result)
        self.assertEqual(sorted(d["code"] for d in target["diagnostics"]), ["CTX-STATE-001", ADVISORY])
        self.assert_one_advisory(target)

    def test_failing_test_command(self):
        self.write(_req("REQ-001", self.RELATED), VERIFY.replace("/bin/true", "/bin/false"))
        result, code, target = self.target()
        self.assertEqual((result["status"], code, target["status"]), ("failed", 1, "failed"), result)
        self.assertEqual([d["code"] for d in target["diagnostics"]], [ADVISORY])
        self.assert_one_advisory(target)


class ContextStopPathTests(_Base):
    """ハッシュ値の不一致で止まる`context`の結果は、その診断だけを返し、`related`の警告を加えない（`context` §10）。"""

    def test_stale_result_has_only_the_stale_diagnostic(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", "relations:\n  related: [REQ-099]\n"))
        self.commit()
        result, code = self.run_op("context", "REQ-001", "--purpose", "interpret", "--expect-digest", "sha256:" + "0" * 64)
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["CTX-STALE-001"])


class MultiWorkspaceRelatedTests(_Base):
    def write(self, web_relations: str):
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n" + VERIFY,
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n" + VERIFY)
        for base in ("", "apps/web/"):
            _write(self.root, f"{base}tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/requirements/REQ-101.md", _req("REQ-101", web_relations))
        self.commit()

    def test_multi_workspace_context_and_verify_return_the_related_warning(self):
        self.write("relations:\n  related: [platform::REQ-099]\n")
        for op, argv in (("context", ("web::REQ-101", "--purpose", "interpret")), ("verify", ("web::REQ-101",))):
            with self.subTest(op=op):
                result, code = self.run_op(op, "--workspace", "web", *argv)
                self.assertEqual((result["status"], code), ("passed_with_warnings", 0), result)
                self.assertIn((ADVISORY, "platform::REQ-099"), self.codes(result))

    def test_resolvable_cross_workspace_related_is_not_a_cross_edge(self):
        self.write("relations:\n  related: [platform::REQ-001]\n")
        result, code = self.run_op("context", "--workspace", "web", "web::REQ-101", "--purpose", "interpret")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(result["resolution"]["crossWorkspaceEdges"], [])

    def test_resolvable_cross_workspace_requires_is_a_cross_edge(self):
        self.write("relations:\n  requires: [platform::REQ-001]\n  related: [platform::REQ-001]\n")
        result, code = self.run_op("context", "--workspace", "web", "web::REQ-101", "--purpose", "interpret")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(
            result["resolution"]["crossWorkspaceEdges"],
            [{"relation": "requires", "source": "web::REQ-101", "target": "platform::REQ-001"}],
        )


if __name__ == "__main__":
    unittest.main()
