---
name: sdd-discovery
description: BitzSDD の上流探索（ディスカバリー）を行うスキル。プロダクトビジョン（Vision Board / PR-FAQ）・成功指標（North Star Metric）・スコープ（MoSCoW / RICE）・ペルソナとジャーニー（JTBD）・ポジショニングを順に確立し、仮説検証ゲート（Go / No-Go）で設計着手可否を裁定する。成果物は docs/01-context/ の proposed ドラフトと .planning/discovery/ の作業成果物。「何を作るか決めたい」「ビジョンを言語化したい」「ペルソナを作って」「ジャーニーマップ」「スコープを切りたい」「作る価値があるか検証したい」と言われたとき、または bitz-sdd の Map/Discuss フェーズで docs/01-context/ の中身が未確立のときに使用する。設計は sdd-design、要件化（EARS・採番）は bitz-sdd の管轄。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-08"
---

# SDD Discovery — 上流探索

docs/01-context/ 層のコンテンツ（なぜ作るか・誰のためか・何をやらないか）を人間と協働で確立する。検証駆動: もっともらしい戦略を**反証可能な賭けの集合**に変換し、Discovery Gate で設計着手可否を裁定してから先に進む。

## 前提

- docs/ が初期化済みであること（未整備なら先に `sdd-docs` で初期化する）
- 作業台帳は assets/discovery-worksheet.md をコピーして `.planning/discovery/worksheet.md` として使う

## 絶対規則

- docs/ に書けるのは `status: proposed` のドラフトのみ。active 文書は書き換えない
- 要件（FR/NFR/CON）の採番はしない。制約・非目標は docs/ のドラフトに書き、要件化は Design Gate 後の bitz-sdd の派生に委ねる
- **事実をでっち上げない**: 根拠のないターゲット数値・ペルソナの感情・競合情報は `TBD` または `[proto / 未検証]` と明示する
- 手法の作業成果物（仮説表・RICE 採点・競合マトリクス）は `.planning/discovery/` に置き、人間向けの結論だけを docs/ ドラフトに落とす

## ワークフロー（6ステップ）

各ステップで対応する reference を読んでから、対話的に確立する。全ステップ必須ではない — 既に人間が持っている答えは確認して記録するだけでよい:

| # | ステップ | 読むファイル | 成果物（結論の行き先） |
|---|---|---|---|
| 1 | ビジョン（Vision Board + PR-FAQ 圧力試験） | references/vision.md | docs/01-context/mission-vision.md（proposed 更新） |
| 2 | 成功指標（NSM + 入力指標 + ガードレール） | references/success-metrics.md | docs/01-context/success-metrics.md（新規 proposed、テンプレは assets/） |
| 3 | スコープ（制約 → Kano → RICE → MoSCoW → In/Out 境界） | references/scope.md | non-goals.md / constraints.md（proposed 更新）+ 作業表は .planning/discovery/ |
| 4 | ペルソナとジャーニー（JTBD → ペルソナカード → 段階×レイヤー） | references/personas-journeys.md | docs/01-context/personas-journeys.md（新規 proposed、テンプレは assets/） |
| 5 | ポジショニング（競合代替 → PoD/PoP → ステートメント） | references/positioning.md | docs/01-context/positioning.md（新規 proposed、テンプレは assets/） |
| 6 | 仮説検証ゲート（分類 → 崩壊影響ランク → テスト+閾値 → Go/No-Go） | references/assumption-gate.md | .planning/discovery/assumptions.md + ゲート判定 |

新規 proposed 文書を作ったら、MASTER.md の文書レジストリに行を追記する（status: proposed）。

## Discovery Gate（人間裁定）

ステップ6の判定材料（仮説一覧・テスト結果・未検証の崩壊クリティカル仮説）を揃えて人間に提示する:

- **Go** — 崩壊クリティカルな仮説がすべて「検証済み」または「テスト+事前閾値が定義済み」。docs/01-context/ ドラフトの active 化を依頼し、`sdd-design` へ進む
- **No-Go / Pivot** — 崩壊クリティカルな仮説が未検証かつテスト未定義。設計に進まず、ビジョン/スコープへ戻る

判定は推奨であり、裁定・active 化は人間が行う。エビデンスが増えたらゲートは再訪してよい。

## 連携

- docs/ の初期化・構造検証は `sdd-docs`、設計工程は `sdd-design`、レビューは `sdd-review`、要件・ゲート運用は `bitz-sdd`

## 出典

本スキルの手法群は [nexus-architect](https://github.com/wfukatsu/nexus-architect)（MIT License, Copyright (c) 2026 Wataru Fukatsu）の product プラグイン（define-vision / define-success-metrics / define-scope / generate-persona / map-journey / design-positioning / validate-assumptions と対応 rules）から翻案・圧縮したもの。
