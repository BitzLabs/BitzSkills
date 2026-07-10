# BitzSkills リファクタリング・マスタープラン

- 作成日: 2026-07-09
- 対象ブランチ起点: `feat/multi-agent-rules-guardrails`（2caad30、作業ツリー clean、`release_check.py` 全 PASS）
- ステータス: **調査・方針整理のみ。実装は未着手**

---

## 0. 最優先の注意事項（実装前に必ず対応）

> **✅ 退避済み（2026-07-10）**: `nexus-architect/` 全体（`.git` 除く 357 ファイル）を
> `docs/調査報告/04.nexus-architect/`（出所は同フォルダの `_provenance.md` 参照、MIT License 確認済み）、
> `translation-glossary.md` を `docs/翻訳規約/translation-glossary.md` へコピーした。
> DB 系スキルに限定せず全体を退避したため、以降の記述は充足済み。翻訳作業ログ
> （batch*.txt 等）は一時ファイルのため退避対象外とした。

元資料が **揮発性の /tmp 配下** に残っている:

```
/tmp/claude-1000/-home-hide-Dev-BitzSkills/28e740b3-d649-4593-b27a-0cff04d94cc1/scratchpad/
├── translation-glossary.md        # 翻訳用語集・スタイルガイド（用語統一レビューの基準）
├── nexus-architect/               # bitz-sdd の蒸留元（約58スキル。DB系スキル群を含む）
└── nexus-ja-batches/ ほか翻訳作業ログ
```

WSL の再起動や tmp クリーンアップで消失する。**Phase 1 の着手前に、最低限
`translation-glossary.md` と `nexus-architect/skills/` の Database 系スキル
（`design-data-layer` / `analyze-data-model` / `migrate-database` / `migrate-mysql` /
`migrate-oracle` / `migrate-postgresql` / `crud-ops` / `jdbc-ops` および
`docs/database-migration*.md`）を恒久的な場所へ退避すること。**
（退避先候補: `docs/調査報告/04.nexus-architect/` または repo 外の `~/BitzLabs/_reference/`。
nexus-architect のライセンス表記を確認のうえリポジトリへ取り込むか判断する）

---

## 1. リファクタリングの目的

1. **bitz-sdd の設計工程に Database（データ層）設計を組み込み**、MVC + Database 型の
   一般的なアプリケーション開発に対応させる。
2. **`.spec/` への成果物集約を徹底**し、「.spec が SSOT」という原則の例外をなくす。
3. **スキル命名規則をプラグイン単位で統一**し、発見性と保守性を上げる。
4. **用語・訳語を translation-glossary.md 基準で統一**し、資料間の表記ゆれをなくす。
5. **安全網（テスト・CI）を先に整備**し、以後の変更を機械検証で守れるようにする。
6. **SDD（プロセス基盤）と DDD（設計手法）をプラグイン分離**し、`.spec` を公開契約として
   設計手法を差し替え可能にする（2026-07-10 の検討で追加）。
7. **実装・テスト工程のスキルを新設**し、SDD を discovery〜report の一気通貫フローとして完成させる。
8. **Git / GitHub を使った開発フロー（worktree・コミット規定・Issue 駆動）を規定**し、
   複数エージェント並列開発に耐える運用をスキル化する（復元は worktree 破棄に一本化し、
   checkpoint の規定は置かない）。

## 2. 現状調査の結果

### 2.1 プロジェクト構造と役割（現状）

```
.claude-plugin/marketplace.json   # マーケットプレイス定義（3プラグイン列挙）
.claude/                          # Claude Code 設定・リポジトリ専用コマンド（/bump, /add-plugin）
.agents/                          # 3エージェント共通の hooks / rules（ガードレール強制層）
plugins/
├── skill-creator/   # スキル開発ライフサイクル（10スキル、全て skill-* 接頭辞）v0.3.0
├── plugin-creator/  # プラグイン開発（7スキル + agents 3 + command 1）v0.2.1
└── bitz-sdd/        # SDD ワークフロー（7スキル + Python スクリプト4本）v0.2.1
docs/調査報告/        # 3エージェント（Antigravity/ClaudeCode/Codex）の検証済み仕様
evals/               # テスト成果物置き場（現状 observations/README.md のみ＝ほぼ空）
scripts/             # 運用スクリプト（bump_version / release_check / agy_guard）
```

### 2.2 主要モジュールの責務と依存の流れ

- **skill-creator**: creator → validator → tester → evaluator →（不合格時 optimizer）→ packager、
  配置後は instrumenter / observer / improver の自己改善ループ。スキル間の連携は
  「スキル名の言及」のみ（自己完結規約どおり）で、相対パス依存はない。健全。
