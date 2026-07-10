# BitzSkills アーキテクチャレビュー

- 作成日: 2026-07-10
- 対象: リポジトリ全体（コミット 2caad30 時点 + 未コミットの退避資料）
- 関連文書: [refactoring_master_plan.md](./refactoring_master_plan.md)（問題点の詳細と改修計画はそちらが正）

---

## 1. プロジェクトの性格

Agent Skills オープン標準に準拠したスキルを、**3つの AI エージェント
（Claude Code / Antigravity 2.0 / Codex）向けプラグインとして開発・配布するモノレポ**。
リポジトリルート自体がマーケットプレイス `bitzskills` であり、アプリケーションコードは持たない。
「コード」に相当するのは (a) スキル定義（Markdown + frontmatter）、(b) それを検証・運用する
少量の Python/シェルスクリプト、(c) エージェント設定（ガードレール）の3種類。

## 2. 主要ディレクトリの役割

| ディレクトリ | 役割 | 備考 |
|---|---|---|
| `.claude-plugin/marketplace.json` | マーケットプレイス定義。全プラグインの唯一のカタログ | 実体 `plugins/*` との整合は `release_check.py` が検証 |
| `plugins/skill-creator/` | **スキル開発ライフサイクル**を担う10スキル | v0.3.0 |
| `plugins/plugin-creator/` | **プラグインの器**（構造・コマンド・エージェント・フック・MCP・設定）の作り方リファレンス7スキル + agents 3 + `create-plugin` コマンド | v0.2.1 |
| `plugins/bitz-sdd/` | **仕様駆動開発（SDD）ワークフロー**7スキル + Python スクリプト4本 | v0.2.1 |
| `scripts/` | リポジトリ横断の運用スクリプト（`bump_version.py` / `release_check.py` / `agy_guard.py`） | 全エージェント共用 |
| `.claude/` | Claude Code 固有: `settings.json`（permissions によるガードレール強制）、`commands/`（`/bump`, `/add-plugin`） | |
| `.agents/` | Antigravity 用: `hooks.json`（PreToolUse → `agy_guard.py`）と `rules/00-guardrails.md` | |
| `docs/調査報告/` | 3エージェントの検証済み仕様（01〜03）+ nexus-architect 退避スナップショット（04、参照専用） | 「迷ったらここが正」と AGENTS.md が規定 |
| `docs/翻訳規約/` | 翻訳用語集（用語統一レビューの基準） | |
| `evals/` | skill-tester / evaluator の成果物と observer の観察ログ置き場 | 現状ほぼ空（枠のみ） |
| `AGENTS.md` | **全ルールの唯一の正**。CLAUDE.md は `@AGENTS.md` インポート + Claude 固有の差分のみ | |

## 3. 主要モジュールの責務

### skill-creator（ライフサイクル型）

| スキル | 責務 |
|---|---|
| skill-pipeline | オーケストレーター。**自身は作業せず**、工程間の受け渡しと反復判断のみ |
| skill-creator | ヒアリングと雛形作成 |
| skill-validator | 仕様準拠チェック（lint。基準は `references/checklist.md`） |
| skill-tester / skill-evaluator | スキルあり/なし比較テストの実行（`evals/` へ保存）と採点 |
| skill-optimizer | description 最適化・progressive disclosure への構造改善 |
| skill-packager | 実環境への配置・バージョンアップ・アンインストール・配布（**唯一リポジトリ外に書くスキル**） |
| skill-instrumenter / observer / improver | 配置後の自己改善ループ（計装 → 観察ログ → 分析修正） |

### bitz-sdd（ワークフロー型）

| スキル | 責務 | 出力先 |
|---|---|---|
| bitz-sdd | オーケストレーター。フェーズ判定と規律の強制 | — |
| sdd-discovery | ビジョン・指標・スコープ・ペルソナ・ポジショニング | `.spec/discovery/` |
| sdd-design | ドメインストーリー・ドメインモデル・API・アーキテクチャ | `.spec/design/` |
| sdd-infra | インフラ・セキュリティ・SLO・DR・コスト | `.spec/design/` |
| sdd-review | 5観点並列レビューと統合判定 | `.spec/reviews/` |
| sdd-docs | `.spec` ⇄ `docs` 双方向同期（`sdd_sync.py`）と docs 検証（`docs_inspect.py`） | `docs/` |
| sdd-report | `.spec/` 集計レポート生成（`sdd_report.py`） | `reports/`（※後述の逸脱） |

### plugin-creator(リファレンス型)

plugin-structure / plugin-settings / command-development / agent-development /
hook-development / mcp-integration / skill-development の7本。作業を実行するというより
「作り方の知識」を提供する。skill-development は skill-creator と守備範囲が重複。

