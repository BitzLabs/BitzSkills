#!/usr/bin/env python3
"""env-update stamp 後付け救済フロー（ENV-FR-012 / ENV-DSN-002）の合成フィクスチャ検証ハーネス。

SKILL.md 手順 1b（救済フロー）と env-doctor 診断項目4をエージェントが解釈実行する挙動を
機械的にモデル化し、以下4観点を確認する（本番の実行コードではなく検証用の使い捨てハーネス）:

  1. env-doctor が「レジストリ存在・bitz-env-version 不在」を WARN + 救済手順提示で検出すること
  2. 救済フロー承認時に D̂ stamp → 差分更新/マイグレーション → T stamp と進むこと
     （途中失敗時も D̂ が残り、再実行が救済フローを経ず正常系で収束すること）
  3. レジストリ不在時は env-init 案内で安全側停止すること
  4. env-doctor が読み取り専用であること（診断前後で入力不変）、
     救済フロー非承認時に一切書き込みが無いこと
"""
import copy
import re
import sys

STAMP_INTRO_VERSION = "0.7.0"  # stamp 機構導入版（ステップ不在時の保守的推定 D̂）


def parse_semver(v):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v.strip())
    if not m:
        raise ValueError(f"semver 解釈不能: {v!r}")
    return tuple(int(x) for x in m.groups())


def estimate_d(steps):
    """保守的推定 D̂ = migrations 最古ステップの from。ステップ不在時は stamp 機構導入版。"""
    if not steps:
        return STAMP_INTRO_VERSION, "ステップ不在 → stamp 機構導入版"
    oldest = min(steps, key=lambda s: parse_semver(s[0]))
    return oldest[0], "migrations 最古ステップの from"


def doctor_check(registry_exists, registry):
    """env-doctor 診断項目4。読み取り専用（registry を変更しない）。"""
    if not registry_exists:
        return "INFO", "レジストリ不在 = env-init 未実行 → env-init の実行を案内"
    if "bitz-env-version" not in registry:
        return ("WARN",
                "bitz-env-version 未記録（stamp 機構導入前の展開）"
                "→ 修正案: env-update の救済フロー（stamp 後付け。手順 1b）を実施")
    return "PASS", f"stamp あり（{registry['bitz-env-version']}）"


def apply_step(state, step):
    """guard 判定 → 未適用なら transform → verify（verify_migration.py と同一機構）。"""
    _from, _to, guard_key, (k, v), fail_verify = step
    if guard_key in state:
        return state, "NO-OP (guard 成立)", True
    ns = copy.deepcopy(state)
    ns[k] = v
    if fail_verify:  # verify 失敗の注入（途中失敗フィクスチャ用）
        return state, "VERIFY 失敗 → rollback して停止", False
    return ns, f"TRANSFORM 適用 ({k}={v})", True


def run_update(steps, registry_exists, registry, T, approve_rescue):
    """env-update 手順1〜5の骨子。戻り値: (status, レジストリ, ログ)"""
    log = []
    if not registry_exists:
        return ("SAFE_STOP_ENV_INIT", None,
                ["レジストリ不在 = env-init 未実行 → 救済対象外。env-init の実行を案内して停止"])
    state = copy.deepcopy(registry)
    D = state.get("bitz-env-version")
    if D is None:
        d_hat, basis = estimate_d(steps)
        log.append(f"救済フロー: D 未記録 → 保守的推定 D̂={d_hat}（{basis}）を提示")
        if not approve_rescue:
            return "SAFE_STOP_DECLINED", registry, log + ["承認なし → 一切書き込まず安全側停止"]
        state["bitz-env-version"] = d_hat  # 承認後の適用の最初に stamp
        log.append(f"承認 → 適用の最初にレジストリへ D̂={d_hat} を stamp")
        D = d_hat
    if parse_semver(D) >= parse_semver(T):
        return "NO_MIGRATION", state, log + [f"D={D} >= T={T}（更新不要）"]
    cand = sorted([s for s in steps if parse_semver(D) < parse_semver(s[1]) <= parse_semver(T)],
                  key=lambda s: parse_semver(s[1]))
    for s in cand:
        state, msg, ok = apply_step(state, s)
        log.append(f"step {s[0]}->{s[1]}: {msg}")
        if not ok:  # 途中失敗: stamp 済み D̂ は残る（再実行は正常系で収束）
            return "STEP_FAILED", state, log
    state["bitz-env-version"] = T  # 全ステップ成功後に T を stamp
    log.append(f"完了: レジストリを T={T} へ stamp")
    return "APPLIED", state, log