- **bitz-sdd**: `bitz-sdd`（オーケストレーター）が discovery → design → infra → review →
  実装 → report を統括。データフローは
  `.spec/`（マスター）→ `sdd_sync.py pull` → `docs/`（人間向け）の一方向 + 逆反映（push）。
  検証は `spec_inspect.py`（.spec 側）と `docs_inspect.py`（docs 側）。
- **plugin-creator**: プラグインの器（structure / commands / agents / hooks / MCP / settings）
  の作り方を教えるリファレンス集。skill-creator とは `skill-development` スキルで内容が重複。
- **scripts/**: リポジトリ運用の横断チェック。`release_check.py` が
  version 整合・marketplace 整合・frontmatter・plugin validate を一括検証（現在全 PASS）。

### 2.3 発見した問題点（どこに・なぜ問題か）

| # | 問題 | 場所 | なぜ問題か | 深刻度 |
|---|------|------|-----------|--------|
| P1 | **Database 設計工程の欠落** | `plugins/bitz-sdd/skills/sdd-design/`（references は domain-modeling / api-design / architecture / domain-story / brownfield のみ） | 蒸留元 nexus-architect には `design-data-layer`・`analyze-data-model`・`migrate-database` 等の DB 系スキル群が丸ごと存在するが、bitz-sdd への蒸留時に脱落。ER 図・スキーマ設計・永続化戦略・マイグレーションを扱う工程がなく、**MVC + Database 型の開発に未対応**（`sdd-design/references/architecture.md` にも MVC・レイヤリング・永続化の記述なし。データストアは「ランタイムビューの1ノード」として登場するだけ） | 高 |
| P2 | **`.spec/` 集約の例外** | `sdd-report`（`sdd_report.py:218` が `reports/status-report.md` に出力） | 「.spec が SSOT、人間向けは docs/ へ sync」という原則から外れた第3の出力先 `reports/` が存在。他の6スキルは `.spec/discovery/`・`.spec/design/`・`.spec/reviews/` に集約済みで、これが唯一の逸脱 | 中 |
| P3 | **スキル命名の不統一** | 全プラグイン | bitz-sdd: オーケストレーターだけ `bitz-sdd`（他は `sdd-*`）。plugin-creator: `plugin-structure` / `plugin-settings` / `command-development` / `agent-development` / `hook-development` / `mcp-integration` / `skill-development` と3パターン混在。skill-creator のみ `skill-*` で統一済み | 中 |
| P4 | **skill-development の重複** | `plugins/plugin-creator/skills/skill-development/`（本体183行 + references/skill-creator-methodology.md） | skill-creator プラグインの守備範囲（スキルの作り方）を plugin-creator 側でも別文書として保持しており、仕様変更時に2箇所メンテが必要。AGENTS.md の「連携はスキル名の言及で行う」規約に沿えば、skill-creator への参照1行に置換できる | 中 |
| P5 | **用語・訳語の未検証** | bitz-sdd の references/assets 全般、`docs/調査報告/` | 全ファイル日本語化は完了している（英語のみの references は検出ゼロ）が、translation-glossary.md の規約（初出「English（日本語）」形式、カタカナ許容リスト、製品名非翻訳）に照らした表記ゆれレビューは未実施 | 中 |
| P6 | **テスト・CI の不在** | リポジトリ全体（`.github/` なし、テストコードゼロ） | Python スクリプト7本・約1,400行（`spec_inspect.py` 347行、`docs_inspect.py` 387行、`sdd_sync.py` 183行、`sdd_report.py` 231行、`release_check.py` 97行、`bump_version.py` 76行、`agy_guard.py` 56行）に自動テストが1本もない。`release_check.py` も手動実行頼み。**このままリネームや構造変更を行うのは危険** | 高 |
| P7 | **frontmatter パーサの多重実装** | `spec_inspect.py:26` / `docs_inspect.py:75` / `sdd_report.py:9` / `release_check.py:34` | 同等の `parse_frontmatter` が4実装あり、挙動が微妙に食い違うと検証結果が不一致になる。ただし「スキルは自己完結」規約があるため、スキル間の共通ライブラリ化は**規約違反**。統一するなら「仕様（テストケース）の共有」で挙動を揃えるのが正攻法 | 低 |
| P8 | **肥大化気味の SKILL.md** | `plugins/plugin-creator/skills/hook-development/SKILL.md`（420行）ほか plugin-creator の5本が240行超 | Agent Skills のベストプラクティス（本文は簡潔に、詳細は references/ へ = progressive disclosure）から逸脱。コンテキスト消費も大きい | 低 |
| P9 | **実装・テスト工程のスキル欠落** | `plugins/bitz-sdd/`（オーケストレーターのフェーズ表に「実装」「検証」はあるが担当スキルなし） | 蒸留元 nexus-architect の `design-implementation` / `generate-test-specs` / `scaffold` / `build-app` が脱落（P1 の Database と同じパターン）。SDD が「設計して終わり」のフローになっている | 高 |
| P10 | **DDD がプロセス基盤に埋め込み** | `sdd-design`（domain-modeling / domain-story 等の DDD 手法が SKILL 本体に同居） | 設計手法（DDD）とプロセス骨格（フェーズ遷移・ゲート・.spec スキーマ）が不可分で、MVC + DB の小規模開発で DDD を外せない。`sdd-review` は `.spec/design/**` を走査するだけで書き手を問わないため、分離の下地は既にある | 中 |
| P11 | **Git / GitHub 開発フロー規定の不在** | `bitz-sdd/references/parallel-git.md`（ブランチ規約・競合回避・権限マトリクスのみ） | worktree（複数エージェント並列の分離手段と失敗時の復元手段）、コミット/マージコメント規定、GitHub Issue 駆動フローが未規定。BitzSkills リポジトリ自身にもコミット規約がない（AGENTS.md はブランチ運用のみ） | 中 |

### 2.4 テストが不足している可能性がある箇所（優先順）

1. `sdd_sync.py` — **双方向同期で既存ファイルを上書きする**。mtime 比較・stories 集約の退行は
   ユーザーの成果物破壊に直結する。最優先。
2. `spec_inspect.py` — ID 体系（要件番号・クロスリファレンス・implements マップ）の中核。
3. `docs_inspect.py` — docs 側の整合検証。registry / supersede / ADR ブリッジのロジックが複雑。
4. `bump_version.py` — 2マニフェスト同時更新の原子性（片方だけ更新される事故の防止）。
5. `release_check.py` — 安全網そのもの。誤 PASS が最も怖い。
6. `sdd_report.py` / `agy_guard.py` — 影響は限定的。スモークテストで十分。

### 2.5 影響範囲が大きく、触ると危険な箇所

- **スキルの `name`（フォルダ名 + frontmatter）のリネーム**: インストール済みユーザーの
  発動トリガー・スキル間の「名前による言及」・README・marketplace.json・
  `.claude/commands/`・AGENTS.md まで波及する。grep で全参照を洗ってから一括変更が必須。
- **`sdd_sync.py` の同期マッピング**: `.spec/` ⇄ `docs/` の対応表を変えると
  既存の BitzSDD 利用プロジェクトのファイルが意図せず上書き・孤立する。
- **`.claude-plugin/marketplace.json` と2マニフェストの整合**: 壊すとインストール自体が失敗。
- **`.claude/settings.json` / `.agents/hooks.json` のガードレール**: 緩める変更は AGENTS.md と
  必ずセットで見直す（既存規約）。
- **`skill-packager` の配置ロジック**: リポジトリ外（`~/.claude/skills/` 等）への書き込みを
  伴うため、変更時の検証はドライラン必須。

### 2.6 削除・統廃合候補

| 候補 | 理由 | 扱い |
|------|------|------|
| `plugins/plugin-creator/skills/skill-development/` | P4 のとおり skill-creator と重複 | Phase 4 で skill-creator への委譲に置換（削除ではなく1枚の案内スキル化 or 完全削除を選択） |
| `plugins/plugin-creator/agents/skill-reviewer.md` | skill-creator の skill-validator と役割重複の疑い | Phase 4 で内容比較のうえ判断 |
| `evals/` 直下 | 空に近いが「置き場」として規約に登場するため削除しない | 維持 |
| 翻訳作業ログ（scratchpad の batch*.txt 等） | 一時ファイル。glossary と nexus 本体以外は退避不要 | 退避対象から除外 |

---

## 3. フェーズ分割

> 原則: **安全網 → 用語 → 中身の順**。リネームと構造変更（P2/P3/P4）はテストと CI が
> 入ってから行う。各フェーズ = 1 PR（Phase 4 のみ2 PR）で、常に `release_check.py` PASS を保つ。

### Phase 0: 安全網の整備（最初に着手）

- **対象**: `scripts/`、`plugins/bitz-sdd/skills/*/scripts/`、`.github/workflows/`（新規）
- **実施内容**:
  1. scratchpad 資料の退避（本書 §0。glossary は `docs/翻訳規約/translation-glossary.md` として取り込み推奨）
  2. `tests/` を新設し pytest 導入。§2.4 の優先順で、まず `sdd_sync.py`（fixture の
     `.spec`/`docs` ツリーに対する pull/push/diff の破壊防止テスト）、`bump_version.py`
     （2マニフェスト同値性）、`release_check.py`（意図的に壊した fixture で FAIL すること）
  3. GitHub Actions: push/PR で `pytest` + `python3 scripts/release_check.py` を実行
- **完了条件**: CI がグリーン。スキルの中身は一切変更しない。

### Phase 1: 用語・訳語の統一レビュー（安全網不要のため Phase 0 と並行可）

- **対象**: `plugins/bitz-sdd/**/*.md`、`plugins/plugin-creator/**/*.md`、`docs/調査報告/`
- **実施内容**: translation-glossary.md の規約（初出「English（日本語訳）」、カタカナ許容
  リスト、製品名非翻訳、見出し・表構造の維持）に照らして全 Markdown をレビューし、
  表記ゆれを修正。文言のみの変更で構造・ロジックには触れない。
- **完了条件**: 用語チェックの観点リストと修正差分。各プラグイン patch bump。

### Phase 2: `.spec/` 集約の徹底（P2）

- **対象**: `plugins/bitz-sdd/skills/sdd-report/`（SKILL.md + `sdd_report.py`）、
  `sdd-docs`（同期マッピングに reports を追加する場合）
- **実施内容**: レポート出力を `reports/status-report.md` → `.spec/reports/status-report.md` に
  変更し、人間向け公開が必要なら `sdd_sync.py pull` の対象に追加。bitz-sdd SKILL.md /
  README の記述も同期。
- **完了条件**: `.spec/` 外に書くスキルがゼロ（skill-packager の「実環境への配置」は
  性質上の例外として明記）。minor bump。

### Phase 3: スキル命名の統一 + プラグイン再編（P3, P10）— ⚠️ 破壊的変更

> 命名変更とプラグイン分割は波及範囲（フォルダ名・frontmatter・相互参照・marketplace.json）が
> 重なるため、**1つの設計判断として同一フェーズで実施**する（手戻り防止）。

- **対象**: 全プラグインのスキルフォルダ名・frontmatter `name`・全参照、
  および `sdd-design` からの DDD 手法の分離
- **プラグイン再編（bitz-ddd 分離）**:
  - **bitz-sdd** = プロセス基盤: フェーズ遷移・ゲート・`.spec` スキーマ・docs 同期。
    `sdd-design` は「軽量デフォルト設計」（API・アーキテクチャ・データ層）として残す
  - **bitz-ddd（新プラグイン）** = 設計手法プロバイダ: `ddd-story`（ドメインストーリーテリング）、
    `ddd-model`（戦略設計・集約・境界づけられたコンテキスト）、
    `ddd-evaluate`（nexus の `evaluate-ddd` / `evaluate-mmi` を蒸留した成熟度評価）
  - **契約は `.spec` のファイル配置 + frontmatter 書式**: 既存の
    `assets/artifact-frontmatter.md` を「外部プラグインが .spec に書き込む際の公開仕様」に昇格。
    依存方向は bitz-ddd → `.spec` → bitz-sdd の一方向で、bitz-sdd は bitz-ddd を知らない
    （DDD 未インストールでも SDD 単体で完結する graceful degradation）
  - bitz-ddd の README に「bitz-sdd との併用前提」と契約書式へのリンクを明記
- **命名規則（2026-07-10 ユーザー確定）**:
  - 規則: **各プラグイン内は単一プレフィックスで統一**
  - skill-creator: 変更なし（`skill-*` で統一済み）
  - bitz-sdd: オーケストレーター `bitz-sdd` → **`sdd-core`** に改名（確定）。
    `sdd-infra` → **`sdd-ops`** に改名（確定。中身は構成・セキュリティ・SLO・DR・コストの
    運用設計そのもので、docs 同期先 `docs/05-operations/` とも一致するため）。
    新設の設計手法プロバイダは **`bitz-ddd`** プラグイン（スキルは `ddd-*` 接頭辞）
  - plugin-creator: `command-development` → `plugin-commands`、`agent-development` →
    `plugin-agents`、`hook-development` → `plugin-hooks`、`mcp-integration` → `plugin-mcp`、
    `plugin-structure` / `plugin-settings` は維持、`skill-development` は Phase 4 で処理
- **手順**: ①全参照を grep で列挙（SKILL.md 相互言及・README・marketplace.json・
  AGENTS.md・`.claude/commands/`・agents/）→ ②フォルダ + frontmatter + 参照を一括変更 →
  ③`release_check.py` + 実インストール（`/plugin install`）で発動確認
- **完了条件**: 全参照更新済み・validate PASS。**major bump**（インストール済みユーザーに
  とって破壊的なため）。README に移行注記。

### Phase 4: 重複の統廃合（P4）

- **対象**: `plugins/plugin-creator/skills/skill-development/`、`agents/skill-reviewer.md`
- **実施内容**: skill-development の独自価値（プラグイン文脈特有の記述）だけを残して
  skill-creator への案内に置換、または完全削除。skill-reviewer は skill-validator と
  diff を取り、重複なら削除・独自観点があれば validator へ吸収。
- **完了条件**: 「スキルの作り方」の記述が skill-creator に一本化。minor bump。

### Phase 5: Database 対応 + 実装・テスト工程の新設（P1, P9）— 本丸

- **PR 5c: 実装・テスト工程スキルの新設**（5a と並行可）
  - `sdd-implement`（新スキル）: `.spec/tasks/` へのタスク分解（depends_on / boundary 宣言）と、
    要件 ID を implements で紐づけた実装の規律。`spec_inspect.py` の implements マップが
    既に検証手段として存在するため、それを実行工程として明文化する
  - `sdd-test`（新スキル）: EARS 要件 → テスト仕様の導出と、検証結果の `.spec` への記録。
    既存の `references/verification.md` を実行スキルへ昇格させる形で蒸留元
    （nexus の `generate-test-specs` / `design-implementation`）を取り込む
  - `bitz-sdd` オーケストレーターのフェーズ表を discovery → design → infra → review →
    **implement → test** → report に更新

- **PR 5a: 設計工程への Database / データ格納設計の組み込み**

  > 配置判断（2026-07-10）: データ層設計は **bitz-sdd 側に残す**。DDD なしでも DB 設計は
  > 必須のため「軽量デフォルト設計」の一部とし、ScalarDB 特化などの深い内容だけ
  > 将来 `bitz-data` に切り出す余地を残す。
  >
  > 構成判断（2026-07-10 ユーザー確定）: **独立の傘スキル `sdd-data` 1本 + references 構成**。
  > DB を使わないシステムもあるため設計工程の必須ステップにはせず、DB に限らない
  > データ格納設計全般（RDB / NoSQL / ファイル形式 / オブジェクトストレージ）を守備範囲とする。
  > `sdd-db` / `sdd-format` への細分化は採らない（sdd-ops と同じ「傘 + references」パターンに統一）。
  - `plugins/bitz-sdd/skills/sdd-data/`（新スキル）を追加。references 構成:
    - `data-modeling.md` — 論理データモデル（ER 図・エンティティ整合性）
    - `storage-selection.md` — 格納方式の選定（RDB / NoSQL / ファイル / オブジェクトストレージ /
      キャッシュ。技術適合性評価は architecture.md の証拠駆動方式に準拠）
    - `format-design.md` — ファイル・交換形式の設計（JSON / CSV / Parquet 等のスキーマ定義）
    - `migration.md` — スキーマ変更・データ移行計画
    （蒸留元: nexus-architect の `design-data-layer` / `analyze-data-model` / `migrate-database`）
  - 成果物は論理モデル → 格納方式 → 物理スキーマ/形式 → 永続化戦略（トランザクション境界・
    整合性）→ マイグレーション計画を `.spec/design/data-model.md` 等に出力
  - `sdd-design/references/architecture.md` にレイヤリング（MVC / レイヤードアーキテクチャ
    における Model–View–Controller とデータ層の対応）の設計指針を追記
  - `sdd-docs` テンプレートに `docs/02-design/data-model.md`（または database.md）を追加し、
    `sdd_sync.py` のマッピングに登録
  - `bitz-sdd` オーケストレーターのフェーズ表に sdd-data を組み込み
    （design と infra の間、review の対象に `.spec/design/data-model.md` を追加。
    `sdd-review/references/perspective-data-integrity.md` は既存なので観点追加は最小）
- **PR 5b: MVC + Database 対応の検証**
  - skill-tester / skill-evaluator で「MVC + DB の小規模題材（例: ToDo アプリ）」を使い、
    discovery → design（+data）→ infra → review → report が一気通貫で回るかを
    `evals/bitz-sdd/` に成果物として残して評価
- **完了条件**: 5a = 新スキルが validator チェックリスト PASS + sync 対象に組み込み済み。
  5b = eval レポートで「MVC + Database 対応」と判定。minor bump。

### Phase 7: Git / GitHub 開発フローの整備（P11）— Phase 5 と並行可

適用範囲は2層あり、両方を扱う。

- **PR 7a: BitzSkills リポジトリ自身の規約（AGENTS.md へ追記 + CI 強制）**
  - コミットコメント規定: Conventional Commits（`feat:` / `fix:` / `docs:` / `refactor:` /
    `test:` / `chore:` + scope はプラグイン名）、本文は日本語可。
    既存コミット（`feat: 3エージェント対応の...`）と互換なので移行コストは低い
  - マージ規定: PR は squash merge、マージコミットのタイトル = PR タイトル（Conventional
    Commits 準拠）、PR 本文テンプレ（目的 / 変更点 / 検証結果 = `release_check.py` の実出力）
  - Phase 0 の CI に commitlint 相当のタイトル検査を追加
- **PR 7b: `sdd-git`（新スキル、bitz-sdd 利用プロジェクト向け）**
  - 既存の `references/parallel-git.md`（ブランチ規約・競合の構造的回避・権限マトリクス）を
    土台に、実行スキルへ昇格させる。追加で規定する内容:
    1. **worktree 運用**: 複数エージェント並列時は「1エージェント = 1 worktree = 1ブランチ」を
       原則とし、共有チェックアウトへの同時書き込みを禁止。`.spec/tasks/` の depends_on が
       空のタスク群を worktree 単位で並列投入（parallel-git.md の並列スコープ規定と接続）。
       worktree の作成・削除・マージバックの定型手順を references 化
    2. **復元は worktree 破棄で行う（checkpoint 規定は置かない — 2026-07-10 確定）**:
       タスクが失敗したら worktree ごと破棄（`git worktree remove` + ブランチ削除）して
       タスクを再投入する。タスクは `.spec/tasks/` で小さく分解されている前提なので
       タスク単位のやり直しで十分であり、`git reset --hard` 禁止のガードレールとも衝突しない。
       エージェント固有の巻き戻し機能（Claude Code の rewind 等）はセッション内の
       即時 undo として自由に使ってよいが、スキルとしては規定しない。
       git 履歴は squash により「1タスク = 1コミット」を保つ
    3. **コミットコメント規定**: Conventional Commits + フッターに要件 ID
       （`Implements: XXX-FR-001`）。`spec_inspect.py` の implements マップと突合可能にする
    4. **GitHub Issue 駆動フロー（別リポジトリで開発する場合）**:
       Issue 起票 → `feat/<issue#>-<slug>` ブランチ → Draft PR → CI ゲート →
       レビュー → squash merge → Issue 自動クローズ（`Closes #N`）。
       `.spec/spec-issues/` と GitHub Issue の対応付け（spec-issue 側に issue URL を記録）
    5. **フロー選択の判断表**: 単独開発 = ブランチのみ / 複数エージェント並列 = worktree /
       別リポジトリ・チーム開発 = Issue 駆動 + PR、のように状況 → フローの対応を明記
  - sdd-implement（PR 5c）の並列実行規定と密接なため、5c の後に着手する
