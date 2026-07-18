<!--
  _scaling.md — 日本語6章を保ったまま、文書の密度を段階的に高める規約。
  各章で「docs/ に残す恒久方針」と「.spec/ が持つ契約・状態」を混同しないこと。
-->
# docs/ スケーリング規約（必須6章 + 宣言式の任意章）

## 正規構成

```
docs/
  MASTER.md                         索引・project_type・拡張宣言
  _conventions.md                   frontmatter・配置ルール
  _scaling.md                       このファイル
  00_はじめに/                      WHY・利用者・用語・スコープ・統制
  01_システム仕様/                  機能・非機能・制約の人間向け説明
  02_ユースケース/                  アクターとシステムの対話
  03_設計仕様/                      構造・API・データ・セキュリティ・ADR・実装規約
  04_テスト仕様/                    テスト戦略・品質ゲート
  05_リリース・運用/                リリース・SLO・runbook・postmortem・教訓
  06_リファレンス/                  外部API・CLI/SDK・移行ガイド（宣言時のみ）
```

必須6章は常に存在させる。任意章は `MASTER.md` の `optional_chapters: reference` と
実ディレクトリを同時に追加する。調査メモ・アーカイブは `excluded_paths` で管理外にできるが、
必須6章・任意章・MASTER・運用規約自身を除外してはならない。

## 章と機械areaの対応

文書IDを安定させるため、章とareaは1対1にしない。`docs_inspect.py` もこの表を検査する。

| 章 | 許容area | 主な内容 |
|---|---|---|
| `00_はじめに` | `context`, `governance` | ビジョン、スコープ、用語、指標、ペルソナ、統制 |
| `01_システム仕様` | `system` | 機能・非機能・制約の索引 |
| `02_ユースケース` | `usecase` | UC索引、基本・代替フロー |
| `03_設計仕様` | `design`, `implementation` | architecture、API、data、security、patterns、ADR |
| `04_テスト仕様` | `quality` | テスト戦略、greenの定義、品質ゲート |
| `05_リリース・運用` | `operations`, `knowledge` | release、SLO、runbook、postmortem、教訓 |
| `06_リファレンス` | `reference` | 外部参照、CLI/SDK、移行ガイド |

## docs ⇄ .spec の境界

> **フィーチャごとに変わる契約・状態は `.spec/`。フィーチャを越えて残る意図・方針は `docs/`。**

| 章 | `docs/`（恒久・方針・WHY） | `.spec/`（契約・実行・状態） |
|---|---|---|
| 00 | ビジョン、用語、スコープ理由、ガバナンス | discovery成果物、ROADMAP、STATE |
| 01 | 機能・品質・制約の人間向け全体像 | EARS要件、version、status |
| 02 | 利用シナリオのナラティブ | UCマスター、要件トレース、検証入力 |
| 03 | 構造、境界、採用理由、恒久実装規約 | design成果物、タスク、依存グラフ |
| 04 | テスト戦略、品質ゲートの意味 | verification_method、test-spec、実行結果 |
| 05 | 再現可能な運用・リリース方針、恒久的教訓 | リリース回ごとの状態、障害調査の作業記録 |
| 06 | 利用者向け参照資料 | 参照資料の生成元となる契約 |

同じ事実が両方に出たら、**意図はdocs、検証可能な契約と状態は.specが勝つ**。

## 段階拡張のトリガー

| 追加する文書 | 追加の合図 |
|---|---|
| 成功指標・ペルソナ・ポジショニング | sdd-discoveryで上流探索を行う |
| 個別ユースケース | 標準UCフローを採用し、要件・テストへ追跡する |
| 実装パターン | 同じパターンが複数featureで反復する |
| 詳細テスト方針 | 品質ゲートをfeature横断で共有する |
| runbook / SLO / support matrix | 定期運用・公開を再現可能にする必要がある |
| `06_リファレンス` | 外部API、CLI/SDK、破壊的変更の移行ガイドが増える |

## app / library での重みの違い

- **app**: `05_リリース・運用` が厚くなる。公開API文書は任意。
- **library**: `03_設計仕様/公開API.md` は必須。互換性、support matrix、移行ガイドが中核。
- **both**: appの運用面とlibraryの公開契約面を両方維持する。
