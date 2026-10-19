"""複合ワークスペースの閉包の循環・別名の二重収録・evidence・`interpret`のADRの単体試験（確認事項 C18・C21・C19・D7）。

- C18: 複合ワークスペースの`context`は、閉包の外の強い関係の循環で失敗せず、閉包の文書が宣言する辺の循環を
  検出する（`01_context.md` §3、`04_関係・トレースモデル.md` §3・§4）。`verify <修飾ID>`と`verify`（引数なし、
  `--all-workspaces`）の複合ワークスペースの経路も、閉包の文書の循環を検出する（`03_verify.md`、同 §6.3）。
  単一ワークスペースと`check`の挙動は変えない。
- C21: 統合索引が作業ワークスペースの文書を修飾のないIDと`<作業ワークスペース>::<ID>`の2つのキーで登録しても、
  同じ文書を1つの実体として扱う（`04_関係・トレースモデル.md` §7「同一の文書が複数の経路から到達しても1回だけ収録し」）。
  二重に収録しない、関係の検査が漏れない、`supersedes`の後継を数え違えない、`addresses`の対象規範文を取りこぼさない。
- C19: 他のメンバーの文書の`CTX-RELATION-TYPE-001`の`evidence`は、宣言どおりの綴りで返す（`01_結果・診断・終了コード.md` §4）。
- D7: 目的`interpret`でも、他のメンバーの文書の`requires`が`accepted`でないADRを指すことを検出する
  （単一ワークスペースの`interpret`、`implement`、`verify`と同じ）。
- 出力が`docs/03.詳細設計/schemas/result.schema.json`に適合すること、`PYTHONHASHSEED`を変えても出力が同じこと。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
# `verify`が実行できるよう、どのワークスペースにも成功するコマンドを置く。
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _root_yaml(ws_id: str, members: list[tuple[str, str]]) -> str:
    text = CONFIG + f"workspace:\n  id: {ws_id}\nmultiWorkspace:\n  members:\n"
    for mid, mpath in members:
        text += f"    - id: {mid}\n      path: {mpath}\n"
    return text + VERIFY


def _single_yaml(ws_id: str) -> str:
    return CONFIG + f"workspace:\n  id: {ws_id}\n" + VERIFY


def _req(doc_id: str, *, requires: list[str] | None = None, covers_test: bool = False, status: str = "approved",
         supersedes: list[str] | None = None) -> str:
    relations = ""
    if requires:
        relations += f"  requires: [{', '.join(requires)}]\n"
    if supersedes:
        relations += f"  supersedes: [{', '.join(supersedes)}]\n"
    front = f"---\nid: {doc_id}\ntitle: REQ\nstatus: {status}\n"
    if relations:
        front += f"relations:\n{relations}"
    if covers_test:
        front += f"tests:\n  - path: tests/t.py\n    covers: [{doc_id}:AC-01]\n    command: t\n"
    return (
        f"{front}---\n\n# {doc_id} REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\nrelations:\n  refines: [{refines}]\n---\n\n"
        f"# {doc_id} TECH\n\n## Context\n\n本文。\n"
    )


def _task(doc_id: str, addresses: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: TASK\nstatus: open\nrelations:\n  addresses: [{addresses}]\n---\n\n"
        f"# {doc_id} TASK\n\n## Objective\n\n目的。\n"
    )


def _adr(doc_id: str, status: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: ADR\nstatus: {status}\n---\n\n# {doc_id} ADR\n\n"
        "## Context\n\n文脈。\n\n## Decision\n\n決定。\n\n## Consequences\n\n結果。\n"
    )


def _validate_against_schema(results: list[dict]) -> None:
    """結果が公開スキーマに適合することを確かめる。Coreの環境に`jsonschema`がないため、`uv`で一時的に用意して別プロセスで検証する。"""

    uv = shutil.which("uv")
    if uv is None:
        raise unittest.SkipTest("uvがないためスキーマ適合を確認できません")
    script = (
        "import json, sys\n"
        "from jsonschema import Draft202012Validator\n"
        "schema = json.load(open(sys.argv[1], encoding='utf-8'))\n"
        "validator = Draft202012Validator(schema)\n"
        "bad = []\n"
        "for item in json.load(sys.stdin):\n"
        "    errors = [e.message for e in validator.iter_errors(item)]\n"
        "    if errors:\n"
        "        bad.append(errors[:3])\n"
        "print(json.dumps(bad, ensure_ascii=False))\n"
    )
    proc = subprocess.run(
        [uv, "run", "--quiet", "--no-project", "--with", "jsonschema==4.23.0", "python", "-I", "-c", script, str(RESULT_SCHEMA)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise unittest.SkipTest(f"jsonschemaを用意できません: {proc.stderr.strip()[-200:]}")
    bad = json.loads(proc.stdout)
    if bad:
        raise AssertionError(f"result.schema.jsonに適合しません: {bad}")


def _without_durations(value):
    """実行時間（`durationMs`）は実行ごとに変わるため、比較から除く。"""

    if isinstance(value, dict):
        return {k: _without_durations(v) for k, v in value.items() if k != "durationMs"}
    if isinstance(value, list):
        return [_without_durations(v) for v in value]
    return value


class _Base(unittest.TestCase):
    """一時のGitリポジトリを作り、各操作を同一プロセスで実行して結果をスキーマ適合の検証へ集める。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.env = dict(os.environ)
        self.results: list[dict] = []
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        self.build()
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "base")

    def build(self) -> None:
        raise NotImplementedError

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def _run(self, module, name: str, argv: tuple[str, ...]):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(self.root), self.env)
        self.results.append(result)
        return result, code

    def context(self, *argv):
        return self._run(context_mod, "context", argv)

    def check(self, *argv):
        return self._run(check_mod, "check", argv)

    def verify(self, *argv):
        return self._run(verify_mod, "verify", argv)

    @staticmethod
    def codes(result: dict) -> list[str]:
        return [d["code"] for d in result["diagnostics"]]

    @staticmethod
    def doc_ids(result: dict) -> list[str]:
        return [d["id"] for d in result["documents"]]