- **完了条件**: 7a = AGENTS.md 追記 + CI 検査が有効。7b = sdd-git が validator PASS、
  parallel-git.md との重複なし（統合 or 参照で一本化）。minor bump。

### Phase 8: BitzSkills 自身の SDD 化（ドッグフーディング）— Phase 5・7 完了後

「スキル・プラグインの開発そのものを sdd-core 準拠で行う」（2026-07-10 ユーザー確定）。

- **PR 8a: ワークスペース初期化と規約の要件化**
  - リポジトリルートに `.spec/` を作成（bitz-sdd のモノレポ対応 aec2833 を利用。
    ルート = 全プラグイン共通要件、`plugins/*` = 個別ワークスペース）
  - AGENTS.md の規約（命名規則・frontmatter 必須項目・2マニフェスト同値・自己完結原則）を
    EARS 要件として `.spec/requirements/` に起票し、`spec_inspect.py` で機械検証可能にする
    （AGENTS.md は人間向けナラティブとして残し、`.spec` がマスターという通常の SSOT 構造に載せる）
  - **軽量レーンの規定**: 小さなスキル修正は spec-issue → 要件 → タスクのみで回し、
    discovery / design はスキップしてよいことを sdd-core に明記（オーバーヘッド対策）
- **PR 8b: evals → .spec 提案フローの接続**
  - skill-evaluator / skill-improver の出口を変更: `evals/` の評価結果・観察ログの分析から
    導かれた改善提案を、直接修正ではなく `.spec/spec-issues/` への起票として出力する
  - 人間が spec-issue を要件化（draft → approved）して初めて実装に進む。これにより
    「improver の自動修正はコミット前に人間が diff 確認」のガードレールが、
    プロンプト依存から `.spec` の状態遷移による機械検証可能な形に昇格する
  - `evals/` は生データ収集層として現在地に維持（`.spec` へは移動しない）