### scripts/（リポジトリ運用）

- `bump_version.py` — 2マニフェスト（`.claude-plugin/plugin.json` と `plugin.json`）を同値に保つ唯一の更新経路
- `release_check.py` — version 整合・marketplace 整合・frontmatter 必須項目・plugin validate の一括ゲート
- `agy_guard.py` — Antigravity の PreToolUse フック実体（危険コマンド deny / リポジトリ外書き込み ask）

## 4. 主要な処理の流れ

### 4.1 スキル開発フロー（skill-creator）

```
skill-creator（作成）→ skill-validator（検証）→ skill-tester（evals/ へ実行結果）
  → skill-evaluator（採点）
      不合格 → skill-optimizer → validator → tester → evaluator（最大3周）
      合格   → skill-optimizer（description 最終調整）→ skill-packager（配置）
配置後: skill-instrumenter（計装）→ skill-observer（observations.jsonl）→ skill-improver（分析・修正）
```

### 4.2 SDD フロー（bitz-sdd、利用側プロジェクトで動く）

```
sdd-discovery → sdd-design → sdd-infra → sdd-review（ゲート）→ 実装 → sdd-report
        すべての成果物: .spec/（SSOT）
        人間向けビュー: sdd_sync.py pull で docs/ へ展開（手修正は push で逆反映）
        機械検証:      spec_inspect.py（.spec 側）/ docs_inspect.py（docs 側）
```

### 4.3 リリースフロー（このリポジトリ自身）

```
スキル変更 → frontmatter の version/updated 更新
  → python3 scripts/bump_version.py <plugin>（2マニフェスト同時 bump）
  → python3 scripts/release_check.py（全ゲート）
  → ブランチ → PR → main（直コミット禁止）
```

### 4.4 ガードレール実行フロー（防御の多層化）

```
規範層:  AGENTS.md（全エージェント共通の禁止・事前確認・検証義務）
強制層:  Claude Code   → .claude/settings.json permissions（deny / ask / allow）
         Antigravity   → .agents/hooks.json → scripts/agy_guard.py（PreToolUse で deny / force_ask）
         Antigravity 規範補強 → .agents/rules/00-guardrails.md
```

## 5. 依存関係の方向

```
marketplace.json ──列挙──▶ plugins/*（カタログ→実体の一方向）
scripts/release_check.py ──読み取り検証──▶ plugins/*（逆方向の依存なし）
スキル ──「名前の言及」──▶ 他スキル（パス参照は規約で禁止 = 疎結合）
.spec/（SSOT）──sdd_sync pull──▶ docs/（派生ビュー。push は例外的な逆反映）
CLAUDE.md ──@import──▶ AGENTS.md（ルールの依存方向は常に AGENTS.md が上流）
docs/調査報告/ ◀──仕様の裏取り── 各スキル・スクリプト（実装が調査文書に従う）
```

要点: **すべて一方向**で、循環依存は存在しない。スキル間連携が「名前の言及」のみなのが
このリポジトリの結合度を最も低く保っている仕組み（フォルダ単位コピーで壊れない）。

## 6. 共通処理の置き場所

| 種類 | 置き場所 | 補足 |
|---|---|---|
| リポジトリ運用ロジック | `scripts/` | 全エージェント共用。唯一の「共有コード」置き場 |
| ルール・規約 | `AGENTS.md`（唯一の正） | 各所は参照のみ。二重記載しない |
| プラットフォーム仕様の知識 | `docs/調査報告/` | 実装が迷ったときの裏取り先 |
| スキル横断の書式定義 | 各スキルの `references/`（spec.md / checklist.md / test-design.md 等） | 「どのスキルの references が正か」を AGENTS.md が指名する方式 |
| スキル間の共有ライブラリ | **存在しない（意図的）** | 自己完結規約により、frontmatter パーサ等は各スクリプトに重複実装（4箇所） |

## 7. 実際に使われている設計パターン

1. **オーケストレーター + 専門スキル**（skill-pipeline / bitz-sdd）— 統括役は判断と委譲のみを行い、作業は単一責務のスキルが担う。
2. **Progressive Disclosure** — SKILL.md 本文は薄く、詳細は `references/`、テンプレは `assets/`、実行系は `scripts/` に分離。3エージェント共通のコンテキスト節約パターン。
3. **SSOT + 派生ビュー** — `.spec/` をマスターとし `docs/` を同期生成。AGENTS.md ⇄ CLAUDE.md も同型（マスター + プラットフォーム差分）。
4. **二重マニフェスト（アダプタ）** — 同一プラグインを `.claude-plugin/plugin.json`（Claude）と `plugin.json`（Antigravity）で二重公開し、`bump_version.py` が同値性を機械保証。
5. **規範 + 機械強制の二層ガードレール** — AGENTS.md の規範を settings.json permissions と PreToolUse フックで機械的に裏打ちする defense in depth。
6. **ゲート駆動** — sdd-review の PASS/FAIL、skill-evaluator の合否、release_check.py の一括ゲートなど、「先へ進む条件を機械判定する」構造が全域で反復。
7. **自己記述** — 配置済みスキルは frontmatter の `installed-at` / `installed-from` で自身の由来を持つ（skill-packager 管理）。
8. **自己改善ループ（テレメトリ）** — instrumenter → observer（observations.jsonl）→ improver による観察駆動の改善。

