"""`bitz.multiws`（複合ワークスペースの全体事前検査）の単体試験。

`02_SPECモデル/05_複合workspace仕様.md` §2・§3・§5.1・§8・§10 を対象にする。メンバー単位の
本体処理（横断する関係の解決、メンバー単位の`check`/`verify`/`context`）はStep 5B以降のため対象外。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import doctor as doctor_mod
from bitz import gitutil
from bitz import multiws
from bitz.cliargs import parse_argv

ROOT_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
MEMBER_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: {wid}\n'


def _git_env() -> dict[str, str]:
    return {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _init_repo(root: Path) -> None:
    env = _git_env()
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=root, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, env=env, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"],
        cwd=root,
        env=env,
        check=True,
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _write_member(root: Path, member_path: str, wid: str) -> None:
    _write(root, f"{member_path}/.spec/bitz.yaml", MEMBER_YAML.format(wid=wid))


class CatalogValidationTests(unittest.TestCase):
    def _precheck(self, root: Path):
        git = gitutil.detect_git(str(root), dict(os.environ))
        return multiws.precheck(str(root), git, dict(os.environ), extra_config_revs=["HEAD"])

    def test_duplicate_workspace_id_is_multi_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = (
                ROOT_YAML
                + "multiWorkspace:\n  members:\n"
                + "    - id: web\n      path: apps/web\n"
                + "    - id: web\n      path: apps/other\n"
            )
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _write_member(root, "apps/other", "web")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(len(pre.diagnostics), 1)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-ID-001")

    def test_invalid_workspace_id_is_multi_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # カタログのメンバーのID記述だけを不正にする（メンバー自身の`.spec/bitz.yaml`は妥当なIDのまま
            # にして、メンバー自身の`SPEC-CONFIG-SCHEMA-001`と競合させない）。
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: Web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-ID-001")

    def test_duplicate_member_path_with_matching_ids_is_multi_path(self):
        """完全に同一のメンバー宣言（IDもパスも重複）は組ごとの比較で1件の`PATH`の重複として検出する。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = (
                ROOT_YAML
                + "multiWorkspace:\n  members:\n"
                + "    - id: web\n      path: apps/web\n"
                + "    - id: web\n      path: apps/web\n"
            )
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(len(pre.diagnostics), 1)
            # IDもパスも重複するため、組ごとの比較は`ID`の重複（優先順位920）を`PATH`の重複（930）より
            # 先に検出する。
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-ID-001")

    def test_duplicate_member_path_different_ids_is_multi_member(self):
        """同一のパスへ異なるIDを宣言した場合、2件目はメンバー自身の設定IDの不一致として検出する
        （診断レジストリの優先順位のとおり`MEMBER`(910)が`PATH`(930)より優先される）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = (
                ROOT_YAML
                + "multiWorkspace:\n  members:\n"
                + "    - id: web\n      path: apps/web\n"
                + "    - id: web2\n      path: apps/web\n"
            )
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-MEMBER-001")

    def test_nested_member_path_is_multi_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = (
                ROOT_YAML
                + "multiWorkspace:\n  members:\n"
                + "    - id: web\n      path: apps/web\n"
                + "    - id: inner\n      path: apps/web/inner\n"
            )
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _write_member(root, "apps/web/inner", "inner")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-PATH-001")
            self.assertIn("配下", pre.diagnostics[0].summary)

    def test_segment_boundary_false_positive_is_not_flagged(self):
        """`apps/web`と`apps/web2`はセグメントの境界が異なるため入れ子／重複ではない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = (
                ROOT_YAML
                + "multiWorkspace:\n  members:\n"
                + "    - id: web\n      path: apps/web\n"
                + "    - id: web2\n      path: apps/web2\n"
            )
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _write_member(root, "apps/web2", "web2")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertTrue(pre.ok, pre.diagnostics)
            self.assertEqual([m.id for m in pre.members], ["web", "web2"])

    def test_member_path_symlink_ancestor_is_multi_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            real_dir = root / "real_web"
            _write_member(real_dir, ".", "web")
            (root / "apps").mkdir(parents=True, exist_ok=True)
            os.symlink(real_dir, root / "apps" / "web")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-PATH-001")

    def test_member_config_missing_is_multi_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            (root / "apps" / "web").mkdir(parents=True, exist_ok=True)
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-MEMBER-001")

    def test_member_workspace_id_mismatch_is_multi_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "other")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-MEMBER-001")

    def test_member_declaring_multiworkspace_is_multi_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            nested_yaml = MEMBER_YAML.format(wid="web") + "multiWorkspace:\n  members:\n    - id: x\n      path: y\n"
            _write(root, "apps/web/.spec/bitz.yaml", nested_yaml)
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-MEMBER-001")

    def test_unregistered_git_known_config_is_multi_unregistered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _write_member(root, "libs/native", "native")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-UNREGISTERED-001")
            self.assertEqual(pre.diagnostics[0].source["path"], "libs/native/.spec/bitz.yaml")

    def test_valid_catalog_precheck_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = (
                ROOT_YAML
                + "multiWorkspace:\n  members:\n"
                + "    - id: web\n      path: apps/web\n"
                + "    - id: api\n      path: services/api\n"
            )
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            _write_member(root, "services/api", "api")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertTrue(pre.ok, pre.diagnostics)
            self.assertEqual(pre.root_id, "platform")
            self.assertEqual({m.id for m in pre.members}, {"web", "api"})