- **ブートストラップ対策（重要）**: 自分に適用する bitz-sdd は**リリース済み（配置済み）
  バージョンに固定**し、開発中の作業ツリー版を自分に適用しない。sdd-core の破壊が
  開発プロセスの破壊に直結する自己参照を避ける
- **完了条件**: 8a = ルート `.spec/` で `spec_inspect.py` PASS、規約要件が最低5件起票済み。
  8b = evaluator / improver の SKILL.md 更新 + 実際に1件の改善提案が
  spec-issue → 要件 → 実装 → verified まで一周する。skill-creator は minor bump。

### Phase 6: 低優先の整理（後回しでよい）

- P8: plugin-creator の長大 SKILL.md（hook-development 420行ほか）を skill-optimizer で
  references/ へ分離（progressive disclosure）
- P7: frontmatter パーサ4実装に共通テストケース集（fixture）を当てて挙動を揃える
  （コード共有はしない — 自己完結規約を維持）
- `docs/調査報告/` の鮮度確認（各エージェントの仕様変化の追随）

### 先に着手 / 後回しの整理

- **先に**: Phase 0（安全網）> Phase 1（用語、並行可）> Phase 2（.spec 集約、小さく安全）
- **中盤**: Phase 3（リネーム + bitz-ddd 分離。テスト整備後でないと危険）> Phase 4（重複整理）
- **本丸**: Phase 5（Database + 実装・テスト工程。新規追加なので既存破壊リスクは低いが、量が最大）
- **並行**: Phase 7a（リポジトリ自身のコミット規約）は Phase 0 直後から可。
  Phase 7b（sdd-git）は PR 5c（sdd-implement）の後