def _member_tree(root: Path, member_id: str, member_path: str) -> None:
    _write(root, f"{member_path}/.spec/bitz.yaml", _single_yaml(member_id))


class ClosureCycleCompositeTests(_Base):
    """C18: 複合ワークスペースの`context`・`verify`は、閉包の文書が宣言する辺の循環だけを検査する。

    ```
    REQ-001  閉包の外から切り離された起点（循環なし）
    REQ-010 <-> REQ-011   起点から到達しない循環（閉包の外）
    REQ-020 <-> REQ-021   起点REQ-020の閉包の内側の循環
    REQ-030 -> api::REQ-130 -> platform::REQ-030   ワークスペースをまたぐ循環（起点ワークスペースが宣言する辺は REQ-030 の1本）
    ```
    """

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("api", "apps/api")]))
        _member_tree(r, "api", "apps/api")
        _write(r, "tests/t.py", "x\n")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", covers_test=True))
        _write(r, ".spec/requirements/REQ-010.md", _req("REQ-010", requires=["REQ-011"], covers_test=True))
        _write(r, ".spec/requirements/REQ-011.md", _req("REQ-011", requires=["REQ-010"], covers_test=True))
        _write(r, ".spec/requirements/REQ-020.md", _req("REQ-020", requires=["REQ-021"], covers_test=True))
        _write(r, ".spec/requirements/REQ-021.md", _req("REQ-021", requires=["REQ-020"], covers_test=True))
        _write(r, ".spec/requirements/REQ-030.md", _req("REQ-030", requires=["api::REQ-130"], covers_test=True))
        _write(r, "apps/api/.spec/requirements/REQ-130.md", _req("REQ-130", requires=["platform::REQ-030"]))

    def test_context_ignores_a_cycle_outside_the_closure(self):
        for purpose in ("interpret", "implement"):
            with self.subTest(purpose=purpose):
                result, code = self.context("REQ-001", "--purpose", purpose)
                self.assertNotIn("CTX-CYCLE-001", self.codes(result), result["diagnostics"])
                self.assertIn(result["status"], ("passed", "passed_with_warnings"))
                self.assertEqual(code, 0)
                self.assertEqual(self.doc_ids(result), ["platform::REQ-001"])

    def test_context_reports_a_cycle_inside_the_closure(self):
        result, code = self.context("REQ-020")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(
            [(d["code"], d["source"]["workspaceId"], d["source"]["path"]) for d in result["diagnostics"]],
            [
                ("CTX-CYCLE-001", "platform", ".spec/requirements/REQ-020.md"),
                ("CTX-CYCLE-001", "platform", ".spec/requirements/REQ-021.md"),
            ],
        )

    def test_context_reports_only_edges_declared_by_the_active_workspace_for_a_cross_workspace_cycle(self):
        result, code = self.context("REQ-030")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(
            [(d["code"], d["source"]["workspaceId"], d["source"]["path"]) for d in result["diagnostics"]],
            [("CTX-CYCLE-001", "platform", ".spec/requirements/REQ-030.md")],
        )

    def test_check_with_an_explicit_target_keeps_returning_the_cycle_edges_of_the_closure(self):
        result, code = self.check("REQ-020")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(
            sorted(d["source"]["path"] for d in result["diagnostics"] if d["code"] == "CTX-CYCLE-001"),
            [".spec/requirements/REQ-020.md", ".spec/requirements/REQ-021.md"],
        )

    def test_verify_with_an_explicit_target_reports_a_cycle_inside_the_closure(self):
        result, code = self.verify("REQ-020")
        self.assertEqual((result["status"], code), ("failed", 1))
        (target,) = result["targetResults"]
        self.assertEqual((target["target"], target["status"]), ("platform::REQ-020", "failed"))
        self.assertEqual([d["code"] for d in target["diagnostics"]], ["CTX-CYCLE-001", "CTX-CYCLE-001"])

    def test_verify_with_an_explicit_target_ignores_a_cycle_outside_the_closure(self):
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0))
        (target,) = result["targetResults"]
        self.assertEqual((target["status"], target["diagnostics"]), ("passed", []))

    def test_verify_default_targets_report_cycles_only_for_the_targets_whose_closure_has_one(self):
        for argv in (("verify",), ("verify", "--all-workspaces")):
            with self.subTest(argv=argv):
                result, code = self._run(verify_mod, "verify", argv[1:])
                self.assertEqual((result["status"], code), ("failed", 1))
                if "--all-workspaces" in argv:
                    (platform,) = [w for w in result["workspaces"] if w["id"] == "platform"]
                    targets = platform["targetResults"]
                else:
                    targets = result["targetResults"]
                by_target = {t["target"]: t for t in targets}
                self.assertEqual(by_target["platform::REQ-001"]["status"], "passed")
                for failing in ("REQ-010", "REQ-011", "REQ-020", "REQ-021", "REQ-030"):
                    self.assertEqual(by_target[f"platform::{failing}"]["status"], "failed", failing)
                    self.assertIn("CTX-CYCLE-001", [d["code"] for d in by_target[f"platform::{failing}"]["diagnostics"]])

    def test_output_is_independent_of_hash_seed(self):
        cases = [("context", "REQ-020"), ("context", "REQ-001"), ("verify", "REQ-020"), ("verify", "--all-workspaces")]
        for argv in cases:
            outputs = {seed: _run_cli(self.root, seed, *argv) for seed in ("0", "1", "12345")}
            with self.subTest(argv=argv):
                self.assertEqual(len(set(outputs.values())), 1, outputs)


