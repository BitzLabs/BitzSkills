---
id: QLT-DSN-002
title: "レビュー基盤 公開API・成果物schema"
status: active
version: 1.0
updated: 2026-08-14
owner: br7.hide
implements: [QLT-FR-018, QLT-FR-019, QLT-FR-020, QLT-FR-021, QLT-FR-022, QLT-FR-023, QLT-FR-024, QLT-FR-027, QLT-FR-028]
---

# 公開API・成果物schema

## CLI契約（v1）

```text
quality_review.py plan <target> --profile <id> --format compact|json
quality_review.py run --manifest <path> --adapter <id>
quality_review.py validate <artifact> --format compact|json
quality_review.py synthesize --manifest <path> --results <dir>
quality_review.py import-sdd-review <legacy-path>
quality_review.py compare --legacy <path> --candidate <path>
```

全CLIは未知引数を非ゼロ終了し、通常出力に秘密値やLLM raw logを含めない。

`plan`はtarget/profileを受けてmanifestを生成し、`run`はmanifestのみを入力にする。
`validate`はschema不正をexit code 1、`synthesize`は未検証resultを入力拒否する。

## Schema catalog

| Schema ID | 主な必須field |
|---|---|
| `quality-review/profile@1` | id, version, perspectives, gates, digest |
| `quality-review/invocation@1` | review_id, target, scope, profile_digest, reviewers, attempt, timeout/quotas, canonicalization, input_digest, timestamps |
| `quality-review/individual-result@1` | reviewer_id, attempt, status, target_digest, findings, evidence, timestamps |
| `quality-review/synthesis@1` | review_id, generation, inputs, verdict, findings, gate_preconditions, carried_over, commit_digest |
| `quality-result@1` | target_sha, status, synthesis_digest, tool/profile/schema versions, evidence_digest |
| `quality-review/qualification@1` | platform, adapter, compatibility_key, trials, measurement_plan, decision, evidence_id |
| `quality-review/run-history@1` | run_id, actor, timestamps, status, tool/profile/schema versions, retention_class |

Schemaはversionごとの閉集合とし、未知fieldは将来互換として黙認せず該当versionではINVALIDにする。
JSON objectのrequired、primitive type、enum、配列のmin/maxItems、ID pattern、digest formatを
各schema catalogに付属するvalidator contractで固定し、追加fieldはschema version bumpなしに許可しない。

## status / exit code

| status | 意味 | consumerへの既定写像 |
|---|---|---|
| PASS | profileのGate条件を満たす | 判定材料として受理可能 |
| CONDITIONAL_PASS | 条件付き | 人間Gateへagenda付きで提示 |
| FAIL | 品質条件未達 | reject/block候補 |
| BLOCKED | 実行・契約前提が不足 | 安全側停止 |
| STALE | target/profileが変化 | 再plan必須 |
| INVALID | schema/参照/不変条件違反 | 成果物不受理 |
| UNKNOWN | 判定材料不足 | 推測禁止 |

exit codeは`0=PASS/valid`、`1=FAIL/invalid`、`2=BLOCKED/STALE/UNKNOWN`、`3=usage`に固定する。

## Consumer contract

- bitz-sddは`quality-result@1`を読み、canonical ReviewFinding/GatePreconditionへ変換する。
- bitz-flowはtarget SHA一致を確認してPR check/enforceへ使う。
- どちらのadapterもqualityから外部statusや副作用を実行させない。
- project overrideの正は`.spec/quality/review/`とし、profileのbase/override digestとownerをmanifestへ記録する。
