---
id: ENV-DSC-003
title: "スコープ（制約 → MoSCoW → In/Out-of-Scope 境界）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# ENV-DSC-003 スコープ

## 制約の棚卸し（最初にやる）

スコープ項目は下記制約に違反してはならない。違反するなら却下または延期する。

| 分類 | 制約 | 根拠 |
|---|---|---|
| 技術 | 同梱フックの deny は **普遍的最小集合**（rm -rf / git push --force / git reset --hard / git clean -f / sudo）に限定。プロジェクト固有制限は permissions 側 | ENV-CON-001 |
| 技術/移植性 | **両プラットフォーム**（Claude Code / Antigravity 2.0）で動くこと。単一 env_guard.py で吸収 | ENV-FR-002 |
| 契約 | 協調アダプタ契約（collab-contract.md）は公開契約。拡張は **後方互換**、破壊時のみバージョン up + 移行期間 | ENV-CON-002 |
| 組織/範囲 | 生成物・レジストリ・診断結果は **対象プロジェクト内に限定**。プロジェクト外書き込み禁止 | ENV-CON-003 |
| 設計思想 | ガードは **誤操作抑止であってセキュリティ境界ではない**。正規表現は回避可能である前提。恒久防御は permissions 層が担う | ENV-CON-004 |
| リソース | 個人開発。メンテ工数は作者の許容範囲に収める | 製作プラン |

## MoSCoW（帯域分け）

判定基準: 「これ以外を全部出荷したら、事故なく協調開発が回るか?」

### Must（なければ成立しない — すべて実装済み）

- 同梱フックによる破壊的操作5種の deny（ENV-FR-001, verified）
- プラットフォーム自動判別と判別不能時の安全素通し（ENV-FR-002, verified）
- env-init のユーザー確認付き生成（上書きせず diff 提示）（ENV-FR-003, verified）
- マーカー区間による安全な再生成（区間外は不変更）（ENV-FR-004, verified）
- モデル非依存の役割割り当て・劣化動作・防御的協調（ENV-FR-005, verified）
- env-doctor の3層同期診断（ENV-FR-007, verified）
- 生成物トラッキングと env-destroy による撤去（ENV-FR-010, verified）
- env-init 生成物の復旧可能性（git 前提 / バックアップ）（ENV-FR-009, verified）

### Should（価値は高いが滑れば外せる）

- **rules/*.md の両プラットフォーム読み込み**（ENV-FR-008, implementing）
  — Antigravity ネイティブ rules + Claude Code SessionStart フック注入。
  **実環境確認が残る**（後段 ENV-DSC-006 の未検証項目）
- 協調アダプタの契約チェック・登録・役割ルーティング（ENV-FR-006, verified）
- **共通ライフサイクルスキル標準への準拠**（init/doctor/update/uninstall）
  — SI-CORE-006。`env-destroy → uninstall` への改名は **人間裁定待ち**
- 依存関係宣言の標準化（SI-CORE-007。metadata.dependencies + release_check 検証）

### Could（あれば嬉しい磨き込み）

- `update` スキルの新設（現状は env-init 再実行で代替）
- 協調アダプタ契約の機能拡張（v3、後方互換前提）
- 診断・撤去のレポート出力の充実

### Won't（今回はやらない — 明示的除外。スコープクリープの最大のガード）

| 除外項目 | なぜやらないか |
|---|---|
| **回避不能なセキュリティ境界**（sandbox・悪意ある回避の防止） | ENV-CON-004。ガードは誤操作抑止に徹する。過剰約束は誤解を生む |
| deny 集合へのプロジェクト固有・組織固有ルールの追加 | ENV-CON-001。移植性を壊す。permissions 側で行う |
| ホーム等 **プロジェクト外への書き込み**・利用テレメトリ収集 | ENV-CON-003。プライバシーと移植性 |
| bitz-env 以外のプラグインのアンインストール・後始末 | env-destroy の責務境界。対象外と明記済み |
| 特定モデルに固定した協調設計 | ENV-FR-005。モデル非依存が中核価値 |

## In-Scope / Out-of-Scope 境界

| In-Scope | Out-of-Scope |
|---|---|
| 破壊的操作の常時ブロック（誤操作抑止） | 悪意ある回避の防止・完全な sandbox |
| permissions / AGENTS.md / CLAUDE.md 断片 / advisor・worker の生成 | プロジェクト固有ルールの deny への同梱 |
| 両プラットフォーム対応の単一フック | プラットフォーム外（他 IDE・CI 単体）への展開 |
| モデル非依存の協調運用3パターン + アダプタ契約 | モデル固定の協調・外部 SaaS 連携の内蔵 |
| 対象プロジェクト内での生成・追跡・撤去・復旧 | プロジェクト外への書き込み・利用状況収集 |