class ClosureCycleSingleWorkspaceControlTests(_Base):
    """対照: 単一ワークスペースの挙動は変わらない（閉包の外の循環は返さず、閉包の内側の循環は返す）。"""

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _single_yaml("solo"))
        _write(r, "tests/t.py", "x\n")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", covers_test=True))
        _write(r, ".spec/requirements/REQ-010.md", _req("REQ-010", requires=["REQ-011"], covers_test=True))
        _write(r, ".spec/requirements/REQ-011.md", _req("REQ-011", requires=["REQ-010"], covers_test=True))

    def test_context_and_verify(self):
        result, code = self.context("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0))
        result, code = self.context("REQ-010")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(self.codes(result), ["CTX-CYCLE-001", "CTX-CYCLE-001"])
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0))
        result, code = self.verify("REQ-010")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual([d["code"] for d in result["targetResults"][0]["diagnostics"]], ["CTX-CYCLE-001", "CTX-CYCLE-001"])


class AliasDoubleCountingTests(_Base):
    """C21: 作業ワークスペースの文書が、修飾のあるIDとないIDの別名で二重に収録されない。

    ```
    platform(作業)  REQ-001(強い関係の誤りを持てる)  REQ-002 -> api::REQ-100  [-> REQ-001]
    api             REQ-100 -> platform::REQ-001
    ```
    """

    bad_req_001 = False
    direct_requires = True

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("api", "apps/api")]))
        _member_tree(r, "api", "apps/api")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", requires=["REQ-999"] if self.bad_req_001 else None))
        requires = ["api::REQ-100"] + (["REQ-001"] if self.direct_requires else [])
        _write(r, ".spec/requirements/REQ-002.md", _req("REQ-002", requires=requires))
        _write(r, "apps/api/.spec/requirements/REQ-100.md", _req("REQ-100", requires=["platform::REQ-001"]))

    def test_a_document_reached_by_an_unqualified_and_a_qualified_reference_is_listed_once(self):
        result, code = self.context("REQ-002")
        self.assertEqual((result["status"], code), ("passed", 0))
        ids = self.doc_ids(result)
        self.assertEqual(len(ids), len(set(ids)), ids)
        self.assertEqual(sorted(ids), ["api::REQ-100", "platform::REQ-001", "platform::REQ-002"])
        self.assertEqual(result["resolution"]["documentCount"], 3)

    def test_the_relations_of_a_document_reached_only_by_a_qualified_reference_are_checked(self):
        # REQ-002が`api::REQ-100`だけを経由してREQ-001へ到達する（修飾のないキーでは到達しない）構成。
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002", requires=["api::REQ-100"]))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", requires=["REQ-999"]))
        for purpose in ("interpret", "implement"):
            with self.subTest(purpose=purpose):
                result, code = self.context("REQ-002", "--purpose", purpose)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(
                    [(d["code"], d["source"]["workspaceId"], d["source"]["path"], d.get("evidence")) for d in result["diagnostics"]],
                    [("SPEC-RELATION-MISSING-001", "platform", ".spec/requirements/REQ-001.md", "REQ-999")],
                )

    def test_output_is_independent_of_hash_seed(self):
        outputs = {seed: _run_cli(self.root, seed, "context", "REQ-002") for seed in ("0", "1", "12345")}
        self.assertEqual(len(set(outputs.values())), 1, outputs)


