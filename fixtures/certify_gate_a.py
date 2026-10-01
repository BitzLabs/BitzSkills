#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gate Aの認定コマンド。コミット済みの`HEAD`から新しいチェックアウトを作り、Step 0Bの検証を照合する（Coreの公開操作は実行しない）。

実装計画 §3.1のGate A条件のうち「Coreの実行体へ依存しない1つのコマンドで、新しいチェックアウトから再実行でき、
2回の結果が一致する」を判定する。validate_conformance.pyは自分が新しいチェックアウトで動いているかを判定できないため、
その`pending`に残る1項目だけをこのコマンドで置き換える。
[ADR-048](../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)が
Gate Aの認定に求める規模の検証も、同じチェックアウトで実行する。`uv run`で実行する。

`HEAD`から独立したクローンを2つ作り、それぞれで統合検証と規模の検証を1回ずつ実行する。同じチェックアウトで2回実行すると、
1回目が残したファイルが2回目の入力になり得るためである。作業ツリーにコミットされていない変更があれば実行しない。
"""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CERTIFIED = "full Gate A fresh-checkout repeatability"
CHECKOUTS = 2
CONFORMANCE = ["fixtures/validate_conformance.py"]
SCALE = ["fixtures/validate_scale.py"]


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, timeout=120)


def worktree_errors():
    """作業ツリーが`HEAD`と同じであることを確かめる。未追跡のファイルも変更として数える。"""
    status = git("status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        return [status.stderr.strip() or "git statusが失敗しました"]
    return ["作業treeにcommitされていない変更があります"] if status.stdout else []


def checkout(commit, directory):
    for args, cwd in ((("clone", "--quiet", "--no-checkout", str(ROOT), str(directory)), ROOT),
                      (("checkout", "--quiet", "--detach", commit), directory)):
        completed = git(*args, cwd=cwd)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"git {args[0]}が失敗しました")


def run(uv, script, cwd, timeout):
    completed = subprocess.run([uv, "run", *script], cwd=cwd, capture_output=True, timeout=timeout)
    return {"exitCode": completed.returncode, "stdout": completed.stdout}


def scale_body(stdout):
    """規模の検証の結果から、実行ごとに変わる所要時間を除く。"""
    report = json.loads(stdout)
    report.pop("durationSeconds", None)
    return report


def judge(conformance, scale):
    """チェックアウトごとの実行結果から、認定を妨げる理由を列挙する。空なら認定できる。

    統合検証は、エラーのある検査がなく、未完了の証拠がこのコマンドの認定する1項目だけで、
    全チェックアウトのレポートがバイト列として一致することを求める。規模の検証は全チェックアウトで成功し、所要時間を除いて一致することを求める。
    """
    errors = []
    if len(conformance) != CHECKOUTS or len(scale) != CHECKOUTS:
        return [f"checkoutは{CHECKOUTS}つ必要です"]
    for index, result in enumerate(conformance, 1):
        try:
            report = json.loads(result["stdout"])
            failed = sorted(name for name, check in report["checks"].items() if check.get("errors"))
            pending = report["pending"]
        except (ValueError, KeyError, TypeError, AttributeError):
            errors.append(f"統合検証{index}: reportの形式が不正です")
            continue
        if failed:
            errors.append(f"統合検証{index}: errorのある検査があります（{', '.join(failed)}）")
        if pending != [CERTIFIED]:
            errors.append(f"統合検証{index}: このcommandで認定できない未完了の証拠があります")
        if result["exitCode"] != 1:
            errors.append(f"統合検証{index}: 終了コードが1ではありません")
    if len({result["stdout"] for result in conformance}) != 1:
        errors.append("統合検証のreportがcheckout間でbyte一致しません")
    bodies = []
    for index, result in enumerate(scale, 1):
        try:
            body = scale_body(result["stdout"])
        except (ValueError, AttributeError):
            errors.append(f"scale検証{index}: reportの形式が不正です")
            continue
        bodies.append(body)
        if result["exitCode"] != 0 or body.get("status") != "Passed" or body.get("errors"):
            errors.append(f"scale検証{index}: 成功していません")
    if len(bodies) == CHECKOUTS and bodies[0] != bodies[1]:
        errors.append("scale検証の結果がcheckout間で一致しません")
    return errors


def version(argv):
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    return completed.stdout.strip() if completed.returncode == 0 else None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def scale_digest(stdout):
    try:
        return sha256(json.dumps(scale_body(stdout), ensure_ascii=False, sort_keys=True).encode())
    except (ValueError, AttributeError):
        return None


def main():
    uv = shutil.which("uv")
    errors = worktree_errors()
    if uv is None:
        errors.append("uvが見つかりません")
    head = git("rev-parse", "--verify", "HEAD")
    if head.returncode != 0:
        errors.append("HEADのcommitがありません")
    commit = head.stdout.strip() or None
    conformance, scale = [], []
    if not errors:
        try:
            with tempfile.TemporaryDirectory(prefix="bitz-gate-a-") as temporary:
                for index in range(CHECKOUTS):
                    directory = Path(temporary) / f"checkout{index}"
                    checkout(commit, directory)
                    conformance.append(run(uv, CONFORMANCE, directory, 600))
                    scale.append(run(uv, SCALE, directory, 900))
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error).split("\n")[0])
        else:
            errors = judge(conformance, scale)
    report = {
        "commit": commit,
        "gateA": "Allowed" if not errors else "Blocked",
        "certifies": CERTIFIED,
        "coreExecution": "Not run",
        "conformance": [{"exitCode": result["exitCode"], "reportSha256": sha256(result["stdout"])} for result in conformance],
        "scale": [{"exitCode": result["exitCode"], "resultSha256": scale_digest(result["stdout"])} for result in scale],
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
