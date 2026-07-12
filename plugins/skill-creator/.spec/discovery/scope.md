---
id: SKC-DSC-003
title: "skill-creator スコープ（制約 → MoSCoW → In/Out 境界）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# スコープ（制約 → MoSCoW → In/Out-of-Scope 境界）

> 遡及 discovery。すでに実装済みの 10 スキルを MoSCoW に整理し、明示的な
> Out-of-Scope（Won't）を残してスコープクリープを止める。改修マスタープラン
> （docs/improvement_master_plan.md）で skill-creator に関わる方針をスコープに反映する。

## 制約の棚卸し（最初にやる）

| 分類 | 制約 |
|---|---|
| 技術 | 各スキルはフォルダ単位でコピーされるため**自己完結必須**。他スキルの `references/` を相対参照しない（AGENTS.md 規約） |
| 技術 | frontmatter 仕様の正は `plugins/skill-creator/skills/skill-creator/references/spec.md`。全スキルに `metadata`（version/author/created/updated）必須 |
| 技術 | Claude Code と Antigravity 2.0 の**両対応**（配置パスの正は skill-packager の platform-paths.md） |
| 組織 | 主要ユーザーは個人開発者本人。対話 UX は「1人で回せる」前提でよい |
| プロセス | 本モノレポの改修は sdd-core 準拠（ドッグフーディング）。skill-creator 変更は `SKC-` 名前空間で起票 |
| プロセス | improver によるスキル自動修正は**コミット前に人間が diff 確認**。自動コミットしない |

**スコープ項目は制約に違反してはならない**。特に「自己完結」を破る共通化は却下する。

## MoSCoW（帯域分け）

判定基準:「これ以外を全部出したら成功指標（検証済み稼働スキル数）を達成できるか?」

### Must（なければプロダクトが成立しない = MVP）

- **skill-creator** — スキル（SKILL.md + フォルダ）の対話的作成。すべての起点。
- **skill-validator** — Agent Skills 仕様準拠のチェックリスト検査。品質の門番。
- **skill-packager** — ライブラリ→実環境（Claude Code / Antigravity / プラグイン）配置・
  version 比較更新・アンインストール・配布。作っても配れなければ価値ゼロ。

### Should（価値は高いが期限が滑れば外せる）

- **skill-tester** — スキルあり/なしベースライン比較の実行と `evals/` 保存。
- **skill-evaluator** — テスト結果の採点と report.md 生成（効果の可視化）。
- **skill-pipeline** — 全工程のオーケストレーション／案内。

### Could（磨き込み。時間が足りなければ最初に切る）

- **skill-optimizer** — description 発動精度改善・progressive disclosure 分離・圧縮。
- **skill-instrumenter** — 自己観察ステップの注入／除去（計装）。
- **skill-observer** — 実行結果の自己観察と observations.jsonl への追記。
- **skill-improver** — 観察ログ分析→ `.spec/spec-issues/` 起票（自己改善の総仕上げ）。

（注: instrumenter/observer/improver は「自己改善ループ」として価値が高いが、
コア価値＝作成・検証・配置の外側にある磨き込みのため Could に置く。実装済みである点は
遡及事実として記載。）

## In-Scope / Out-of-Scope 境界

### In-Scope

- Agent Skills 標準（agentskills.io）準拠スキルの、作成・検証・テスト・評価・最適化・
  配置・自己改善の全工程支援。
- Claude Code / Antigravity 2.0 両プラットフォームへの配置。
- スキル単体の品質と効果（あり/なし比較）に閉じた測定。

### Out-of-Scope（Won't — 今回はやらない。理由つき）

| Won't 項目 | なぜやらないか |
|---|---|
| **プラグイン全体の構造・コマンド・エージェント・フック・MCP の設計** | plugin-creator プラグインの責務。skill-creator はスキル（skills/）に閉じる |
| **SDD ワークフロー（要件・タスク・実装・検証）の運用** | bitz-sdd の責務。improver は起票までで、要件化・裁定は人間＋sdd-core |
| **DDD（ドメインモデリング・成熟度評価）** | bitz-ddd の責務 |
| **Git/GitHub フロー（worktree・PR・コミット規約）** | sdd-git（将来 bitz-flow, SI-CORE-008）の責務。skill 配布はするが VCS 運用はしない |
| **スキルを横断する共通 references の集約・DRY 化** | 自己完結制約（フォルダ単位コピー）を壊すため恒久的に非対象 |
| **改修マスタープランの共通ライフサイクルスキル標準（init/doctor/update/uninstall）の制定** | SI-CORE-006 のルート規約側マター。skill-packager の配置機能とは別レイヤー |
| **エンドユーザー向けスキル実行ランタイム／実行環境の提供** | 実行は各エージェント基盤（Claude Code 等）の責務。本プラグインは開発ツール |
| **商用課金・ライセンス管理・マーケットプレイス運営** | 非商用の個人開発＋OSS 公開が前提 |

## 改修マスタープランの反映（skill-creator 関連）

- 個別 `.spec/` ワークスペースは SI-CORE-004 で新設済み（プレフィックス `SKC-`）。
- 本 discovery は SI-CORE-005 の一環。以後の skill-creator 変更は `SKC-` で通常 SDD フロー。
- SI-CORE-006（共通ライフサイクルスキル標準）は skill-packager の配置と隣接するが、
  規約制定はルート側で行うため本プラグインのスコープ外（上表 Won't 参照）。