class AliasRefinerAndSuccessorTests(_Base):
    """C21（同じ原因の別の経路）: 逆参照・`supersedes`の後継・`addresses`の走査が別名のキーを数えない。

    ```
    platform(作業)  REQ-001  TECH-001 refines REQ-001:AC-01  REQ-003 supersedes REQ-001
                    TASK-001 addresses platform::REQ-001:AC-01（自ワークスペースを修飾した宣言）  TASK-002 addresses REQ-001:AC-01
    api             TECH-100 refines platform::REQ-001:AC-01  TASK-100 addresses platform::REQ-001:AC-01
    ```
    """

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("api", "apps/api")]))
        _member_tree(r, "api", "apps/api")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(r, ".spec/technical/TECH-001.md", _tech("TECH-001", "REQ-001:AC-01"))
        _write(r, "apps/api/.spec/technical/TECH-100.md", _tech("TECH-100", "platform::REQ-001:AC-01"))
        _write(r, ".spec/tasks/TASK-001.md", _task("TASK-001", "platform::REQ-001:AC-01"))
        _write(r, ".spec/tasks/TASK-002.md", _task("TASK-002", "REQ-001:AC-01"))
        _write(r, "apps/api/.spec/tasks/TASK-100.md", _task("TASK-100", "platform::REQ-001:AC-01"))

    def test_a_refining_document_of_the_root_is_listed_once(self):
        for purpose in ("interpret", "implement"):
            with self.subTest(purpose=purpose):
                result, _code = self.context("REQ-001", "--purpose", purpose)
                ids = self.doc_ids(result)
                self.assertEqual(len(ids), len(set(ids)), ids)
                self.assertEqual(
                    sorted(i for i in ids if "TECH" in i), ["api::TECH-100", "platform::TECH-001"]
                )

    def test_tasks_addressing_a_target_statement_are_included_whichever_way_the_reference_is_written(self):
        result, _code = self.context("REQ-001", "--purpose", "implement")
        ids = self.doc_ids(result)
        self.assertEqual(len(ids), len(set(ids)), ids)
        self.assertEqual(
            sorted(i for i in ids if "TASK" in i), ["api::TASK-100", "platform::TASK-001", "platform::TASK-002"]
        )
        must = result["coverage"]["must"]
        self.assertEqual((must["unaddressed"], must["addressed"]), ([], ["platform::REQ-001:AC-01"]))
        # TASKを起点にしたときも、自ワークスペースを修飾した`addresses`で対象規範文へ到達する。
        result, _code = self.context("TASK-001", "--purpose", "implement")
        self.assertEqual(result["coverage"]["must"]["addressed"], ["platform::REQ-001:AC-01"])

    def test_a_single_successor_is_not_counted_twice(self):
        _write(self.root, ".spec/requirements/REQ-003.md", _req("REQ-003", supersedes=["REQ-001"]))
        result, code = self.context("REQ-001")
        self.assertNotIn("CTX-STATE-SUPERSEDED-002", self.codes(result), result["diagnostics"])
        self.assertEqual((result["status"], code), ("passed", 0))
        roles = {d["id"]: d["role"] for d in result["documents"]}
        self.assertEqual((roles["platform::REQ-001"], roles["platform::REQ-003"]), ("advisory", "replacement"))
        # 後継が2つあれば従来どおり`CTX-STATE-SUPERSEDED-002`。
        _write(self.root, ".spec/requirements/REQ-004.md", _req("REQ-004", supersedes=["REQ-001"]))
        result, _code = self.context("REQ-001")
        self.assertIn("CTX-STATE-SUPERSEDED-002", self.codes(result))


