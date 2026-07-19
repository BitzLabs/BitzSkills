#!/usr/bin/env python3
"""env-update マイグレーション機構の合成フィクスチャ検証ハーネス。

CORE-CON-009 / DSN-002 / migration-steps.md の機構を決定的に再現し、
以下2挙動を確認する（宣言的 Markdown ステップをエージェントが解釈実行する挙動を
機械的にモデル化したもの。本番の実行コードではなく検証用の使い捨てハーネス）:

  1. チェーン断裂時の安全側停止（書き込みが起きないこと）
  2. 同一ステップ二重適用の no-op（guard による冪等性）
"""
import re, sys, copy

def parse_semver(v):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v.strip())
    if not m:
        raise ValueError(f"semver 解釈不能: {v!r}")
    return tuple(int(x) for x in m.groups())

def resolve_chain(steps, D, T):
    """steps: [(from,to,guard_key,transform_kv)]。戻り値: (status, 適用順ステップ, 理由)"""
    try:
        d, t = parse_semver(D), parse_semver(T)
    except ValueError as e:
        return ("SAFE_STOP", [], f"semver 解釈不能: {e}")
    if d >= t:
        return ("NO_MIGRATION", [], "D >= T（更新不要）")
    # to 昇順ソート、適用候補 D < to <= T
    cand = sorted(
        [s for s in steps if d < parse_semver(s[1]) <= t],
        key=lambda s: parse_semver(s[1]))
    if not cand:
        return ("NO_MIGRATION", [], "適用候補が空（形式変更なし）")
    # 連続性検査: D が最古候補の from より古く接続無し → GAP
    if parse_semver(cand[0][0]) > d:
        return ("SAFE_STOP", [], f"GAP: D={D} が最古候補の from={cand[0][0]} より古く接続ステップ無し")
    for i in range(len(cand) - 1):
        if parse_semver(cand[i][1]) != parse_semver(cand[i+1][0]):
            return ("SAFE_STOP", [],
                    f"GAP: チェーン断裂 step[{i}].to={cand[i][1]} != step[{i+1}].from={cand[i+1][0]}")
    return ("APPLY", cand, "連続性 PASS")

def apply_step(state, step):
    """guard 判定 → 未適用なら transform → verify。冪等性の核。"""
    _from, _to, guard_key, (k, v) = step
    if guard_key in state:              # guard 成立 → 適用済み → no-op
        return state, "NO-OP (guard 成立)"
    ns = copy.deepcopy(state)
    ns[k] = v                           # transform
    assert k in ns                      # verify
    return ns, f"TRANSFORM 適用 ({k}={v})"

def run_update(steps, registry, T):
    """registry: dict（frontmatter 模擬。bitz-env-version=D を含む）"""
    D = registry.get("bitz-env-version")
    if D is None:
        return "SAFE_STOP", registry, "D 未記録（bitz-env-version 不在）→ 移行基準確定不能"
    status, chain, reason = resolve_chain(steps, D, T)
    if status != "APPLY":
        # SAFE_STOP / NO_MIGRATION いずれも書き込み無しでレジストリ不変
        return status, registry, reason
    state = copy.deepcopy(registry)
    log = []
    for s in chain:
        state, msg = apply_step(state, s)
        log.append(f"  step {s[0]}->{s[1]}: {msg}")
    state["bitz-env-version"] = T       # 全ステップ成功後に stamp
    return "APPLIED", state, "\n".join(log)


def main():
    print("=" * 70)
    print("フィクスチャ検証: env-update マイグレーション機構")
    print("=" * 70)

    # ---- Fixture 1: チェーン断裂 → 安全側停止（書き込み無し） ----
    print("\n[Fixture 1] チェーン断裂時の安全側停止")
    steps_broken = [
        ("0.6.0", "0.7.0", "migrated_070", ("migrated_070", True)),
        # 0.7.0-to-0.8.0 を意図的に欠落
        ("0.8.0", "0.9.0", "migrated_090", ("migrated_090", True)),
    ]
    reg1 = {"bitz-env-version": "0.6.0", "entries": ["advisor.md"]}
    reg1_before = copy.deepcopy(reg1)
    status, reg1_after, reason = run_update(steps_broken, reg1, "0.9.0")
    print(f"  ステップ: 0.6.0->0.7.0, (欠落), 0.8.0->0.9.0 / D=0.6.0 T=0.9.0")
    print(f"  結果: {status} — {reason}")
    print(f"  レジストリ書き込み: {'無し（不変）' if reg1_after == reg1_before else '発生!!'}")
    ok1 = (status == "SAFE_STOP" and reg1_after == reg1_before)
    print(f"  判定: {'PASS' if ok1 else 'FAIL'} (安全側停止かつ書き込み無し)")

    # ---- Fixture 2: 同一ステップ二重適用 → guard で no-op ----
    print("\n[Fixture 2] 同一ステップ二重適用の no-op（冪等性）")
    steps_ok = [("0.6.0", "0.7.0", "migrated_070", ("migrated_070", True))]
    reg2 = {"bitz-env-version": "0.6.0", "entries": ["advisor.md"]}

    # 1回目: guard 未成立 → transform 適用
    st1, reg2_1, log1 = run_update(steps_ok, reg2, "0.7.0")
    print(f"  1回目: {st1}\n{log1}")
    print(f"    → {reg2_1}")

    # 2回目: D は 0.7.0 に stamp 済み。同一 T=0.7.0 で再実行 → D>=T で NO_MIGRATION（更新不要）
    st2, reg2_2, reason2 = run_update(steps_ok, reg2_1, "0.7.0")
    print(f"  2回目(再実行): {st2} — {reason2}")
    print(f"    → {reg2_2}")

    # 追加確認: 途中失敗を模し D=0.6.0 のまま状態には migrated_070 が既にあるケース
    #           （擬似トランザクション: stamp 前に落ちた後の再走）を直接 apply で確認
    partial = {"bitz-env-version": "0.6.0", "entries": ["advisor.md"], "migrated_070": True}
    reapplied, msg = apply_step(partial, steps_ok[0])
    print(f"  再走時(適用済み状態への同一ステップ): {msg}")
    print(f"    → 状態不変: {reapplied == partial}")

    ok2 = (st1 == "APPLIED" and reg2_1.get("migrated_070") is True
           and reg2_1["bitz-env-version"] == "0.7.0"
           and st2 == "NO_MIGRATION" and reg2_2 == reg2_1
           and reapplied == partial)
    print(f"  判定: {'PASS' if ok2 else 'FAIL'} (二重適用で状態不変・guard で no-op)")

    print("\n" + "=" * 70)
    print(f"総合: Fixture1={'PASS' if ok1 else 'FAIL'} / Fixture2={'PASS' if ok2 else 'FAIL'}")
    print("=" * 70)
    return 0 if (ok1 and ok2) else 1

if __name__ == "__main__":
    sys.exit(main())
