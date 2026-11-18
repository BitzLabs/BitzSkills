#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gate Aの認定コマンド。コミット済みの`HEAD`から新しいチェックアウトを作り、Step 0Bの検証を照合する（Coreの公開操作は実行しない）。

実装計画 §3.1のGate A条件のうち「Coreの実行体へ依存しない1つのコマンドで、新しいチェックアウトから再実行でき、
2回の結果が一致する」を判定する。validate_conformance.pyは自分が新しいチェックアウトで動いているかを判定できないため、
その`pending`に残る1項目だけをこのコマンドで置き換える。
実寸の生成を照合する規模の検証（`fixtures/validate_scale.py`）は、
[ADR-076](../docs/02.設計書/10_決定記録/ADR-076_上限の値を設定で小さくできるようにし、実寸の上限の検証を手動にする.md)により
手動で実行する検証であり、Gate Aの認定の条件にしない（ADR-048のDecision 3の部分改訂）。`uv run`で実行する。

`HEAD`から独立したクローンを2つ作り、それぞれで監査を1回ずつ実行する。同じチェックアウトで2回実行すると、
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


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, timeout=120)


def worktree_errors():
    """作業ツリーが`HEAD`と同じであることを確かめる。未追跡のファイルも変更として数える。"""
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


def run(uv, script, cwd, timeout):
    completed = subprocess.run([uv, "run", *script], cwd=cwd, capture_output=True, timeout=timeout)
    return {"exitCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def stderr_tail(result):
    """レポートを読めなかった実行の原因を示すため、標準エラー出力の最後の空でない行を返す。"""
    lines = [line.strip() for line in (result.get("stderr") or b"").decode("utf-8", "replace").splitlines() if line.strip()]
    return f"（{lines[-1]}）" if lines else ""


def judge(conformance):
    """チェックアウトごとの監査の実行結果から、認定を妨げる理由を列挙する。空なら認定できる。

    監査は、エラーのある検査がなく、未完了の証拠がこのコマンドの認定する1項目だけで、
    全チェックアウトのレポートがバイト列として一致することを求める。規模の検証の結果は求めない（ADR-076）。
    """
    errors = []
    if len(conformance) != CHECKOUTS:
        return [f"チェックアウトは{CHECKOUTS}つ必要です"]
    for index, result in enumerate(conformance, 1):
        try:
            report = json.loads(result["stdout"])
            failed = sorted(name for name, check in report["checks"].items() if check.get("errors"))
            pending = report["pending"]
        except (ValueError, KeyError, TypeError, AttributeError):
            errors.append(f"監査{index}: レポートの形式が不正です{stderr_tail(result)}")
            continue
        if failed:
            errors.append(f"監査{index}: エラーのある検査があります（{', '.join(failed)}）")
        if pending != [CERTIFIED]:
            errors.append(f"監査{index}: このコマンドで認定できない未完了の証拠があります")
        if result["exitCode"] != 1:
            errors.append(f"監査{index}: 終了コードが1ではありません")
    if len({result["stdout"] for result in conformance}) != 1:
        errors.append("監査のレポートがチェックアウト間でバイト一致しません")
    return errors


def version(argv):
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    return completed.stdout.strip() if completed.returncode == 0 else None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    uv = shutil.which("uv")
    errors = worktree_errors()
    if uv is None:
        errors.append("`uv`が見つかりません")
    head = git("rev-parse", "--verify", "HEAD")
    if head.returncode != 0:
        errors.append("`HEAD`のコミットがありません")
    commit = head.stdout.strip() or None
    conformance = []
    if not errors:
        try:
            with tempfile.TemporaryDirectory(prefix="bitz-gate-a-") as temporary:
                for index in range(CHECKOUTS):
                    directory = Path(temporary) / f"checkout{index}"
                    checkout(commit, directory)
                    # 監査はハングを止めるための上限で、合否の条件ではない。監査の自己試験が増え、遅い実行環境では
                    # 1回が600秒に近づいたので、上限を1800秒にする（中の自己試験の上限は1200秒。CIのGate Aのジョブは全体で30分の上限を持つ）。
                    conformance.append(run(uv, CONFORMANCE, directory, 1800))
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error).split("\n")[0])
        else:
            errors = judge(conformance)
    report = {
        "commit": commit,
        "gateA": "Allowed" if not errors else "Blocked",
        "certifies": CERTIFIED,
        "coreExecution": "Not run",
        "conformance": [{"exitCode": result["exitCode"], "reportSha256": sha256(result["stdout"])} for result in conformance],
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