class AliasSingleWorkspaceControlTests(_Base):
    """対照: 単一ワークスペースでは別名が無く、逆参照・`addresses`の収録は従来どおり1回ずつである。"""

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _single_yaml("solo"))
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(r, ".spec/technical/TECH-001.md", _tech("TECH-001", "REQ-001:AC-01"))
        _write(r, ".spec/tasks/TASK-002.md", _task("TASK-002", "REQ-001:AC-01"))

    def test_documents_are_listed_once(self):
        result, code = self.context("REQ-001", "--purpose", "interpret")
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(sorted(self.doc_ids(result)), ["REQ-001", "TECH-001"])
        result, _code = self.context("REQ-001", "--purpose", "implement")
        self.assertEqual(sorted(self.doc_ids(result)), ["REQ-001", "TASK-002", "TECH-001"])
        self.assertEqual(result["coverage"]["must"]["addressed"], ["REQ-001:AC-01"])
        result, _code = self.context("TASK-002", "--purpose", "implement")
        self.assertEqual(sorted(self.doc_ids(result)), ["REQ-001", "TASK-002", "TECH-001"])


class SupersededSummaryQualifiedTests(_Base):
    """複合ワークスペースの`CTX-STATE-SUPERSEDED-*`の`summary`は、差し込む文書IDを正規形式（修飾ID）にする。

    複合ワークスペース仕様 §4（複合ワークスペース内の出力は正規形式）。起点と依存先も、後継と同じく修飾する。
    文型は変えない。
    ```
    platform(作業)  REQ-001(置換される)  REQ-010 requires REQ-001  REQ-003 supersedes REQ-001（同じワークスペースの後継、``same_ws``のとき）
    api             REQ-009 supersedes platform::REQ-001（他のメンバーの後継、``other_ws``のとき）
    ```
    """

    same_ws = False
    other_ws = True

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("api", "apps/api")]))
        _member_tree(r, "api", "apps/api")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(r, ".spec/requirements/REQ-010.md", _req("REQ-010", requires=["REQ-001"]))
        if self.same_ws:
            _write(r, ".spec/requirements/REQ-003.md", _req("REQ-003", supersedes=["REQ-001"]))
        if self.other_ws:
            _write(r, "apps/api/.spec/requirements/REQ-009.md", _req("REQ-009", supersedes=["platform::REQ-001"]))

    def summaries(self, diagnostics: list[dict]) -> list[tuple[str, str]]:
        return [(d["code"], d["summary"]) for d in diagnostics if d["code"].startswith("CTX-STATE-SUPERSEDED")]

    @property
    def successor(self) -> str:
        return "platform::REQ-003" if self.same_ws else "api::REQ-009"

    def test_origin_summary_is_qualified_for_context_and_verify(self):
        expected = [("CTX-STATE-SUPERSEDED-001", f"起点platform::REQ-001は{self.successor}に置換されています")]
        for purpose in ("implement", "verify"):
            with self.subTest(purpose=purpose):
                result, code = self.context("REQ-001", "--purpose", purpose)
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual(self.summaries(result["diagnostics"]), expected)
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(self.summaries(result["targetResults"][0]["diagnostics"]), expected)

    def test_dependency_summary_is_qualified_for_context_and_verify(self):
        expected = [("CTX-STATE-SUPERSEDED-001", f"依存先platform::REQ-001は{self.successor}に置換されています")]
        result, code = self.context("REQ-010", "--purpose", "implement")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(self.summaries(result["diagnostics"]), expected)
        result, code = self.verify("REQ-010")
        self.assertEqual(self.summaries(result["targetResults"][0]["diagnostics"]), expected)

    def test_output_is_independent_of_hash_seed(self):
        outputs = {seed: _run_cli(self.root, seed, "verify", "REQ-001") for seed in ("0", "1", "12345")}
        self.assertEqual(len(set(outputs.values())), 1, outputs)


