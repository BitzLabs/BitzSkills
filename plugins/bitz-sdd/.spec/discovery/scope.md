---
id: SDD-DSC-003
title: "bitz-sdd スコープ（制約 → MoSCoW → In/Out 境界）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# スコープ — bitz-sdd

> 遡及的 discovery。既にリリース済み（v1.4.6・11 スキル）の実装をスコープとして
> 追認しつつ、改修マスタープラン（`docs/improvement_master_plan.md`）の移管・分割予定を
> Won't / 移管予定に反映する。

## 制約の棚卸し（最初にやる）

| 分類 | 制約 |
|---|---|
| 技術 | Agent Skills オープン標準（agentskills.io）準拠。Claude Code と Antigravity 2.0 両対応（2マニフェスト構成）。各スキルはフォルダ単位でコピーされるため**自己完結必須**（他スキルの references を相対参照しない） |
| 技術 | 同梱スクリプトは Python（uv 導入前提、pip/venv 不在）。決定的処理はスクリプト、判断のみスキル本文 |
| 組織 | 開発者は個人（hide）1名 + 将来 OSS コントリビュータ。重量級プロセスは維持コスト的に不可 |
| 運用 | モノレポの1プラグイン。共通規約の正はルート `.spec/`（CORE-）、bitz-sdd 固有は `SDD-` 名前空間 |
| ブートストラップ | bitz-sdd 自身の開発に適用する bitz-sdd は**リリース済み版に固定**（作業ツリー版を自分に適用しない） |
| 法規制 | OSS ライセンス下での配布。特段の法規制リスクは現時点で `TBD`（未精査） |

> スコープ項目は上記制約に違反してはならない。違反する場合は理由を明示して却下または延期する。

## MoSCoW（帯域分け）

### Must（なければプロダクトが成立しない）
- `.spec/` を単一の正とする EARS 要件運用と status ライフサイクル（sdd-core）。
- 機械検証 `spec_inspect.py`（カバレッジ / 孤児要件 / 幽霊参照 / `--workspace` 解決）。
- 上流探索ゲート（sdd-discovery）と設計工程（sdd-design）。
- 実装（sdd-implement：implements/depends_on/boundary 宣言）とテスト・検証（sdd-test）。
- `.spec/` ⇄ `docs/` 双方向同期（sdd-docs / `sdd_sync.py`）。
- Claude Code / Antigravity 2.0 両対応の配布形態。

### Should（価値は高いが期限が滑れば外せる）
- データ格納設計（sdd-data）、運用・インフラ設計（sdd-ops）— 永続データ/運用を伴う案件のみ必須。
- 多観点レビュー（sdd-review）と進捗レポート（sdd-report）。
- 定型処理のスクリプト化（spec_status.py / spec_scaffold.py / spec_update.py。SI-CORE-011/012 予定）。

### Could（あれば嬉しい磨き込み）
- SPEC 3段階読み込みへの再構成（SI-CORE-013、内容不変の構造整理）。
- フェーズ・ステータスの日本語表記化（SI-CORE-018、表示層のみ）。
- sdd-plan（現状把握と次アクション提案）/ sdd-issue（要望インテーク→予備判定）新設（SI-CORE-016/017）。

### Won't（今回は — 明示的に延期・除外）
- **本格 DDD 手法**（ドメインストーリーテリング・戦略/戦術設計・成熟度評価/MMI）は
  **bitz-ddd プラグインの責務**。bitz-sdd は軽量デフォルト設計に留める（導入時はそちらを優先）。
- **環境展開・ライフサイクル管理**（env-init 等）は **bitz-env の責務**。bitz-sdd は扱わない。
- **完全な形式検証・独自 ALM 統合・重量級プロセス**（anti-persona 向け）は狙わない。
- **収益機能・課金**（OSS・非収益）。
- **NSM 等の実測値自動収集基盤**（metrics.md の `TBD`。別 issue）。

### 移管予定（現在は bitz-sdd 内だが将来切り出す — Won't に準じる）
- **Git / GitHub 開発フロー（sdd-git）**は **bitz-flow プラグインへ移管予定**
  （`docs/improvement_master_plan.md` の方針 1 / SI-CORE-008・010）。
  bitz-flow 新設後、sdd-git は薄い委譲ポインタ化または廃止し、bitz-sdd は
  bitz-flow へ**依存宣言**（SI-CORE-007 の `metadata.dependencies` 機構）して連携する。
  それまでの間、worktree 運用・コミット規約・Issue 駆動 PR は暫定的に bitz-sdd の
  In-Scope に留まる。

## In-Scope / Out-of-Scope 境界（必須）

| 項目 | In / Out | 理由 |
|---|---|---|
| EARS 要件・status ライフサイクル・機械検証 | **In** | Must。プロダクトの核 |
| 設計（軽量デフォルト）/ データ / 運用設計 | **In** | Must/Should |
| `.spec` ⇄ `docs` 同期・進捗レポート・多観点レビュー | **In** | Must/Should |
| Git/GitHub フロー（worktree・コミット規約・PR） | **In（暫定）→ 移管予定** | 現状 sdd-git。将来 bitz-flow へ |
| 本格 DDD（ストーリーテリング・戦略設計・MMI） | **Out** | bitz-ddd の責務 |
| 環境展開・ライフサイクルスキル | **Out** | bitz-env の責務 |
| 収益・課金・独自 ALM 統合・重量級形式手法 | **Out** | 非収益 OSS / anti-persona |
| 指標の実測自動収集基盤 | **Out（現時点）** | 別 issue、`TBD` |

## Open Questions
- bitz-flow 移管後の bitz-sdd↔bitz-flow 依存境界の粒度 — SI-CORE-010 で人間裁定。
- sdd-data / sdd-ops を「必須でない Should」とする境界の顧客側期待 — `[proto / 未検証]`。
