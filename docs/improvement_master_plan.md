# BitzSkills 改修マスタープラン（2026-07-12）

ユーザー要望（bitz-flow 独立化 / 全プラグイン discovery / 定型処理スクリプト化 /
共通ライフサイクルスキル / SPEC 3段階読み込みと issue 委託フロー）に対する調査結果と実行計画。
**本計画の実行単位はルート `.spec/spec-issues/` の SI-CORE-004〜015**（status: open、人間裁定待ち）。

## 調査結果サマリ

| 観点 | 現状 |
|---|---|
| Git/GitHub フロー | `bitz-sdd:sdd-git`（v0.1.0、references 2枚）。規約の正は sdd-core の parallel-git.md |
| 個別 .spec ワークスペース | bitz-sdd / bitz-env のみ。bitz-ddd / plugin-creator / skill-creator は未設置 |
| 既存スクリプト | spec_inspect / docs_inspect / sdd_sync / sdd_report（スキル同梱）、bump_version / release_check / agy_guard（リポジトリ）|
| 未スクリプト化の定型処理 | 状況確認、要件/issue/タスクの採番・雛形生成、status 遷移、STATE.md 更新、worktree 操作、コミット規約検査、PR 本文生成 |
| 共通ライフサイクルスキル | bitz-env が env-init / env-doctor / env-destroy で先行。命名・契約は未標準化 |
| プラグイン間依存 | 宣言機構なし（bitz-ddd→bitz-sdd 依存等は description の文言のみ）。release_check も未検証 |
| issue 委託 | SI-CORE-003 でルート→サブの引き継ぎを手作業実施。フロー・書式は未規定 |

## 要望別の方針

### 1) bitz-flow 独立プラグイン化

sdd-git の内容（フロー選択・worktree 運用・Issue 駆動 PR・コミット規約・失敗時復元）を
`plugins/bitz-flow/` へ移管する。SDD 非採用プロジェクトでも単独で使える汎用 Git/GitHub
フロープラグインとし、bitz-sdd は bitz-flow に**依存宣言**（方針 4-3 の機構）して連携する。

- スキル構成案: `flow-core`（フロー選択・コミット規約）/ `flow-worktree` / `flow-pr`（Issue 駆動 + PR）
- 定型スクリプト: worktree_ops.py / commit_lint.py / pr_helper.py（方針 3 と連動、テスト先行）
- sdd-git は薄い委譲ポインタ化（または廃止）。裁定は SI-CORE-010 で人間が行う

### 2) 全プラグインへの sdd-discovery 実施

前提として bitz-ddd / plugin-creator / skill-creator に個別 `.spec/` ワークスペースを新設
（プレフィックス案: `DDD-` / `PLG-` / `SKC-`）。その後、各プラグインで sdd-discovery を実施し
`.spec/discovery/` に Vision / North Star / MoSCoW / JTBD / Go-No-Go を残す。
bitz-env / bitz-sdd は既存ワークスペースに discovery を補完。bitz-flow は新設時に実施。

### 3) 定型処理のスクリプト化（トークン削減）

原則: **決定的に再現できる処理はスクリプト、判断が要る処理だけスキル本文**。
エージェントは「スクリプトを実行して結果を読む」だけにし、毎回のコード生成トークンを削る。

| プラグイン | スクリプト | 役割 |
|---|---|---|
| bitz-flow | worktree_ops.py | worktree 作成/破棄/マージバックの定型操作 |
| bitz-flow | commit_lint.py | Conventional Commits + Implements フッター検査 |
| bitz-flow | pr_helper.py | PR 本文（目的/変更点/検証結果）の生成補助 |
| bitz-sdd | spec_status.py | 状況確認（要件/issue/タスク集計・フェーズ判定・次アクション）読み取り専用 |
| bitz-sdd | spec_scaffold.py | 要件/issue/タスクの採番付き雛形生成 |
| bitz-sdd | spec_update.py | status 遷移（権限マトリクス準拠）・STATE.md 更新 |
| bitz-ddd | mmi_score.py 等 | MMI 採点集計・成果物雛形生成 |

### 4) plugin-creator — 共通/独自スキルの分離

- **4-1 共通ライフサイクルスキル標準**: `<plugin>:init` / `doctor` / `update` / `uninstall` を
  標準名として制定（bitz-env の env-destroy → uninstall への改名は人間裁定）。
  plugin-creator に標準仕様 reference と雛形を追加し、ルート要件（CORE-CON draft）で規約化