class SupersededSummaryQualifiedSameWorkspaceTests(SupersededSummaryQualifiedTests):
    """同じワークスペースの後継だけ（後継も起点も修飾する）。"""

    same_ws = True
    other_ws = False


class SupersededMultipleSummaryQualifiedTests(SupersededSummaryQualifiedTests):
    """有効な後継が複数（同じワークスペースと他のメンバー）のとき、`CTX-STATE-SUPERSEDED-002`の文書IDも修飾する。"""

    same_ws = True
    other_ws = True

    def test_origin_summary_is_qualified_for_context_and_verify(self):
        expected = [("CTX-STATE-SUPERSEDED-002", "platform::REQ-001の有効な後継が複数存在します")]
        for purpose in ("interpret", "implement", "verify"):
            with self.subTest(purpose=purpose):
                result, code = self.context("REQ-001", "--purpose", purpose)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(self.summaries(result["diagnostics"]), expected)
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(self.summaries(result["targetResults"][0]["diagnostics"]), expected)

    def test_dependency_summary_is_qualified_for_context_and_verify(self):
        expected = [("CTX-STATE-SUPERSEDED-002", "platform::REQ-001の有効な後継が複数存在します")]
        result, code = self.context("REQ-010", "--purpose", "implement")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(self.summaries(result["diagnostics"]), expected)


