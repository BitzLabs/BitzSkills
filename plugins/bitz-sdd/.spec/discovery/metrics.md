---
id: SDD-DSC-002
title: "bitz-sdd 成功指標（North Star Metric + 入力指標 + ガードレール）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# 成功指標 — bitz-sdd

> 遡及的 discovery。目標値の多くは計測基盤が未整備のため `TBD`。
> でっち上げず、定義・測定方法・ガードレールの枠組みを先に確立する。

## North Star Metric（NSM）— 1つ

**検証済み（verified/done）まで到達した SDD フィーチャー／ワークスペースの数**
（＝ discovery→設計→実装→検証まで規律を通しきった単位数）。

- **なぜこれか**: bitz-sdd が届ける中核価値は「規律を通しきること」。単なる導入数や
  スキル発動数（バニティ）ではなく、**要件が検証で裏づけられた状態に到達した回数**が
  顧客の受け取った価値を捉える。
- **収益に先行**: 非収益 OSS のため収益は対象外。代わりに「規律の定着＝継続利用・外部採用」
  の先行指標として機能する。
- **顧客が動かせる**: エージェント＋開発者の実作業（要件承認・実装・検証）で直接引ける。
- **測定方法**: `spec_inspect.py` のカバレッジ集計 / `sdd_report.py` の status 集計から
  `verified` / `done` 件数を数える。ワークスペース横断は `--workspace` 解決で合算。

## 入力指標（3〜5個）— 広さ × 深さ × 頻度 × 効率

| # | 指標 | レバー（次元） | 定義 / 測定 | 目標値 | ガードレール |
|---|---|---|---|---|---|
| I1 | discovery を起票したワークスペース数 | 広さ | `.spec/discovery/` を持つ WS 数 | `TBD` | — |
| I2 | approved まで到達した要件数 | 深さ | status=approved 以上の要件件数（`spec_inspect`） | `TBD` | 未検証 approved の滞留を増やさない |
| I3 | 要件→テストのトレース率 | 効率 | verification_method を持ち検証に紐づく要件の割合 | 100% を志向 | カバレッジ偽装（空テスト）を作らない |
| I4 | ドッグフーディング利用頻度 | 頻度 | 本人が bitz-sdd スキルを起動した週次回数 | `TBD` | 惰性利用でなく実タスクに紐づくこと |
| I5 | 機械検証（release_check / spec_inspect）成功率 | 効率 | CI/ローカルでの PASS 率 | 高位安定 | 誤検知で開発を止めない |

> レンズ: **AARRR** を採る（Activation = 最初の `.spec/` 起票、Retention = 継続的な
> verified 到達）。個人開発＋OSS のため Referral/Revenue は当面 `TBD`。

## ガードレール指標（NSM 最適化中に劣化させない対抗指標）

- **誤検知率**: `spec_inspect.py` / `release_check.py` の偽陽性が増えないこと
  （規律を増やすほど検証が邪魔になる罠を防ぐ。目標 `TBD`、実測基盤は未整備）。
- **スキル本文の肥大化**: SKILL.md 本文が薄く保たれること（3段階読み込み方針 SI-CORE-013 と対応。
  肥大化はトークンコスト＝顧客負担の劣化）。
- **同期の齟齬**: `.spec/` ⇄ `docs/` の `sdd_sync.py diff` が未解消ドリフトを残さないこと。
- **オンボーディング摩擦**: OSS 利用者が最初の成果物到達までに離脱しないこと = `[proto / 未検証]`。

## 下流への接続

- ガードレール（誤検知率・本文サイズ・同期齟齬）は Design Gate 後に NFR
  （verification_method: benchmark / example-test、数値は検証可能な形で明示）へ派生する候補。
- 計測基盤（実測値の収集）自体が未整備であり、目標値の `TBD` 解消は別 issue の対象。

## Open Questions
- NSM/入力指標の実測を自動収集する仕組み（`sdd_report.py` 拡張か observations ログ活用か）— `TBD`。
- OSS 採用の観測手段（marketplace 導入数の可視化可否）— `TBD`。
