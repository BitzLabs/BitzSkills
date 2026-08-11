---
id: FLW-REV-008
title: "M1開始前4 spec-issue統合レビュー"
status: pending
version: 1.0
updated: 2026-08-11
owner: codex
decision: FAIL
---

# 設計レビュー統合レポート — M1開始前4 spec-issue

- **review_id**: FLW-REV-008
- **対象**: SI-FLW-006、SI-FLW-029、SI-FLW-037、SI-FLW-038と関連要件・設計・ROADMAP
- **判定**: **FAIL**
- **集計スコア**: 2.50
- **非適用**: data-integrity（永続ドメインデータを扱わない）

## 観点別スコア

| 観点 | スコア | 正規化後の重み | 主要所見 |
|---|---:|---:|---|
| consistency | 2.00 | 0.20 | M1横断要件、裁定順、verified要件改訂手順が不足 |
| operations | 3.30 | 0.27 | qualification入口、証跡互換、raw log運用が不足 |
| risk | 2.00 | 0.33 | blind retry、危険NEXT、commit誤帰属、候補選別がP0 |
| business | 2.75 | 0.20 | 定量Gateと追加予算の根拠が不足 |

findings: 統合前17件 → 重複排除後8件（P0: 4 / P1: 4 / P2: 0 / P3: 0）

## P0 — Blocker

- **FLW-REV-008:SYN-002**: write出力上限超過後のblind retry（追跡: SI-FLW-006）
- **FLW-REV-008:SYN-003**: 失敗時NEXTから危険なwrite再実行への連鎖（追跡: SI-FLW-029）
- **FLW-REV-008:SYN-004**: 証跡再利用のTOCTOUと結果選択バイアス（追跡: SI-FLW-038）
- **FLW-REV-008:SYN-005**: commit成功のapply因果誤帰属（追跡: FLW-REV-008:GP-001）

## P1 — Must Fix

- M1横断のqualification・証跡要件と裁定順を固定する（SI-FLW-037）。
- write評価raw logの秘密値運用をqualificationへ含める（SI-FLW-037）。
- qualificationの定量Gateとevidence合成の独立予算を裁定する（SI-FLW-037）。
- verified FLW-FR-004を直接改訂せず、独立FRまたは再承認・再検証手順を採る（SI-FLW-029）。

## 持ち越し

FLW-REV-006の未解決P0/P1 9件を`carried_over[]`に保持した。

## 人間への裁定依頼

4件の問題意識とaccept方向は妥当だが、現案のままacceptedへ遷移してM1を開始することは推奨しない。
本レビューのP0/P1を各spec-issueへ取り込み、M1横断要件・REC-COMMIT因果証跡・定量予算を補強した後に
再レビューする。したがって今回の裁定は**accept保留、M1 Design Gate不通過**を推奨する。