class SupersededSummarySingleWorkspaceControlTests(_Base):
    """対照: 単一ワークスペースの`summary`は修飾しない（承認済みの文型のまま）。"""

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _single_yaml("solo"))
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(r, ".spec/requirements/REQ-010.md", _req("REQ-010", requires=["REQ-001"]))
        _write(r, ".spec/requirements/REQ-003.md", _req("REQ-003", supersedes=["REQ-001"]))

    def test_summaries_are_unqualified(self):
        result, code = self.context("REQ-001", "--purpose", "implement")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(
            [(d["code"], d["summary"]) for d in result["diagnostics"]],
            [("CTX-STATE-SUPERSEDED-001", "起点REQ-001はREQ-003に置換されています")],
        )
        result, _code = self.context("REQ-010", "--purpose", "implement")
        self.assertEqual(
            [(d["code"], d["summary"]) for d in result["diagnostics"]],
            [("CTX-STATE-SUPERSEDED-001", "依存先REQ-001はREQ-003に置換されています")],
        )
        _write(self.root, ".spec/requirements/REQ-004.md", _req("REQ-004", supersedes=["REQ-001"]))
        result, _code = self.context("REQ-001", "--purpose", "interpret")
        self.assertEqual(
            [(d["code"], d["summary"]) for d in result["diagnostics"]],
            [("CTX-STATE-SUPERSEDED-002", "REQ-001の有効な後継が複数存在します")],
        )
        result, _code = self.verify("REQ-001")
        self.assertEqual(
            [d["summary"] for d in result["targetResults"][0]["diagnostics"]], ["REQ-001の有効な後継が複数存在します"]
        )


class DeclaredEvidenceTests(_Base):
    """C19: 他のメンバーの文書の`requires`の`CTX-RELATION-TYPE-001`の`evidence`は宣言どおりの綴りで返す。

    `web`のREQ-100が`requires: [<declared>]`（`<declared>`は`ADR-001`または自ワークスペースを修飾した`web::ADR-001`）で、
    状態が`proposed`のADRを指す。`platform`(作業)のREQ-001が`web::REQ-100`を`requires`する。
    """

    declared = "ADR-001"

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web")]))
        _member_tree(r, "web", "apps/web")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", requires=["web::REQ-100"], covers_test=True))
        _write(r, "tests/t.py", "x\n")
        _write(r, "apps/web/.spec/requirements/REQ-100.md", _req("REQ-100", requires=[self.declared]))
        _write(r, "apps/web/.spec/decisions/ADR-001.md", _adr("ADR-001", "proposed"))

    def expected_diag(self) -> tuple:
        return ("CTX-RELATION-TYPE-001", "web", ".spec/requirements/REQ-100.md", self.declared)

    def relation_diagnostics(self, diagnostics: list[dict]) -> list[tuple]:
        return [
            (d["code"], d["source"]["workspaceId"], d["source"]["path"], d.get("evidence"))
            for d in diagnostics
            if d["code"] == "CTX-RELATION-TYPE-001"
        ]

    def test_evidence_is_the_declared_spelling_for_every_purpose_and_for_verify(self):
        for purpose in ("interpret", "implement", "verify"):
            with self.subTest(purpose=purpose):
                result, code = self.context("REQ-001", "--purpose", purpose)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(self.relation_diagnostics(result["diagnostics"]), [self.expected_diag()])
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("failed", 1))
        (target,) = result["targetResults"]
        self.assertEqual(self.relation_diagnostics(target["diagnostics"]), [self.expected_diag()])


class DeclaredEvidenceQualifiedTests(DeclaredEvidenceTests):
    """自ワークスペースを修飾して書いた`web::ADR-001`の修飾を失わない。"""

    declared = "web::ADR-001"


