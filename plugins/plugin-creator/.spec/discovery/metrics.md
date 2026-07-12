---
id: PLG-DSC-002
title: "plugin-creator 成功指標（North Star Metric + 入力指標 + ガードレール）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# 成功指標 — plugin-creator

> 遡及的ディスカバリー。目標値は実測基盤がないものは `TBD` とし発明しない。主ユーザーは開発者本人（hide）＋将来の OSS 利用者。

## North Star Metric（NSM）— 1つ

**「両対応で動く状態のまま出荷されたプラグイン数」**
（= plugin-creator の支援を受けて作られ、Claude Code / Antigravity 2.0 の少なくとも意図した対象で、配置ミスなく発見・動作した状態に到達したプラグインの累計）

- **収益に先行するか**: 該当（OSS のため収益は非目標）。この指標が伸びることは「両対応プラグインが正しく作れる」というビジョン達成の先行指標
- **顧客の価値を顧客の言葉で**: 「作りたいプラグインが、調べ直しなしで、動く状態で出せた」を捉える
- **チームが動かせるか**: ガイドの正確さ・検証カバレッジ・雛形品質という plugin-creator 自身のレバーで動かせる
- アンチパターン回避: スキルの生 install 数や PV ではなく「動く状態で出荷された成果物」を数える

## 入力指標（3〜5個）— 広さ × 深さ × 効率

| # | 指標 | 定義 | 測定方法 / ソース | 目標値 | ガードレール |
|---|---|---|---|---|---|
| 1 | ガイド発動の適合率（深さ） | ユーザーのプラグイン開発意図に対し、正しいコンポーネントスキルが発動した割合 | skill-observer 観察ログ（`evals/observations/`）の partial/fail 集計 | `TBD` | 誤発動・過剰発動を増やさない |
| 2 | 検証通過率（効率） | plugin-validator / release_check.py が初回検証で構造・マニフェスト整合を通した割合 | `release_check.py` 実行結果、plugin-validator レポート | `TBD` | 検証を緩めて通過率を水増ししない |
| 3 | 両対応カバレッジ（広さ） | 7コンポーネント領域のうち Claude Code / Antigravity 双方の仕様差を明記できている領域数 | 各スキル SKILL.md / references の内容点検 | 7/7 領域で両対応言及 | 片側だけの記述に退行させない |
| 4 | 一次情報の鮮度 | Antigravity 仕様記述が `docs/調査報告/01.Antigravity/` の実測と整合している度合い | 調査報告との突き合わせレビュー | 乖離ゼロ | Gemini 生成解説を混入させない |

## マッピング枠組み（レンズ: HEART）

UX 中心の開発者ツールのため HEART を採用。

- **Adoption**: 新規に plugin-creator 経由で着手されたプラグイン数（NSM の広さ側）
- **Task success**: 検証通過率（入力指標2）と発動適合率（入力指標1）
- **Happiness**: 「調べ直し不要だった」の主観評価 — 計測手段未整備のため `TBD` / `[proto / 未検証]`
- Engagement / Retention は個人内製主体のため当面重視しない

## ガードレール指標（NSM 最適化で劣化させない対抗指標）

- **責務境界の維持**: skill-creator が正であるスキル作成・検証・配置の実作業を plugin-creator に肩代わりさせない（越境をゼロに保つ）
- **スキル本文の軽さ**: progressive disclosure を崩さない（SKILL.md 本文の肥大化を避け、詳細は references/ へ）
- **保守負荷**: 両対応維持のためのガイド更新が、リリース速度を著しく落とさないこと（`TBD`）

## 下流への接続

- 検証通過率・両対応カバレッジは、Design Gate 後に NFR（`verification_method: inspection` / release_check）へ派生する第一候補
- 目標値 `TBD` は Open Questions として残し、計測基盤（観察ログの蓄積）が整い次第、検証可能な形（母集団・期間の明示）で埋める
