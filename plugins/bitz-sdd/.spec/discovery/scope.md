---
id: SDD-DSC-003
title: "bitz-sdd スコープ（制約 → MoSCoW → In/Out 境界）"
status: draft
version: 1.1
updated: 2026-07-29
owner: hide
---

# スコープ — bitz-sdd


> **改訂 1.1（2026-07-29）**: SDD-REV-006 の GP-004（Discovery を実体へ追随させる）による改訂。
> 初版 1.0（2026-07-12）以降の実体変化を反映する。破棄せず改訂であり、判断の骨格は変えていない。
> **bitz-flow との依存境界と sdd-git 移管に関する記述は意図的に据え置く**
> （bitz-flow の設計が並行進行中のため、決定は同プラグイン完了後の最終合わせで行う。人間裁定）。

> 遡及的 discovery。既にリリース済みの実装をスコープとして追認しつつ、改修マスタープラン
> （`docs/improvement_master_plan.md`）の移管・分割予定を Won't / 移管予定に反映する。
> 初版執筆時 v1.4.6・11 スキル → **1.1 時点で v3.5.0・14 スキル**（sdd-plan / sdd-issue /
> sdd-doctor が加わった）。

## 制約の棚卸し（最初にやる）

| 分類 | 制約 |
|---|---|
| 技術 | Agent Skills オープン標準（agentskills.io）準拠。Claude Code / Antigravity 2.0 / OpenAI Codex CLI の3エージェント対応（**3マニフェスト構成**。SI-CORE-024）。各スキルはフォルダ単位でコピーされるため**自己完結必須**（他スキルの references を相対参照しない） |
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
- **人間裁定必須遷移の権限分離**（対話確認経路 / 代行可視化経路。SDD-FR-145）。
  裁定を人間の専権として保ちつつ、代行の可視化で実運用を止めないための中核契約。
- Claude Code / Antigravity 2.0 / Codex CLI 対応の配布形態（3マニフェスト）。

### Should（価値は高いが期限が滑れば外せる）
- データ格納設計（sdd-data）、運用・インフラ設計（sdd-ops）— 永続データ/運用を伴う案件のみ必須。
- 多観点レビュー（sdd-review）と進捗レポート（sdd-report）。
- 定型処理のスクリプト化（`spec_status.py` / `spec_scaffold.py` / `spec_update.py`。
  SI-CORE-011/012 — **実装済み**）。
- 検証結果の機械可読証跡（`spec_verify.py` / `.spec/verification/`。SI-SDD-016 — **実装済み**）。
- 環境診断（sdd-doctor）。依存プラグインとワークスペース前提の読み取り専用チェック。

### Could（あれば嬉しい磨き込み）
> 1.0 で Could に置いた3項目はいずれも **実装済み**。履歴として残し、消さない。

- ~~SPEC 3段階読み込みへの再構成（SI-CORE-013）~~ — **実装済み**。
- ~~フェーズ・ステータスの日本語表記化（SI-CORE-018）~~ — **実装済み**（`spec_labels.py`）。
- ~~sdd-plan / sdd-issue 新設（SI-CORE-016/017）~~ — **実装済み**。sdd-doctor も加わった。
- docs/ の日本語6章レイアウトと旧8章からの安全な移行（SI-SDD-012）— **実装済み**。

### Won't（今回は — 明示的に延期・除外）
- **本格 DDD 手法**（ドメインストーリーテリング・戦略/戦術設計・成熟度評価/MMI）は
  **bitz-ddd プラグインの責務**。bitz-sdd は軽量デフォルト設計に留める（導入時はそちらを優先）。
- **環境展開・ライフサイクル管理**（env-init 等）は **bitz-env の責務**。bitz-sdd は扱わない。
- **完全な形式検証・独自 ALM 統合・重量級プロセス**（anti-persona 向け）は狙わない。
- **収益機能・課金**（OSS・非収益）。
- **NSM 等の実測値自動収集基盤**（metrics.md の `TBD`。別 issue）。一部は `spec_status` /
  `sdd_report` / `.spec/verification/` で前進したが、目標値の設定と自動収集は未着手のまま。

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
  **2026-07-29 時点も未決**。bitz-flow の設計が並行進行中のため、決定は同プラグイン
  完了後の最終合わせで行う（人間裁定）。それまで sdd-git は In-Scope に留める。
- 14 スキルの責務分界（境界づけられたコンテキスト）が未定義 — SI-SDD-013 / SDD-REV-006 の SYN-008。
  スキルを増やす前に境界を定義する必要がある。
- sdd-data / sdd-ops を「必須でない Should」とする境界の顧客側期待 — `[proto / 未検証]`。