- **4-2 独自スキル**: 従来の命名規則を維持。新規設計時は「スクリプト化できる定型処理を
  references/ でなく scripts/ に置く」ことを設計チェック項目にする
- **4-3 依存関係管理**: マニフェスト `metadata.dependencies` で宣言し、release_check.py が
  存在・循環を機械検証。init / update / doctor 時に依存確認を行う契約を標準に含める

### 5) SPEC 3段階読み込みと issue 委託フロー

- **3段階読み込み**: ①frontmatter description（常時ロード）→ ②SKILL.md 本文（薄く保つ）→
  ③references/scripts（必要時のみ）。bitz-sdd / bitz-ddd のスキルをこの構造に再整理し、
  `.spec/` 側も spec_status.py（方針 3）で「読まずに問い合わせる」形にして読み込み量を削減
- **issue 委託フロー**: spec-issue frontmatter に `origin` / `delegated_to`（ワークスペース指定）を
  追加。サブ→ルートはエスカレーション、ルート→サブは委任、**サブ間はルート経由を原則**
  （直接委託は依存宣言があるペアのみ許可する案を併記）。ルート SPEC 不在時はルート作成から
  始めるフローを正式化。spec_inspect.py に workspace 横断の整合チェックを追加

## ISSUE 分割計画（SI-CORE-004〜015）

分割原則: 1 ISSUE = 小さな変更量 / 動作変更と構造変更を混ぜない / テスト追加が先 /
後の ISSUE ほど前の ISSUE に依存（＝逆順 revert で安全にロールバック可能）。

| # | ID | 種別 | 内容 | 依存 |
|---|---|---|---|---|
| 1 | SI-CORE-004 | 構造(追加) | bitz-ddd / plugin-creator / skill-creator に個別 .spec 新設 | — |
| 2 | SI-CORE-005 | docs(追加) | 全既存プラグインへ sdd-discovery 実施 | 004 |
| 3 | SI-CORE-006 | 規約 | 共通ライフサイクルスキル標準（init/doctor/update/uninstall）制定 | — |
| 4 | SI-CORE-007 | テスト→動作 | 依存関係宣言の標準化 + release_check 検証（テスト先行） | 006 |
| 5 | SI-CORE-008 | 構造(追加) | bitz-flow スキャフォールド新設（sdd-git 内容の転記のみ） | 006 |
| 6 | SI-CORE-009 | テスト→動作 | bitz-flow 定型スクリプト群（テスト先行） | 008 |
| 7 | SI-CORE-010 | 動作変更 | sdd-git の bitz-flow 委譲化 + bitz-sdd 依存宣言 | 007,009 |
| 8 | SI-CORE-011 | テスト→動作 | bitz-sdd spec_status.py（読み取り専用、テスト先行） | — |
| 9 | SI-CORE-012 | テスト→動作 | bitz-sdd spec_scaffold.py / spec_update.py（テスト先行） | 011 |
| 10 | SI-CORE-013 | 構造のみ | bitz-sdd スキルの3段階読み込み再構成（内容不変） | 010,012 |
| 11 | SI-CORE-014 | 構造+動作 | bitz-ddd の3段階化 + 定型スクリプト化（テスト先行） | 013 |
| 12 | SI-CORE-015 | テスト→動作 | ルート/サブ SPEC の issue 委託フロー規定 + spec_inspect 対応 | 012 |
| 13 | SI-CORE-016 | スキル追加 | sdd-plan 新設（spec 現状把握と次アクション提案。spec_status.py の判断層） | 011 |
| 14 | SI-CORE-017 | スキル追加 | sdd-issue 新設（要望インテーク→予備判定→SI 起票。裁定は人間のまま） | 012,015,016 |
| 15 | SI-CORE-018 | 表示のみ | フェーズ・ステータスの日本語表記化（機械値は英語維持、表示層+入力正規化） | 011,012 |

追加要望（2026-07-12）: bitz-sdd に **sdd-plan**（現状把握と次アクション提案）と
**sdd-issue**（要望インテーク→可否の予備判定→SI 起票）を新設する。いずれも
SI-CORE-011/012 のスクリプトを実体とする薄い判断層スキルとし、裁定権（accepted 化）は
人間に残す。sdd-report（人間向け文書生成）/ sdd-core（規律の正）との責務境界は各 SI に記載。

各 ISSUE の目的・対象ファイル・確認観点・ロールバック手順は `.spec/spec-issues/SI-CORE-0XX.md` に記載。
実装着手は各 ISSUE の人間裁定（accepted 化）後、軽量レーンまたは通常フローで行う。