class IndependentRawCauseTests(unittest.TestCase):
    """診断レジストリ §2「独立した元の原因はそれぞれ主診断を持つ」の複合ワークスペース版。"""

    def _precheck(self, root: Path):
        git = gitutil.detect_git(str(root), dict(os.environ))
        return multiws.precheck(str(root), git, dict(os.environ), extra_config_revs=[])

    def test_two_members_with_independent_problems_yield_two_diagnostics(self):
        """メンバー1はID重複、メンバー3・メンバー4はパスの入れ子。異なるメンバーの組の独立した元の原因は2件返す。"""

        root_yaml = (
            ROOT_YAML
            + "multiWorkspace:\n  members:\n"
            + "    - id: platform\n      path: apps/dup-id\n"  # ルートと同じID（重複）
            + "    - id: outer\n      path: apps/outer\n"
            + "    - id: inner\n      path: apps/outer/inner\n"  # `outer`の配下（入れ子）
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/dup-id", "platform")
            _write_member(root, "apps/outer", "outer")
            _write_member(root, "apps/outer/inner", "inner")
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            codes = sorted(d.code for d in pre.diagnostics)
            self.assertEqual(codes, ["SPEC-MULTI-ID-001", "SPEC-MULTI-PATH-001"])
            self.assertEqual(len(pre.diagnostics), 2)

    def test_same_member_two_conditions_yield_one_diagnostic(self):
        """1つのメンバーがIDの不正とパスの不正を同時に持つ場合、そのメンバーからは1件だけ返す
        （診断レジストリの優先順位のとおり`MEMBER`(910) > `ID`(920) > `PATH`(930)の順で選ぶ）。
        """

        root_yaml = (
            ROOT_YAML
            + "multiWorkspace:\n  members:\n"
            + "    - id: Bad-ID\n      path: ..\n"  # ID不正 かつ パスの字句上の不正
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, ".spec/bitz.yaml", root_yaml)
            _init_repo(root)

            pre = self._precheck(root)
            self.assertFalse(pre.ok)
            self.assertEqual(len(pre.diagnostics), 1)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-ID-001")


class GitBoundaryTests(unittest.TestCase):
    def test_git_unavailable_yields_multi_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            # Gitリポジトリを作らない（`git`バイナリ自体は使えても境界を確定できない状況を模す）。
            git = gitutil.GitInfo(available=False)
            pre = multiws.precheck(str(root), git, dict(os.environ), extra_config_revs=[])
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-GIT-001")
            self.assertEqual(pre.root_id, "platform")

    def test_doctor_all_workspaces_git_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_yaml = ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            _write(root, ".spec/bitz.yaml", root_yaml)
            _write_member(root, "apps/web", "web")
            parsed = parse_argv(["doctor", "--all-workspaces", "--format", "json"])
            env = {**os.environ, "PATH": "/nonexistent"}
            result, exit_code = doctor_mod.run(parsed, str(root), env)
            self.assertEqual(exit_code, 2)
            self.assertEqual(result["status"], "blocked")
            names = [c["name"] for c in result["checks"]]
            self.assertEqual(names, ["core", "git"])
            self.assertEqual(result["checks"][1]["status"], "blocked")
            self.assertEqual(result["diagnostics"][0]["code"], "SPEC-MULTI-GIT-001")
            self.assertEqual(result["workspaces"], [])


class ResourceLimitTests(unittest.TestCase):
    def _precheck_with_members(self, count, max_members_line=""):
        members_raw = "\n".join(f"    - id: w{i}\n      path: apps/w{i}" for i in range(count))
        root_yaml = ROOT_YAML + f"multiWorkspace:\n{max_members_line}  members:\n{members_raw}\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, ".spec/bitz.yaml", root_yaml)
            for i in range(count):
                _write_member(root, f"apps/w{i}", f"w{i}")
            _init_repo(root)
            git = gitutil.detect_git(str(root), dict(os.environ))
            return multiws.precheck(str(root), git, dict(os.environ), extra_config_revs=[])

    def test_member_count_uses_default_max_members_20(self):
        """`maxMembers`の省略時は既定20が実効上限になる（複合ワークスペース仕様 §2）。"""
        self.assertTrue(self._precheck_with_members(20).ok)
        pre = self._precheck_with_members(21)
        self.assertFalse(pre.ok)
        self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-LIMIT-001")
        self.assertEqual(pre.diagnostics[0].evidence, {"dimension": "memberCount", "limit": 20, "observedAtLeast": 21})

    def test_member_count_uses_explicit_max_members(self):
        """明示した`maxMembers`が絶対上限より狭ければ、それを実効上限にする。"""
        self.assertTrue(self._precheck_with_members(3, "  maxMembers: 3\n").ok)
        pre = self._precheck_with_members(4, "  maxMembers: 3\n")
        self.assertFalse(pre.ok)
        self.assertEqual(pre.diagnostics[0].evidence["limit"], 3)

    def test_member_count_over_hard_limit_stops_early(self):
        """`memberCount`の次元はCoreの絶対上限（既定100）に対して判定する（`複合ワークスペース仕様 §10`）。

        101メンバー分のfixtureを毎回作ると重いため、`HARD_LIMITS["memberCount"]`を一時的に3へ
        下げて早期停止を検証する。
        """

        members_raw = "\n".join(f"    - id: w{i}\n      path: apps/w{i}" for i in range(5))
        root_yaml = ROOT_YAML + f"multiWorkspace:\n  members:\n{members_raw}\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, ".spec/bitz.yaml", root_yaml)
            for i in range(5):
                _write_member(root, f"apps/w{i}", f"w{i}")
            _init_repo(root)

            git = gitutil.detect_git(str(root), dict(os.environ))
            original = dict(multiws.HARD_LIMITS)
            try:
                multiws.HARD_LIMITS["memberCount"] = 3
                pre = multiws.precheck(str(root), git, dict(os.environ), extra_config_revs=[])
            finally:
                multiws.HARD_LIMITS.clear()
                multiws.HARD_LIMITS.update(original)
            self.assertFalse(pre.ok)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-LIMIT-001")
            self.assertEqual(pre.diagnostics[0].evidence["dimension"], "memberCount")
            self.assertEqual(pre.diagnostics[0].evidence["limit"], 3)
            self.assertEqual(pre.diagnostics[0].evidence["observedAtLeast"], 5)

    def test_dimension_priority_and_early_stop(self):
        """複数の次元が並存する合成した`totals`から、表の順で最初の次元が選ばれる。"""

        totals = {
            "specFileCount": 1,
            "inputBytes": 0,
            "statementCount": 0,
            "relationEdgeCount": 0,
            "traceEntryCount": 0,
            "commandDefinitionCount": 0,
        }
        original = dict(multiws.HARD_LIMITS)
        try:
            multiws.HARD_LIMITS["specFileCount"] = 0
            multiws.HARD_LIMITS["inputBytes"] = 0
            self.assertEqual(multiws._first_exceeded(totals), "specFileCount")
        finally:
            multiws.HARD_LIMITS.clear()
            multiws.HARD_LIMITS.update(original)

    def test_statement_and_relation_counting_from_document(self):
        text = (
            "---\n"
            "id: REQ-001\n"
            "title: t\n"
            "status: approved\n"
            "relations:\n"
            "  requires: [TECH-001, TECH-002]\n"
            "  refines: [TECH-003]\n"
            "implements:\n"
            "  - src/a.py\n"
            "  - src/b.py\n"
            "tests:\n"
            "  - path: tests/a.py\n"
            "    covers: [REQ-001:AC-01, REQ-001:AC-02]\n"
            "    command: default\n"
            "---\n"
            "# REQ-001 t\n\n"
            "## Acceptance Criteria\n\n"
            "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] bを満たす。\n"
        )
        stmt_count, rel_count, trace_count = multiws._scan_document_counts(text)
        self.assertEqual(stmt_count, 1)
        self.assertEqual(rel_count, 3)  # `requires`(2) + `refines`(1)
        self.assertEqual(trace_count, 5)  # `implements`(2) + `tests`(1) + `covers`(2)


if __name__ == "__main__":
    unittest.main()