- **後回し**: Phase 6 全部

---

## 4. リスクと対策

| リスク | フェーズ | 対策 |
|--------|---------|------|
| スキルリネームで発動しなくなる / 相互参照が切れる | 3 | 事前 grep で参照一覧を PR 説明に添付。実環境インストールで発動テスト。major bump + 移行注記 |
| `sdd_sync.py` 変更で利用プロジェクトの docs/.spec を破壊 | 2, 5a | Phase 0 の同期テストを先に整備。diff モードでのドライラン手順を SKILL.md に明記 |
| nexus 由来ドキュメントの取り込みでライセンス問題 | 0, 5a | 取り込み前に nexus-architect の LICENSE を確認。不明なら「蒸留（自分の言葉で再構成）」に限定し原文はリポジトリ外に退避 |
| 用語統一で技術的意味が変わる | 1 | glossary の「意訳禁止」規約を適用。用語置換のみ、文構造は変えない。diff レビューは用語単位 |
| bitz-ddd 分離後、SDD 単体で設計工程が回らなくなる | 3 | `sdd-design` に軽量デフォルト設計を必ず残し、「DDD 未インストールで discovery→report が完走する」ことを Phase 5b の eval で検証項目に含める |
| worktree 運用と既存のブランチ規約（STATE.md merge=ours 等）の衝突 | 7b | parallel-git.md を正として sdd-git はそれを拡張する形にする。矛盾が出たら parallel-git.md 側の改訂として扱い、二重規定を作らない |
| 2マニフェストの version 不整合 | 全 | 手編集禁止・必ず `bump_version.py`。CI の `release_check.py` で常時検知 |

