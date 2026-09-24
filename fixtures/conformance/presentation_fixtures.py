"""matrix §6.11の既定表示とrevisionを固定した証拠。

描画処理、Gitの読取り、Core操作は実装しない。各fixtureはreview済みのcorpusと結果を再利用し、
提示または環境の性質をちょうど1つだけ変える。`--format`の省略、commitの有無、空のcommand出力、
2つのtargetでの同一条件である。
"""
import copy
import json
from pathlib import Path
import os
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference, markdown_reference
from . import digest_fixtures, report_absent_fixtures, verify_fixtures, verify_output_fixtures
from .harness import setup, git, snapshot
from .initial_fixtures import CONFIGS, observe, compare_state
from .registry_closure_fixtures import CORE, doctor_checks

HERE = Path(__file__).resolve().parent
CONFIG_PATH = digest_reference.CONFIG_PATH
SILENT_SCRIPT = "#!/bin/sh\nexit 0\n"
MISSING_ROOTS = ["REQ-900", "REQ-901"]
GOLDEN = verify_fixtures.GOLDEN
SUMMARY_PATTERN = re.compile(
    r"^(?P<operation>[a-z]+) (?P<status>[a-z_]+) (?:scope=(?P<scope>[a-z-]+) )?"
    r"targets=(?P<targets>\d+) diagnostics=(?P<diagnostics>\d+) \(\d+ms\)$")
TEXT = {
    "SINGLE-104-02": "check passed scope=full targets=3 diagnostics=0 (0ms)\n",
    "SINGLE-104-03": "verify passed scope=selected targets=1 diagnostics=0 (0ms)\n",
    "SINGLE-104-04": "doctor passed targets=8 diagnostics=0 (0ms)\n",
    "SINGLE-106-05": "verify failed scope=selected targets=2 diagnostics=2 (0ms)\n" + "".join(
        f"invocation:::: error: CTX-ROOT-MISSING-001: 起点{root}が存在しません\n" for root in MISSING_ROOTS),
}
# ID: (操作, status, 終了コード, 説明)
CASES = {
    "SINGLE-104-01": ("context", "passed", 0, "format省略のcontextが既定のMarkdown提示を返す"),
    "SINGLE-104-02": ("check", "passed", 0, "format省略のcheckがtext要約行を出す"),
    "SINGLE-104-03": ("verify", "passed", 0, "format省略のverifyがtext要約行を出す"),
    "SINGLE-104-04": ("doctor", "passed", 0, "format省略のdoctorがscope=なしのtext要約行を出す"),
    "SINGLE-105-01": ("context", "passed", 0, "commitのあるcontextが40桁小文字16進のrevisionを返す"),
    "SINGLE-105-02": ("verify", "passed", 0, "Git不在のverifyがrevision nullを返す"),
    "SINGLE-106-04": ("verify", "passed", 0, "出力のないcommandを空excerptとtruncated falseで返す"),
    "SINGLE-106-05": ("verify", "failed", 1, "2 targetの同一条件をtextのdiagnostics総数へ数える"),
}
MARKDOWN_CASES = {"SINGLE-104-01"}
TEXT_CASES = set(TEXT) | MARKDOWN_CASES
GIT_ABSENT = {"SINGLE-105-02"}
COMMITTED = {"SINGLE-104-02", "SINGLE-105-01"}
STAGED = {"SINGLE-104-03", "SINGLE-106-04", "SINGLE-106-05"}


