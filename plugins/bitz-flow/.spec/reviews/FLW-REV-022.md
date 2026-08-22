---
id: FLW-REV-022
title: "approval-mode 宣言の観測可能な再照合と安全な束縛の再レビュー"
status: active
version: 1.0
updated: 2026-08-22
owner: codex
decision: PASS
---

# 設計レビュー統合レポート — approval-mode 再設計

- **review_id**: FLW-REV-022
- **対象**: FLW-NFR-014 v1.1、FLW-DSN-017 v1.2
- **判定**: **PASS（設計品質）**
- **集計スコア**: **4.28 / 5.00**（PASS ≥ 3.5）
- **Design Gate**: **通過承認済み**。2026-08-22にuserが本レビューを根拠として通過を承認。

## 観点別スコア

| 観点 | スコア | 重み | 新規所見 |
|---|---:|---:|---|
| consistency | 5.00 | 0.15 | なし |
| data-integrity | 4.00 | 0.25 | なし |
| operations | 4.00 | 0.20 | なし |
| risk | 4.00 | 0.25 | なし |
| business | 4.85 | 0.15 | なし |

findings: 統合前 0 件 → 重複排除後 0 件（P0: 0 / P1: 0 / P2: 0 / P3: 0）

## 再設計で確立した境界

- HEAD・index・worktreeの三者すべてが不在の場合だけ`absent`とする。
- 成功した最終再照合を観測可能な承認線形化点とし、非観測履歴を検出済みと主張しない。
- common-dirのOS lock、namespace manifest、durable fencing状態機械で別CLIとcrash後を収束させる。
- `MutationGuardian`がLinux・macOS・WindowsでGit child終了までleaseを保持する。
- capability v2、実体JSON Schema境界、SLI/runbook成果物を実装タスクへ分離する。
- sentinel-aware baselineを全起動経路で証明するpromotion barrierの後だけcontract v2 stateを生成する。

## 監査上の未解消事項

再レビューでは新規findingがなく設計品質をPASSとした。2026-08-22の人間裁定により
`SI-FLW-078/079`、後継要件、`FLW-REV-021`の対象findingを解消済みとして反映した。
`FLW-REV-022.json`は本件外の過去レビュー由来P0/P1を`carried_over`へ保持する。
本レビューを根拠に`FLW-GATE-004`でDesign Gateを通過し、実装タスク再分解へ進む。

## 人間への裁定依頼（消化済み）

1. `SI-FLW-078`で案B（観測可能checkpoint契約）をacceptする。
2. `SI-FLW-079`の要件系譜訂正をacceptする。
3. 後継要件`FLW-NFR-014`をapprovedとする。
4. 上記裁定後に`FLW-NFR-013`の後継接続と前回findingの監査状態を更新し、Design Gateを裁定する。

## 人間裁定

- **裁定日**: 2026-08-22
- **裁定者**: user
- **決定**: 提案された4項目を承認する。`SI-FLW-078`は推薦案Bを採用し、`SI-FLW-079`をaccept、
  `FLW-NFR-014`をapproved、`FLW-NFR-013`をdeprecatedとして`FLW-NFR-014`へ後継接続する。
- **範囲**: 本裁定は要件・spec-issue・後継接続の承認であり、Design Gate通過および実装着手は別途扱う。

### Design Gate裁定

- **裁定日**: 2026-08-22
- **裁定者**: user
- **決定**: `FLW-NFR-014`、`FLW-DSN-017`、`FLW-REV-022`を対象とするDesign Gate通過を承認。
- **根拠**: 統合レビューPASS 4.28、新規finding 0件、本件の`FLW-REV-021` finding全件resolved、
  `spec_inspect`および`release_check.py`終了コード0。