## 5. レビュー方針

- 全 PR: `release_check.py` PASS（CI 化後は自動）+ 人間による diff 確認をマージ条件とする
- スキルの新規・変更を含む PR: skill-validator チェックリスト
  （`plugins/skill-creator/skills/skill-validator/references/checklist.md`）を通す
- Phase 3(命名) と Phase 5a(新スキル) はセルフレビューに加えて
  **antigravity:review によるクロスモデルレビュー**を推奨（判断は Claude が最終）
- 他エージェントの「成功しました」は信用せず、ゲート（pytest / release_check）を
  レビュアー自身が再実行する（AGENTS.md 検証義務どおり）

## 6. ロールバック方針

- 1フェーズ = 1 PR（Phase 5 のみ 2 PR）とし、`git revert` で丸ごと戻せる粒度を維持
- `main` 直コミット禁止（既存ガードレール）。フェーズブランチは
  `refactor/phase0-safety-net` のような命名で切る
- version bump はフェーズ PR の最終コミットで行い、revert 時に bump も一緒に戻す
- Phase 3 のリネームを revert する場合は、逆リネームの参照更新も機械的に可能なよう
  「変更マッピング表（旧名 → 新名）」を PR 説明に必ず残す
- 実環境（`~/.claude/skills/` 等）への配置は skill-packager 経由のみとし、
  ライブラリ側 revert 後に再配置すれば実環境も戻る

