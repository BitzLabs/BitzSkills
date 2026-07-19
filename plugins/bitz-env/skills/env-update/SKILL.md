---
name: env-update
description: env-init で展開済みの bitz-env 環境（settings.json の permissions・AGENTS.md / CLAUDE.md のマーカー区間・.claude/agents/ の advisor / worker・.claude/bitz-env.local.md レジストリ）を、ライブラリ側の最新バージョンへ安全に更新する。レジストリ記録の展開時バージョン D とライブラリ版 T を比較して差分のある生成物のみを更新し、CORE-CON-009 の累積マイグレーション機構でレジストリ・frontmatter 等の形式変更を移行する。「bitz-env を更新して」「環境を最新版に上げて」「env-update」「マイグレーションを適用して」と言われたとき、または bitz-env プラグインをバージョンアップした後に使用する。環境の展開は env-init、診断は env-doctor、撤去は env-uninstall が担当する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-19"
  updated: "2026-07-19"
---

# env-update

## 目的

env-init が展開した生成物（生成層）は、プラグインの更新に自動追従しない。本スキルは
CORE-CON-008 の update 最小契約（バージョン更新と依存再確認）と CORE-CON-009 の
累積マイグレーション機構（任意拡張）に準拠し、展開済み環境をライブラリ側の最新バージョンへ
**ユーザー確認付きで**安全に更新する。マイグレーション規約の正は plugin-creator の
`plugin-structure/references/migration-steps.md`。本スキルはその機構を bitz-env に実装する。

## バージョン軸

- **D**（配置先の現在バージョン）= レジストリ `.claude/bitz-env.local.md` の frontmatter
  `bitz-env-version` に env-init / env-update が stamp した bitz-env **プラグイン version**。
- **T**（移行先バージョン）= ライブラリ側（更新後の bitz-env プラグイン）の `plugin.json` の
  `version`（3マニフェスト共通の semver）。
- semver 比較は 3 整数分解 → major→minor→patch の数値比較（文字列比較しない。`0.10.0` >
  `0.9.0`）。これは skill-packager の semver 規約と同一軸で、スキル単位の `metadata.version`
  とは別軸である（責務境界は下記）。

## 原則

- **マーカー区間の外側は不変**。`AGENTS.md` / `CLAUDE.md` の
  `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->` 区間、および env-init が生成した
  ファイルのみを更新対象とし、ユーザー編集領域には一切触れない（区切りの空行1行も足さない）。
- **書き込み前に必ず dry-run 差分を提示し承認を得る**。配置先はリポジトリ外になりうる。
- **状態が判定できないときは安全側停止**。推測で書き込まない。
- **責務境界**: スキルファイル本体（SKILL.md・references）の置き換え可否判定は
  skill-packager（`skill-packager/references/lifecycle.md`）が担う。本スキルは
  「置き換え後の**配置先の状態・設定**（レジストリ／マーカー区間／frontmatter）をどう直すか」
  のみを規定する（二重規定の禁止）。

## ワークフロー

### 1. D と T の読み取り（書き込み前・読み取り専用）

1. レジストリ `.claude/bitz-env.local.md` を読み、frontmatter `bitz-env-version`（= D）を取得する。
2. ライブラリ側 bitz-env の `plugin.json` の `version`（= T）を取得する。
3. 次のいずれかなら **安全側停止**（変換せず状態と不足を提示。以降の書き込みへ進まない）:
   - D または T が semver として解釈不能。
   - **D が未記録**（レジストリに `bitz-env-version` が無い）= 展開時 version の stamp が無い
     旧レジストリ、または env-init 未実行。この場合は「D 不明のため差分更新・マイグレーションの
     基準が確定できない」と報告し、env-doctor による現状診断と、必要なら env-init 相当の
     再スタンプをユーザーに案内する（推測で D を補完しない）。
4. `D >= T` なら更新不要（同一版か降格）→ その旨を報告して終了。

### 2. 生成物の差分更新（マーカー区間内のみ）

`D < T` のとき、env-init のテンプレート（`references/permissions.md` /
`references/templates/`）の最新版と配置先の生成物を突き合わせ、**差分のある生成物のみ**を
更新する。更新対象と手順:

| 生成物 | 更新範囲 |
| --- | --- |
| `.claude/settings.json` | env-init テンプレート由来の permissions エントリのみ差分反映（ユーザー追加エントリは保持） |
| `AGENTS.md` / `CLAUDE.md` | マーカー区間内のみ再生成。区間外は不変 |
| `.claude/agents/advisor.md` / `worker.md` | env-init が生成したファイルのみ差し替え（存在するもののみ） |

差分が無い生成物はスキップする。すべての書き込みは手順4の承認後に行う。

### 3. マイグレーション（形式変更の累積移行）

`references/migrations/` のステップで、レジストリ・frontmatter 等**配置先に残す状態の形式変更**を
D→T へ移行する。詳細な解決手順は `references/migration-runbook.md`（規約の正は
plugin-creator の `migration-steps.md`）。要点:

1. `references/migrations/<from>-to-<to>.md` を全て集め、ファイル名から from/to を抽出して
   `to` 昇順にソートし、**適用候補** = `D < to <= T` を取る。
2. **適用候補が空**（`migrations/` が空、または D〜T 間に形式変更が無い）→ マイグレーション不要。
   手順2の差分更新のみで完了する（**初回出荷時は `migrations/` 空が正**）。
3. **連続性検査（dry-run・書き込み前）**: D が最古候補の `from` より古く接続ステップが無い、
   または隣接候補で `step[i].to != step[i+1].from` の断裂があれば → **安全側停止**。
4. 連続性 PASS なら `from` 昇順に**逐次適用**。各ステップは「guard 判定 → 未適用なら transform →
   verify」の順で実行する。verify 失敗はそのステップの rollback を実行して停止・報告する。

### 4. 書き込み前の承認フロー

手順2・3で確定した全変更について、**書き込み前に必ず**:

1. dry-run で変換対象ファイル一覧と before/after 差分プレビューを提示する。
2. 書き込み先の絶対パスと、それがリポジトリ内 / 外のいずれかを明示する。
3. 失敗時 rollback 用のバックアップ先を提示する。
4. **ユーザー承認を得るまで一切書き込まない**（バックアップ取得を含む実書き込みは承認後）。

書き込み先が作業中リポジトリ内（ドッグフーディング）の場合もリポジトリ外承認と同様に
dry-run 差分を提示し、デフォルトブランチへの直接コミット禁止のブランチ規律に従う。

### 5. 適用と stamp（承認後）

1. バックアップを取得する（git 管理外の対象は `<ファイル名>.bak`、git 管理下は git を復旧手段とする）。
2. 手順2の差分更新と手順3のマイグレーションを適用する。
3. **全ステップ成功後に**、レジストリ frontmatter `bitz-env-version` を D→T へ更新する
   （コミットマーカー。必ず最後に行う）。途中失敗時は D が旧値のまま残るため env-update は
   再実行可能で、guard により適用済みステップは no-op で通過し、修正後の再走で収束する。

### 6. 依存再確認と報告

- 更新後の環境について依存を再確認する: プラグイン同梱フックの有効性、`.claude/agents/` の
  advisor / worker の frontmatter 妥当性、レジストリ登録アダプタの実体（詳細診断は env-doctor に委ねてよい）。
- 更新した生成物・スキップした生成物・適用したマイグレーションステップ・レジストリの新バージョン
  （T）・依存再確認結果を報告する。

## 安全側停止の条件（変換せず停止し状態と不足を提示）

- (a) D または T が semver として解釈不能。
- (b) D が未記録（`bitz-env-version` 不在）で移行基準が確定できない。
- (c) D が最古ステップの `from`（baseline）より古く、その間を接続するステップが無い。
- (d) 適用候補チェーンに断裂がある（`step[i].to != step[i+1].from`）。
- (e) ステップの verify が不成立、かつ rollback 後も回復不能。
- (f) 変換対象ファイルが配置先に存在しない／パース不能で入力形式を判定できない。

(a)〜(d) は dry-run 段階で読み取りのみで検出でき、書き込み前に停止する。無視して先へ進めない。

## してはいけないこと

- ユーザー承認なしの書き込み（配置先がリポジトリ外なら特に）。
- マーカー区間の外にある既存記述の変更、および区間外への追記（区切りの空行1行も含む）。
- D 不明・チェーン断裂・semver 解釈不能を無視した書き込み。
- スキルファイル本体の置き換え可否判定への踏み込み（skill-packager の責務）。
- プロジェクト外（ホームディレクトリ等、レジストリが指す配置先を除く）への無承認操作。