def show(title, status, log):
    print(f"\n[{title}]")
    for line in log:
        print(f"  {line}")
    print(f"  結果: {status}")


def main():
    print("=" * 70)
    print("フィクスチャ検証: stamp 後付け救済フロー（ENV-FR-012）")
    print("=" * 70)
    step_078 = ("0.7.0", "0.8.0", "migrated_080", ("migrated_080", True), False)
    unstamped = {"entries": ["advisor.md"], "markers": ["AGENTS.md#bitz-env"]}

    # ---- R1: env-doctor の WARN 検出（読み取り専用） ----
    reg = copy.deepcopy(unstamped)
    before = copy.deepcopy(reg)
    sev, msg = doctor_check(True, reg)
    show("R1 doctor: 未記録レジストリの検出", f"{sev} — {msg}", [])
    ok1 = (sev == "WARN" and "救済フロー" in msg and reg == before)
    print(f"  読み取り専用: {'不変' if reg == before else '変更!!'}")
    print(f"  判定: {'PASS' if ok1 else 'FAIL'} (WARN + 救済手順提示 + 入力不変)")

    # ---- R2: 救済フロー承認 → D̂ stamp → 適用 → T stamp ----
    st, after, log = run_update([step_078], True, copy.deepcopy(unstamped), "0.8.0", True)
    show("R2 救済承認: D̂=0.7.0 → step 適用 → T=0.8.0", st, log)
    ok2 = (st == "APPLIED" and after["bitz-env-version"] == "0.8.0"
           and after.get("migrated_080") is True)
    # 再実行: D>=T で更新不要（救済フローを経ない）
    st_re, after_re, log_re = run_update([step_078], True, after, "0.8.0", False)
    show("R2b 再実行: 収束確認", st_re, log_re)
    ok2 = ok2 and st_re == "NO_MIGRATION" and after_re == after
    # ステップ不在: D̂=導入版 → 差分更新のみ → T stamp
    st_e, after_e, log_e = run_update([], True, copy.deepcopy(unstamped), "0.8.0", True)
    show("R2c ステップ不在: D̂=0.7.0（導入版）→ 差分更新のみ", st_e, log_e)
    ok2 = ok2 and st_e == "APPLIED" and after_e["bitz-env-version"] == "0.8.0"
    # 途中失敗: D̂ が残り、再実行は救済フローなしで正常系
    step_fail = ("0.7.0", "0.8.0", "migrated_080", ("migrated_080", True), True)
    st_f, after_f, log_f = run_update([step_fail], True, copy.deepcopy(unstamped), "0.8.0", True)
    show("R2d 途中失敗: D̂ 残存の確認", st_f, log_f)
    st_f2, after_f2, log_f2 = run_update([step_078], True, after_f, "0.8.0", False)
    show("R2e 途中失敗後の再実行: 救済フローなしで収束", st_f2, log_f2)
    ok2 = (ok2 and st_f == "STEP_FAILED" and after_f["bitz-env-version"] == "0.7.0"
           and st_f2 == "APPLIED" and after_f2["bitz-env-version"] == "0.8.0"
           and not any("救済フロー" in line for line in log_f2))
    print(f"  判定: {'PASS' if ok2 else 'FAIL'} (承認→stamp→適用→T stamp、再実行・失敗時も収束)")

    # ---- R3: レジストリ不在 → env-init 案内で停止 ----
    st3, _, log3 = run_update([step_078], False, None, "0.8.0", True)
    show("R3 レジストリ不在: env-init 案内", st3, log3)
    ok3 = (st3 == "SAFE_STOP_ENV_INIT" and any("env-init" in line for line in log3))
    print(f"  判定: {'PASS' if ok3 else 'FAIL'} (救済対象外・env-init 案内で停止)")

    # ---- R4: 救済非承認 → 一切書き込み無し ----
    reg4 = copy.deepcopy(unstamped)
    before4 = copy.deepcopy(reg4)
    st4, after4, log4 = run_update([step_078], True, reg4, "0.8.0", False)
    show("R4 救済非承認: 書き込み無し", st4, log4)
    ok4 = (st4 == "SAFE_STOP_DECLINED" and after4 == before4)
    print(f"  レジストリ書き込み: {'無し（不変）' if after4 == before4 else '発生!!'}")
    print(f"  判定: {'PASS' if ok4 else 'FAIL'} (非承認時は不変のまま安全側停止)")

    print("\n" + "=" * 70)
    results = {"R1": ok1, "R2": ok2, "R3": ok3, "R4": ok4}
    print("総合: " + " / ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in results.items()))
    print("=" * 70)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