## 7. 実装をサブエージェント（実装AI）に渡す作業単位

> 原則: **仕様（このプラン + 対象ファイル一覧 + 完了条件）を1タスク1メッセージで渡し、
> 検証（pytest / release_check / validator）は必ず発注側が再実行する。**
> 判断を含む作業（命名規則の裁定、skill-development の存廃、蒸留の取捨選択）は渡さない。

| 単位 | 内容 | 向き先 | 判断の要否 |
|------|------|--------|-----------|
| W1 | pytest fixture + `sdd_sync.py` / `bump_version.py` / `release_check.py` のテスト一式生成 | サブエージェント向き（テスト網羅生成は得意領域） | 低 |
| W2 | GitHub Actions ワークフロー1本 | サブエージェント向き（定型） | 低 |
| W3 | glossary 照合の全 Markdown 一括レビューと修正候補列挙 | サブエージェント向き（機械的照合）。**適用判断は人間/Claude** | 中 |
| W4 | Phase 3 の参照一括リネーム（マッピング表を渡して機械置換） | サブエージェント向き。マッピング表作成は Claude | 低 |
| W5 | `sdd-data` スキルの references/assets ドラフト生成（nexus 蒸留元と構成指示を渡す） | サブエージェント向き。**SKILL.md 本文と工程への組み込みは Claude** | 高（分担） |
| W6 | Phase 5b の eval 実行（スキルあり/なし比較） | skill-tester の手順どおりサブエージェントで実行、採点は skill-evaluator | 中 |
| W7 | `sdd-implement` / `sdd-test` / `sdd-git` の references ドラフト生成（蒸留元 + parallel-git.md + 構成指示を渡す） | サブエージェント向き。**契約設計（.spec スキーマ・フェーズ表更新）は Claude** | 高（分担） |
| W8 | bitz-ddd への DDD 手法の移設（移設対象ファイル一覧と新スキル構成を渡して機械的に移動・参照更新） | サブエージェント向き。**分割境界の裁定と契約書式の明文化は Claude** | 中 |
| — | Phase 2（.spec 集約）、Phase 4（重複統廃合） | 小さく判断含みのため **Claude が直接実施**（委譲は割に合わない） | 高 |

