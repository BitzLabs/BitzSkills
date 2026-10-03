#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Gate Bの認定コマンド（ADR-052の`Decision`の4番目の項目）。コミット済みのHEADから独立したクローンを2つ作り、
それぞれで参照適合harnessを`--step N`で実行して結果を照合する（Step 2以降は構文解析器のアダプターも
実行する）。作業ツリーにコミットされていない変更があれば実行しない。

`fixtures/certify_gate_a.py`と同じ作風・構成にする。`tests/`から`fixtures/`とCoreの導入先
`plugins/bitz-core`を参照する（ADR-049の`Decision`の6番目の項目が許す向き）。`uv run`で実行する。

Core本体が未完成の間、`fixtures/conformance/test_fake_core.py`の偽のCoreによる自己試験が
参照harnessの正しさを検査する。このコマンド自体はGate Bの認定手順（クリーンな作業ツリーの判定、独立したクローン、
`--step`の実行、Step 2以降の構文解析器のアダプターの必須化、クローン間の一致の判定）を提供する。
"""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CHECKOUTS = 2
PARSER_ADAPTER = "tests/bitz-core/parser_adapter.py"
CORE_SOURCE = "plugins/bitz-core"


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, timeout=120)


def worktree_errors():
    """作業ツリーがHEADと同じであることを確かめる。未追跡のファイルも変更として数える。"""
    status = git("status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        return [status.stderr.strip() or "`git status`が失敗しました"]
    return ["作業ツリーにコミットされていない変更があります"] if status.stdout else []


def checkout(commit, directory):
    for args, cwd in ((("clone", "--quiet", "--no-checkout", str(ROOT), str(directory)), ROOT),
                      (("checkout", "--quiet", "--detach", commit), directory)):
        completed = git(*args, cwd=cwd)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"`git {args[0]}`が失敗しました")


def run_conformance(uv, directory, step, timeout):
    argv = [uv, "run", "fixtures/run_conformance.py", "--core", CORE_SOURCE, "--step", str(step)]
    completed = subprocess.run(argv, cwd=directory, capture_output=True, timeout=timeout)
    return {"exitCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def run_parser_adapter(uv, directory, timeout):
    """Step 2以降だけが要求する構文解析器のアダプター（適合fixture仕様 4.1）。存在しなければエラーとする。"""
    adapter = directory / PARSER_ADAPTER
    if not adapter.is_file():
        return {"exitCode": None, "stdout": b"", "stderr": b"", "error": "構文解析器のアダプターがありません"}
    completed = subprocess.run([uv, "run", str(adapter)], cwd=directory, capture_output=True, timeout=timeout)
    return {"exitCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "error": None}


def _normalized_conformance_body(stdout_bytes):
    """クローンごとに変わる検査対象のパスと所要時間を除いた、比較可能な結果本体。"""
    report = json.loads(stdout_bytes.decode("utf-8"))
    report["core"] = "<core>"  # クローンごとの一時ディレクトリのパスは実行ごとに変わるため比較対象にしない
    for entry in report.get("fixtures", []):
        entry.pop("durationMs", None)
    return report


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _conformance_digest(stdout_bytes):
    try:
        body = _normalized_conformance_body(stdout_bytes)
    except (ValueError, UnicodeDecodeError, KeyError, TypeError):
        return None
    return sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def judge(step, conformance, parser_adapter):
    """チェックアウトごとの実行結果から、認定を妨げる理由を列挙する。空なら認定できる。"""
    errors = []
    if len(conformance) != CHECKOUTS:
        return [f"チェックアウトは{CHECKOUTS}つ必要です"]
    for index, result in enumerate(conformance, 1):
        try:
            body = _normalized_conformance_body(result["stdout"])
        except (ValueError, UnicodeDecodeError, KeyError, TypeError):
            errors.append(f"参照適合harness{index}: 結果JSONの形式が不正です")
            continue
        if not body.get("allPassed", False):
            errors.append(f"参照適合harness{index}: 選んだfixtureがすべて`passed`ではありません")
        expected_exit = 0 if body.get("allPassed") else 1
        if result["exitCode"] != expected_exit:
            errors.append(f"参照適合harness{index}: 終了コードが`allPassed`と整合しません")
    digests = [_conformance_digest(result["stdout"]) for result in conformance]
    if len(set(digest for digest in digests if digest is not None)) not in (0, 1) or None in digests:
        errors.append("参照適合harnessの結果がチェックアウト間で一致しません")
    if step >= 2:
        if len(parser_adapter) != CHECKOUTS:
            errors.append(f"チェックアウトは{CHECKOUTS}つ必要です（構文解析器のアダプター）")
        else:
            for index, result in enumerate(parser_adapter, 1):
                if result.get("error"):
                    errors.append(f"構文解析器のアダプター{index}: {result['error']}")
                elif result["exitCode"] != 0:
                    errors.append(f"構文解析器のアダプター{index}: 終了コードが0ではありません")
            adapter_stdouts = {result["stdout"] for result in parser_adapter if not result.get("error")}
            if not any(result.get("error") for result in parser_adapter) and len(adapter_stdouts) != 1:
                errors.append("構文解析器のアダプターの結果がチェックアウト間で一致しません")
    return errors


def version(argv):
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    return completed.stdout.strip() if completed.returncode == 0 else None


def parse_args(argv):
    import argparse
    parser = argparse.ArgumentParser(description="Gate Bの認定コマンド（ADR-052の`Decision`の4番目の項目）。")
    parser.add_argument("--step", type=int, required=True, help="判定するStep番号（`steps.json`の`step`）")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    step = args.step
    uv = shutil.which("uv")
    errors = worktree_errors()
    if uv is None:
        errors.append("`uv`が見つかりません")
    head = git("rev-parse", "--verify", "HEAD")
    if head.returncode != 0:
        errors.append("`HEAD`のコミットがありません")
    commit = head.stdout.strip() or None
    conformance, parser_adapter = [], []
    if not errors:
        try:
            with tempfile.TemporaryDirectory(prefix="bitz-gate-b-") as temporary:
                for index in range(CHECKOUTS):
                    directory = Path(temporary) / f"checkout{index}"
                    checkout(commit, directory)
                    conformance.append(run_conformance(uv, directory, step, 900))
                    if step >= 2:
                        parser_adapter.append(run_parser_adapter(uv, directory, 900))
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error).split("\n")[0])
        else:
            errors = judge(step, conformance, parser_adapter)
    report = {
        "gateB": {"step": step, "result": "Passed" if not errors else "Failed"},
        "commit": commit,
        "reports": [_conformance_digest(result["stdout"]) for result in conformance],
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "uv": version([uv, "--version"]) if uv else None,
            "git": version(["git", "--version"]),
            "system": f"{platform.system()} {platform.machine()}",
        },
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