## 8. 設計上の一貫性が崩れている箇所

> 詳細・改修計画は refactoring_master_plan.md の P1〜P8 を参照。ここでは「どの原則が破れているか」を示す。

| 箇所 | 破れている原則 |
|---|---|
| `sdd-report` が `reports/status-report.md` に出力 | 「`.spec/` が SSOT、人間向けは docs/ へ sync」の原則の唯一の例外。第3の出力先が生えている（P2） |
| スキル命名: bitz-sdd のオーケストレーターだけ `bitz-sdd`、plugin-creator は `plugin-*` / `*-development` / `mcp-integration` の3パターン混在 | 「プラグイン内プレフィックス統一」（skill-creator だけが達成）（P3） |
| `plugin-creator/skills/skill-development` | 「連携はスキル名の言及で行う」規約に反し、skill-creator の内容を複製保持（P4） |
| frontmatter パーサ4実装（spec_inspect / docs_inspect / sdd_report / release_check） | 自己完結規約による**意図的**重複だが、挙動を揃える共有テストが無いため静かに乖離しうる（P7） |
| ガードレール強制層の非対称 | Claude（settings.json）と Antigravity（hooks + agy_guard.py）は機械強制があるが、Codex 向けの強制層はリポジトリ内に存在しない（規範層 AGENTS.md のみ）。deny パターンの網羅度も settings.json と agy_guard.py で個別管理であり、片方だけ更新される余地がある |
| `evals/` | 規約上はテスト成果物の置き場だが実体がほぼ空。パイプラインの「テスト→評価」工程がまだ実運用されていないことを示す |

## 9. 肥大化している箇所

| 対象 | 規模 | 評価 |
|---|---|---|
| `plugin-creator/skills/hook-development/SKILL.md` | 420行 | Progressive Disclosure 違反の筆頭。references/ へ分離すべき |
| plugin-creator の他4本（mcp-integration 293 / plugin-settings 280 / plugin-structure 260 / agent-development 240行） | 240行超 | 同上。skill-creator 群（60〜103行）・bitz-sdd 群（32〜82行）と比べ突出 |
| `docs_inspect.py`（387行）/ `spec_inspect.py`（347行） | 検証ロジックの中核 | 行数自体より「テストゼロのまま複雑化している」ことが問題。分割よりテスト整備が先 |

## 10. 今後リファクタリングする際の注意点

1. **テストと CI を最初に入れる**（refactoring plan Phase 0）。特に `sdd_sync.py` は利用側プロジェクトのファイルを上書きするため、退行テストなしで触らない。
2. **スキル名は「発動トリガーであり公開 API」**。リネームは frontmatter・フォルダ名・他スキルからの名前言及・README・marketplace.json・AGENTS.md・`.claude/commands/` まで波及する。事前 grep の参照一覧と旧名→新名マッピング表を必ず残す（revert 可能性の担保）。
3. **自己完結規約を壊さない**。重複排除の誘惑（共通ライブラリ化）は Agent Skills の「フォルダ単位コピー」前提と衝突する。重複は「共有テストケースで挙動を揃える」方向で解消する。
4. **2マニフェストは手編集しない**。version 変更は必ず `bump_version.py` 経由。完了報告の前に `release_check.py` を自分で実行する（他エージェントの自己申告を信用しない — AGENTS.md 検証義務）。
5. **ガードレールは3点セットで見直す**。AGENTS.md（規範）・`.claude/settings.json`・`.agents/hooks.json` + `agy_guard.py`（強制）は対応関係にあり、片方だけ緩める/強めると乖離する。
6. **`.spec` ⇄ `docs` の同期マッピング変更は既存利用プロジェクトへの互換性問題**。マッピング追加（新ファイル）は安全だが、既存対応の変更・削除は移行手順込みで設計する。
7. **`docs/調査報告/04.nexus-architect/` は編集禁止のスナップショット**（参照専用、MIT）。蒸留はしてよいがスナップショット自体は改変しない。
8. **リポジトリ外への書き込み（skill-packager の配置先）はユーザー承認必須**のまま維持する。緩和は設計判断ではなくガードレール変更として扱う。