## 8. PR 分割まとめ

1. `refactor/phase0-safety-net` — tests + CI + 資料退避（機能変更なし）
2. `refactor/phase1-glossary` — 用語統一（文言のみ、patch bump ×3）
3. `refactor/phase2-spec-consolidation` — sdd-report の `.spec/` 集約（minor bump）
4. `refactor/phase3-skill-naming` — 命名統一 + bitz-ddd 分離 + `.spec` 契約明文化
   （major bump、移行注記付き）
5. `refactor/phase4-dedupe` — skill-development / skill-reviewer 統廃合（minor bump）
6. `refactor/phase5a-sdd-data` — Database 設計スキル追加（minor bump）
7. `refactor/phase5c-implement-test` — sdd-implement / sdd-test 新設 + フェーズ表更新（minor bump）
8. `refactor/phase5b-mvc-db-eval` — MVC+DB 一気通貫 eval（evals/ 成果物のみ。5a/5c の後）
9. `refactor/phase7a-repo-git-conventions` — AGENTS.md コミット/マージ規定 + CI 検査
   （Phase 0 直後から可）
10. `refactor/phase7b-sdd-git` — sdd-git スキル新設（worktree / Issue 駆動フロー。
    5c の後、minor bump）
11. `refactor/phase8a-dogfood-spec` — ルート `.spec/` 初期化 + 規約の要件化（Phase 5・7 の後）
12. `refactor/phase8b-evals-to-spec` — evals → spec-issues 提案フロー接続（skill-creator minor bump）
13. `refactor/phase6-*` — 低優先整理（任意・随時）

## 9. 未確定事項（着手前にユーザー判断が必要）

1. ~~**オーケストレーター `bitz-sdd` をリネームするか**~~ → **解決済み（2026-07-10）**:
   `sdd-core` に改名し、新プラグインは `bitz-ddd`（スキルは `ddd-*`）とする（§Phase 3 参照）
2. ~~**nexus-architect 資料の退避先**~~ → **解決済み（2026-07-10）**: MIT License を確認のうえ
   `docs/調査報告/04.nexus-architect/` へ退避完了（§0 参照）
3. ~~**「すべてのスキルの情報は .spec に集約」の解釈**~~ → **解決済み（2026-07-10）**:
   2層構造で確定。①bitz-sdd 系スキルの成果物出力先は `.spec/` に一本化（Phase 2、当初解釈どおり）。
   ②さらに **BitzSkills 自身のスキル・プラグイン開発も sdd-core 準拠にする**（ドッグフーディング）。
   `evals/` は生データ（テスト結果・観察ログ）の収集層として現在地に残し、そこから導かれた
   改善提案を `.spec/spec-issues/` へ起票するフローで両者を接続する（新設 Phase 8 参照）
4. ~~**`sdd-data` を独立スキルにするか、`sdd-design` のステップ5として吸収するか**~~
   → **解決済み（2026-07-10）**: 独立の傘スキル `sdd-data` 1本 + references 構成で確定
   （DB 非使用システムを考慮し必須ステップにしない。RDB / NoSQL / ファイル形式 /
   オブジェクトストレージまで守備範囲。Phase 5a 参照）。
   あわせて `sdd-infra` → **`sdd-ops`** への改名も確定（Phase 3 のリネーム一括に含める）
5. ~~**コミットコメントの言語**~~ → **解決済み（2026-07-10）**: (a) で確定。
   タイトルは Conventional Commits（英語プレフィックス + scope はプラグイン名）、
   説明部は日本語可。既存コミットと互換（Phase 7a で AGENTS.md へ規定 + CI 検査）
6. ~~**checkpoint 運用の粒度**~~ → **解決済み（2026-07-10）**: checkpoint の規定自体を廃止。
   復元は「worktree ごと破棄してタスク再投入」に一本化（Phase 7b 参照）。
   これによりガードレール（reset --hard 禁止）との衝突・.spec 状態との整合・
   エージェント間機能差の裏取りがすべて不要になった