class InterpretAdrTests(_Base):
    """D7: 目的`interpret`でも、他のメンバーの文書の`requires`が`accepted`でないADRを指すことを検出する。"""

    adr_status = "proposed"

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web")]))
        _member_tree(r, "web", "apps/web")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", requires=["web::REQ-100", "ADR-900"]))
        _write(r, ".spec/decisions/ADR-900.md", _adr("ADR-900", self.adr_status))
        _write(r, "apps/web/.spec/requirements/REQ-100.md", _req("REQ-100", requires=["ADR-001"]))
        _write(r, "apps/web/.spec/decisions/ADR-001.md", _adr("ADR-001", self.adr_status))

    def test_an_adr_that_is_not_accepted_is_detected_once_per_edge(self):
        result, code = self.context("REQ-001", "--purpose", "interpret")
        self.assertEqual((result["status"], code), ("failed", 1))
        # 起点ワークスペースの文書の辺(REQ-001 -> ADR-900)は関係の検査、他のメンバーの文書の辺(REQ-100 -> ADR-001)は展開が検出する。
        self.assertEqual(
            sorted(
                (d["code"], d["source"]["workspaceId"], d["source"]["path"], d.get("evidence")) for d in result["diagnostics"]
            ),
            [
                ("CTX-RELATION-TYPE-001", "platform", ".spec/requirements/REQ-001.md", "ADR-900"),
                ("CTX-RELATION-TYPE-001", "web", ".spec/requirements/REQ-100.md", "ADR-001"),
            ],
        )

    def test_the_same_edge_is_detected_by_implement_and_verify(self):
        interpret, _ = self.context("REQ-001", "--purpose", "interpret")
        for purpose in ("implement", "verify"):
            other, _code = self.context("REQ-001", "--purpose", purpose)
            self.assertEqual(
                sorted((d["code"], d["source"]["path"], d.get("evidence")) for d in other["diagnostics"]),
                sorted((d["code"], d["source"]["path"], d.get("evidence")) for d in interpret["diagnostics"]),
            )

    def test_output_is_independent_of_hash_seed(self):
        outputs = {seed: _run_cli(self.root, seed, "context", "REQ-001", "--purpose", "interpret") for seed in ("0", "1", "12345")}
        self.assertEqual(len(set(outputs.values())), 1, outputs)


class InterpretAdrAcceptedTests(InterpretAdrTests):
    """`accepted`のADRは検出しない（陰性対照）。"""

    adr_status = "accepted"

    def test_an_adr_that_is_not_accepted_is_detected_once_per_edge(self):
        result, code = self.context("REQ-001", "--purpose", "interpret")
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertNotIn("CTX-RELATION-TYPE-001", self.codes(result))

    def test_the_same_edge_is_detected_by_implement_and_verify(self):
        for purpose in ("implement", "verify"):
            result, _code = self.context("REQ-001", "--purpose", purpose)
            self.assertNotIn("CTX-RELATION-TYPE-001", self.codes(result))


class InterpretAdrSingleWorkspaceControlTests(_Base):
    """対照: 単一ワークスペースの`interpret`は従来どおり、`accepted`でないADRへの`requires`を1件だけ検出する。"""

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _single_yaml("solo"))
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", requires=["ADR-001"]))
        _write(r, ".spec/decisions/ADR-001.md", _adr("ADR-001", "proposed"))

    def test_detected_once(self):
        for purpose in ("interpret", "implement", "verify"):
            with self.subTest(purpose=purpose):
                result, code = self.context("REQ-001", "--purpose", purpose)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(
                    [(d["code"], d.get("evidence")) for d in result["diagnostics"]], [("CTX-RELATION-TYPE-001", "ADR-001")]
                )


def _run_cli(cwd: Path, seed: str, *argv: str) -> str:
    """CLIを別プロセスで実行し、`durationMs`を除いた出力を返す。"""

    proc = subprocess.run(
        [sys.executable, "-m", "bitz.cli", *argv, "--format", "json"], cwd=cwd,
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True, text=True,
    )
    return json.dumps([proc.returncode, _without_durations(json.loads(proc.stdout))], ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
