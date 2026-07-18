<!--
  _conventions.md — HOW docs/ works. Not a project document itself; it governs the others.
  Keep this in sync with ADR-template.md and the .spec/requirements/ registry (sdd-core skill).
-->
# docs/ 運用規約 (Conventions)

このツリー (`docs/`) は **人間ナラティブ / 遅く変わる意図 (WHY と人間向け WHAT)** を持つ。
実行状態・検証可能な契約は持たない。それらは `.spec/` の責務。

## 責務の非重複（どちらが真実か）

| 事実の種類 | 真実の在り処 |
|---|---|
| 意図・背景・なぜ (WHY) | `docs/` |
| 人間向けの WHAT（何を作るか／何を作らないか） | `docs/` |
| 恒久的な知見・決定の履歴 | `docs/`（教訓 / ADR） |
| 検証可能な受入基準 (EARS) ・契約 | `.spec/requirements/`（1要件1ファイル） |
| 実行状態・タスク・進捗 | `.spec/`（STATE.md 等） |

同じ事実が両方にあったら、**意図は `docs/`、契約と状態は `.spec/` が勝つ**。

## 派生方向は一方向

```
docs/（人が書く意図・遅い） ──derive──▶ .spec/（生成される契約・速い）
        ▲                                              │
        └──────────── promotion gate（閉じ戻し）────────┘
```

エージェントは `docs/` へ書き込まない。フィーチャ完了時のみ、`.spec/STATE.md` の
durable な学びを `docs/05_リリース・運用/教訓.md` と ADR に**人間承認で昇格**させる。

## 共通 frontmatter

すべての `docs/` 文書は先頭に以下を持つ。

```yaml
---
id: DOC-<area>-<slug>      # 例: DOC-context-mission。ツリー内で一意
title: <人が読むタイトル>
status: active             # proposed | active | deprecated | superseded
version: 0.1.0             # SemVer。changeImpact に応じて bump
changeImpact: low          # low | medium | high
project_type: app          # app | library | both
updated: 2026-07-07        # ISO 8601
owner: <担当ハンドル>
superseded_by: null        # status: superseded のとき DOC-... を必須
---
```

### status（文書ライフサイクル）

- `proposed` … 起票済み・未合意
- `active` … 現行の真実
- `deprecated` … 採用したが役目を終えた（履歴として残す）
- `superseded` … 別文書に置換された。`superseded_by` 必須

一度も採用しなかった案はここには使わない。不採用案は要件として起票せず、
ADR の "Considered Options" に理由付きで記録する。

### changeImpact → version bump ポリシー（FeelFlow 由来）

| changeImpact | bump | 付随して必要なこと |
|---|---|---|
| `low` | patch (0.1.**0**→0.1.1) | なし |
| `medium` | minor (0.**1**.0→0.2.0) | CHANGELOG に1行 |
| `high` | major (**0**.1.0→1.0.0) | CHANGELOG + 文末の Revision History 追記 + レビュー |

> **library の場合の注意**: ここでの version は「**文書の**版」であって、
> 出荷するパッケージの SemVer とは別物。パッケージの互換性は
> `03_設計仕様/公開API.md` が管理する。混同しないこと。

## 配置決定（Decision Matrix）

新しい情報をどこに置くか迷ったら、上から順に answer:

1. **検証可能な契約 / 実行状態か？** → Yes: `.spec/` へ。No: 2へ
2. **決定の理由・不採用案・試行錯誤か？** → Yes: `03_設計仕様/意思決定/ADR-*.md`
3. **恒久的な学び（再発防止・教訓）か？** → Yes: `05_リリース・運用/教訓.md`
4. **背景・目的・用語・スコープ境界か？** → Yes: `00_はじめに/`
5. **機能・非機能・制約の人間向け説明か？** → Yes: `01_システム仕様/`
6. **利用者とシステムの対話か？** → Yes: `02_ユースケース/`
7. **構造・境界・技術設計か？** → Yes: `03_設計仕様/`（library は `公開API.md` も）
8. **検証方針か？** → Yes: `04_テスト仕様/`
9. **リリース・運用・振り返りか？** → Yes: `05_リリース・運用/`
10. **参照資料か？** → Yes: 宣言済みの場合のみ `06_リファレンス/`
11. どれでもない → 置く前に MASTER.md の索引設計を見直す（増やしすぎない）

## 命名

- 人間向けファイル名と章名は日本語を基本とし、型名・API名・略語は原語を維持する。
- ADR は `意思決定/ADR-NNNN-<slug>.md`（4桁ゼロ埋め連番）。
- `id`、frontmatterキー、statusなどの機械値は英語を維持する。
- 章と許容areaは `_scaling.md` の対応表を正とする。
