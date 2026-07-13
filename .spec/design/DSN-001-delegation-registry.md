---
id: DSN-001
title: 委譲レジストリ機構の設計（相対選択・プラットフォーム別・機械検証）
implements: [CORE-FR-006, CORE-FR-007, CORE-FR-008, CORE-FR-009, CORE-NFR-001, CORE-CON-007]
origin: SI-CORE-021
status: active
---

## 1. 目的

SDD の Execute フェーズに委譲ゲートを設け、司令塔（起動モデル）が機械的作業まで直接実行して
トークンを浪費する構造を是正する。モデル世代交代で陳腐化しないよう、モデル束縛を単一の情報源
（レジストリ）に寄せ、機械検証で整合を保つ。

## 2. 核となる構造的分離（最重要）

| 層 | 内容 | 置き場所 | 移植性 |
|---|---|---|---|
| **委譲アルゴリズム（汎用）** | 役割分類・相対選択・損益分岐の手順 | `sdd-implement/references/delegation-routing.md` | プラグインに同梱（環境非依存） |
| **委譲レジストリ（環境固有）** | 役割→委譲先(agent)→ティアの束縛、ティア順序 | 各プロジェクトの `CLAUDE.md` 委譲マトリクス ＋ `.claude/agents/*.md` frontmatter | 環境ごとに差し替え |

スキルは自己完結（他スキルの references を参照しない）。アルゴリズムは「プロジェクトの委譲レジストリ」を
抽象参照し、具体束縛は各環境が持つ。本リポジトリ（ドッグフーディング）ではレジストリ＝自身の CLAUDE.md。

## 3. ティアはしご（Claude・本リポジトリの場合）

上位＜＝＞下位の順序を明示宣言する（相対選択の基盤）:

```
Fable 5（最上位・司令塔候補） > Opus > Sonnet > Haiku
```

役割→委譲先→ティア束縛（CLAUDE.md 委譲マトリクスが SSOT）:

| 役割 | 委譲先 | ティア |
|---|---|---|
| 深い推論・設計・難調査 | `deep-reasoner` | Opus |
| 機械的・定型作業 | `fast-worker` | Sonnet |
| 量産・Web検索 | `antigravity-delegate` | （別プラットフォーム＝直交） |
| クロスモデル検証 | `antigravity:review` | （別プラットフォーム＝直交） |

## 4. 相対選択アルゴリズム（delegation-routing.md に実装）

司令塔ティア T を起点に、タスクを役割分類してから:

1. **役割分類**: 機械的修正 / 難調査・設計 / 量産 / 検証。
2. **下位への委託（CORE-FR-007）**: 機械的・量産タスクで、役割の委譲先ティアが T より**下位**なら委譲。
   下位が無ければ司令塔が自己実行。役割の束縛ティア == T なら**同一ティア＝無効化**（省トークンにならない）。
3. **上位への相談・上申（CORE-FR-008）**: 難調査・設計タスクで、上位ティアが存在するなら相談・上申。
   T が最上位なら相談先なし＝自己判断。
4. **別プラットフォーム（直交）**: antigravity(Gemini) は相対階層と独立。量産・クロス検証はいつでも可。
5. **損益分岐（CORE-CON-007）**: 1ファイルの軽微編集など往復コスト＞節約の小さな単発は委譲せず自己実行。

具体例（本リポジトリの束縛）:
- 司令塔=Fable5 → 下位(Opus/Sonnet)へ委譲可・相談先なし。
- 司令塔=Opus → fast-worker(Sonnet)へ委譲可・deep-reasoner(=Opus,同一ティア)は無効・相談先なし。
- 司令塔=Sonnet → 下位worker無し・難題はOpus(deep-reasoner)へ上申。

## 5. プラットフォーム別レジストリ（CORE-FR-009）

- **Claude レジストリ**: 本リポジトリの CLAUDE.md 委譲マトリクス（本設計で形式化）。env-register が更新機構。
- **Antigravity レジストリ**: antigravity プラグイン側が所有（Gemini のモデルルーティング）。本リポジトリでは
  参照するのみで所有しない。両者は物理的に別ファイル＝分離。一方の更新が他方に干渉しない。
- ルーティング文書（delegation-routing.md）は**モデル名を直書きせず役割で参照**する。

## 6. 機械検証（CORE-NFR-001）— release_check.py に実装

本リポジトリのレジストリ整合を検査する（環境固有のため spec_inspect.py ではなく repo 側の release_check.py）:

1. **agent 実在**: 委譲マトリクスの委譲先（deep-reasoner / fast-worker）が `.claude/agents/*.md` に実在。
2. **ティア順序整合**: ティアはしごに重複・循環がなく、各委譲先のティアがはしご上に存在。
3. **モデル名の外部直書き禁止**: 具体モデル名（opus/sonnet/haiku/fable/gemini/claude-*）が、
   許可された場所（委譲マトリクス・`.claude/agents/*.md` frontmatter）**以外**のルーティング文書に現れない。
4. いずれか違反で非ゼロ終了。

テスト先行（tests/）で正常系＋各違反系フィクスチャを検証。

## 7. サーフェシング（CORE-FR-006 の入口連結）

- `sdd-implement/SKILL.md`: タスク着手前に delegation-routing.md を参照する委譲ゲート手順を追加。
- `sdd-core/SKILL.md`: フェーズ・ルーティング表の Execute 行から env-orchestration を明示クロス参照。
- `env-orchestration/SKILL.md`: Execute からの想起点を追記（決定木の入口）。

## 8. 影響とロールバック

規約・文書・検査の追加が中心（既存実行挙動は不変）。対象プラグイン（bitz-sdd / bitz-env）は version bump。
複数スキル横断のため軽量レーン非適用・単独 revert 可能。