def reviewed_inputs(identifier):
    if identifier == "SINGLE-104-02":
        return report_absent_fixtures.reviewed_inputs("SINGLE-070-01")
    if identifier == "SINGLE-104-04":
        return {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
    if identifier == "SINGLE-106-04":
        inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
        inputs[CONFIG_PATH] = digest_reference.CONFIG.replace(
            '"/bin/true", "{tests}"', f'"{verify_output_fixtures.COMMAND_PATH}", "{{tests}}"').encode()
        inputs[verify_output_fixtures.COMMAND_PATH] = SILENT_SCRIPT.encode()
        return inputs
    if identifier in {"SINGLE-104-03", "SINGLE-105-02"}:
        return verify_fixtures.reviewed_inputs("SINGLE-055")
    return dict(digest_reference.reviewed_inputs("SINGLE-042"))


def executables(identifier):
    return {verify_output_fixtures.COMMAND_PATH} if identifier == "SINGLE-106-04" else set()


def context_digest(identifier):
    if identifier == "SINGLE-106-04":
        return verify_output_fixtures.context_digest("SINGLE-069-01")
    return GOLDEN


def reviewed_manifest(identifier):
    operation, status, exit_code, description = CASES[identifier]
    plan = {"git": identifier not in GIT_ABSENT, "operations": []}
    if identifier in COMMITTED:
        plan["baseCommit"] = {"message": "base", "paths": ["."]}
    elif identifier in STAGED:
        plan["operations"] = [{"op": "stage", "paths": ["."]}]
    argv = {"check": ["check", "--full", "--base", "HEAD"],
            "doctor": ["doctor"],
            "context": ["context", "REQ-001", "--purpose", "verify"],
            "verify": ["verify", *(MISSING_ROOTS if identifier == "SINGLE-106-05" else ["REQ-001"])],
            }[operation]
    if identifier == "SINGLE-106-05":
        argv = [*argv, "--format", "text"]
    elif identifier not in TEXT_CASES:
        argv = [*argv, "--format", "json"]
    stdout = ("markdown" if identifier in MARKDOWN_CASES
              else "text" if identifier in TEXT_CASES else "json")
    expect = {"status": status, "exitCode": exit_code, "stdout": stdout,
              "resultFile": f"expected/{operation}.json", "reportFileCount": 0}
    if identifier in TEXT_CASES:
        expect["textFile"] = f"expected/{operation}.txt"
    return {"fixtureId": identifier, "description": description, "setup": plan,
            "invocation": {"runner": "bitz", "cwd": ".", "argv": argv,
                           "env": {"PATH": "/dev/null"} if identifier in GIT_ABSENT else {}},
            "expect": expect}


def silent_command():
    command = copy.deepcopy(verify_output_fixtures.reviewed_result("SINGLE-069-01")["commands"][0])
    command.update(stdoutExcerpt="", stderrExcerpt="", stdoutTruncated=False, stderrTruncated=False)
    return command


def missing_root_targets():
    return [{"target": root, "status": "failed", "contextDigest": None, "statements": [],
             "bindingRefs": [],
             "diagnostics": [{"code": "CTX-ROOT-MISSING-001", "severity": "error",
                              "resultStatus": "failed", "summary": f"起点{root}が存在しません",
                              "source": {"kind": "invocation", "argument": root}}]}
            for root in MISSING_ROOTS]


def reviewed_result(identifier):
    if identifier == "SINGLE-104-02":
        return report_absent_fixtures.reviewed_result("SINGLE-070-01")
    if identifier == "SINGLE-104-04":
        return {"schemaVersion": "1.0", "operation": "doctor", "status": "passed",
                "workspace": {"id": "root", "path": "."}, "durationMs": 0, "diagnostics": [],
                "core": copy.deepcopy(CORE), "checks": doctor_checks()}
    if identifier == "SINGLE-104-01":
        return digest_fixtures.reviewed_result("SINGLE-042", GOLDEN)
    if identifier == "SINGLE-105-01":
        result = digest_fixtures.reviewed_result("SINGLE-042", GOLDEN)
        result["revision"] = {"commit": "0" * 40, "dirty": False}
        return result
    if identifier in {"SINGLE-104-03", "SINGLE-105-02"}:
        return verify_fixtures.reviewed_result("SINGLE-055")
    if identifier == "SINGLE-106-04":
        result = verify_output_fixtures.reviewed_result("SINGLE-069-01")
        result["commands"] = [silent_command()]
        return result
    result = verify_output_fixtures.reviewed_result("SINGLE-069-01")
    result.update(status="failed", targetResults=missing_root_targets(), commands=[])
    return result


def check_summary_line(identifier, result, text):
    """review済みのtextは、別に数えた表示ではなく、公開した導出手順を通して
    対応するJSONと一致しなければならない。"""
    lines = text.decode().splitlines()
    match = SUMMARY_PATTERN.match(lines[0])
    if match is None:
        raise ValueError("要約行がreview済みの形に従っていません")
    operation = result["operation"]
    targets = {"check": lambda: result.get("checkedDocumentCount"),
               "verify": lambda: len(result.get("targetResults", [])),
               "doctor": lambda: len(result.get("checks", []))}[operation]()
    diagnostics = len(result["diagnostics"]) + sum(
        len(target["diagnostics"]) for target in result.get("targetResults", []))
    if (match["operation"] != operation or match["status"] != result["status"]
            or int(match["targets"]) != targets or int(match["diagnostics"]) != diagnostics):
        raise ValueError("要約行がJSONからの導出と異なります")
    if (match["scope"] is None) != (operation == "doctor") or (
            match["scope"] is not None and match["scope"] != result["scope"]):
        raise ValueError("doctorはscope=を省略し、他の操作はこれを表示する必要があります")
    if len(lines) != 1 + diagnostics:
        raise ValueError("要約行の後にDiagnosticごとに1行が続く必要があります")


def check_revision(identifier, result, repository):
    """置き場所の値を信頼せず、隔離したrepositoryを観測する。"""
    operation = CASES[identifier][0]
    if operation == "doctor":
        if "revision" in result:
            raise ValueError("doctorの結果はrevisionを持ちません")
        return
    revision = result["revision"]
    if identifier not in COMMITTED:
        if revision is not None:
            raise ValueError("commitのないfixtureはrevision nullを返す必要があります")
        return
    commit = git(repository, "rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("隔離setupが40桁の小文字のcommitを作りませんでした")
    if git(repository, "status", "--porcelain=v1").decode() != "":
        raise ValueError("cleanなrevisionの期待値にはcleanな作業treeが必要です")
    # checkは基準版のrevisionも持つ。contextとverifyは現在のrevisionだけを持つ。
    expected = {"base", "commit", "dirty"} if operation == "check" else {"commit", "dirty"}
    if set(revision) != expected or revision["dirty"]:
        raise ValueError("revisionはこの操作のreview済みのcleanな形である必要があります")


def observe_silence(repository):
    executable = repository / verify_output_fixtures.COMMAND_PATH
    if not (executable.is_file() and os.access(executable, os.X_OK)):
        raise ValueError("command fileは通常の実行可能fileである必要があります")
    completed = subprocess.run([str(executable)], cwd=repository, capture_output=True, timeout=60)
    if completed.returncode != 0 or completed.stdout or completed.stderr:
        raise ValueError("review済みのcommandは成功し、何も書いてはいけません")


def check_markdown(path, result):
    """commitしたMarkdownは§9の参照描画と一致し、sectionの順序、
    変更しない本文、所要時間tokenがないことを保たなければならない。"""
    text = path.read_bytes()
    if text != markdown_reference.render(result).encode():
        raise ValueError("Markdownがreview済みの結果の参照描画と異なります")
    value = text.decode()
    if "\r" in value or not value.endswith("\n") or value.endswith("\n\n"):
        raise ValueError("MarkdownはLFを使い、改行1個で終わる必要があります")
    if "\n\n\n" in value:
        raise ValueError("Markdownは連続した空行を持ってはいけません")
    # 提示した本文の中の見出しはSPECに属し、Bundleには属さない。
    outside = value
    for document in result["documents"]:
        body = document.get("bodyText")
        if body is None:
            continue
        marker = markdown_reference.fence(body)
        block = f"{marker}markdown\n{body}{marker}\n"
        if value.count(block) != 1:
            raise ValueError("本文がない、変更されている、または最長runより長いfenceで囲まれていません")
        outside = outside.replace(block, "", 1)
    headings = [line[3:] for line in outside.splitlines() if line.startswith("## ")]
    if headings != markdown_reference.SECTIONS:
        raise ValueError("sectionの見出しが固定した順序と異なります")
    if [line for line in outside.splitlines() if line.startswith("# ")] != ["# Context Bundle"]:
        raise ValueError("BundleはreviewしたH1をちょうど1つ持つ必要があります")
    if "durationMs" in outside or re.search(r"\(\d+ms\)", outside):
        raise ValueError("Markdownは所要時間を提示してはいけません")


def observe_state(repository, external, identifier):
    """Git不在は空のstatusではなく、明示的なnullとして記録する。"""
    if identifier not in GIT_ABSENT:
        return observe(repository, external)
    return {"repository": snapshot(repository), "git": None,
            **{name: snapshot(path) for name, path in external.items()}}


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        operation = CASES[identifier][0]
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{operation}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("manifestまたは結果が審査済みの単一条件と異なります")
            if identifier in MARKDOWN_CASES:
                check_markdown(fixture / f"expected/{operation}.txt", result)
            elif identifier in TEXT_CASES:
                text = (fixture / f"expected/{operation}.txt").read_bytes()
                if text != TEXT[identifier].encode():
                    raise ValueError("textがreview済みの完全な出力と異なります")
                check_summary_line(identifier, result, text)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs):
                raise ValueError("入力が審査済みcorpusと異なります")
            for name, path in files.items():
                if path.is_symlink() or path.read_bytes() != inputs[name]:
                    raise ValueError("入力が審査済みcorpusと異なります")
                if bool(path.stat().st_mode & 0o111) != (name in executables(identifier)):
                    raise ValueError(f"{name}の実行bitが審査済み入力と異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("提示はfileを書いてはいけません")
            if (effects["before"]["git"] is None) is (identifier not in GIT_ABSENT):
                raise ValueError("Git snapshotの有無が審査済みの環境と矛盾します")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-presentation-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe_state(repository, external, identifier)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    check_revision(identifier, result, repository)
                    if identifier == "SINGLE-106-04" and run == 0:
                        observe_silence(repository)
                        if compare_state(effects["after"], observe(repository, external)):
                            raise ValueError("commandの観測でfixtureの状態が変わりました")
                    if result.get("contextDigest") or any(
                            target["contextDigest"] for target in result.get("targetResults", [])):
                        derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                        if digest_crosscheck.digest(derived) != context_digest(identifier):
                            raise ValueError("参照計算どうしでContext Digestが一致しません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
