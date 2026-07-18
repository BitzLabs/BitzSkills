---
id: ENV-DSN-001
version: 1.1
status: approved
domain: deploy
origin: 製作プラン（2026-07-11 人間承認済み）からの移送
---

# ENV-DSN-001 bitz-env アーキテクチャ

製作プラン（人間承認済み）の設計部分を `.spec/` へ移送したもの。実装 v0.1.0 の根拠。

## 可否判定の要点（設計の前提）

- permissions（settings.json の deny/allow）はプラグインで直接配布**できない**
  → PreToolUse フックで実行時ブロック + env-init が permissions を生成、の2層で代替
- サブエージェントのモデルエイリアスは Claude Code 固有 → 雛形配布 + セットアップ時選択
- Claude Code のプラグイン `rules/` 自動マージは仕様上未確認 → ルール文書は生成方式が確実

## 2層構造

| 層 | 実体 | 効き始め | 特性 |
|---|---|---|---|
| 即効層 | 同梱 PreToolUse フック（hooks/hooks.json + hooks.json + scripts/env_guard.py） | プラグイン有効化直後 | プロジェクトに書き込まない。プラグイン無効化で消える |
| 生成層 | env-init が生成する permissions / AGENTS.md / CLAUDE.md 断片 / advisor・worker | env-init 実行後 | プラグイン無効時も効く恒久層。更新に自動追従しない（env-doctor が差分検出） |

同一ガードレールの意図的な二重化。3層（permissions ⇔ フック ⇔ ナラティブ）の
同期ズレは env-doctor の診断対象（ENV-FR-007）。

## ガード共通ロジック（env_guard.py）

- 1スクリプトで両プラットフォーム対応。stdin の JSON 形状で自動判別（ENV-FR-002）
- Claude Code: `hooks/hooks.json`（ラッパー形式・snake_case・`${CLAUDE_PLUGIN_ROOT}`）
- Antigravity: ルート `hooks.json`（camelCase・matcher `run_command`・相対パス。
  `${CLAUDE_PLUGIN_ROOT}` 相当が無いため cwd = hooks.json の場所を前提）
- deny は普遍的最小集合に限定（ENV-CON-001）。ガードの故障は素通し（fail-open）—
  恒久層（permissions）が二重に守るため、フック側は可用性を優先する

## モデル非依存の協調運用

- 中心 = ユーザー選択モデル。役割は相対定義（advisor / worker）。ENV-FR-005
- 3パターン: 委譲型（中心→worker）/ 相談型（中心→advisor、最終判断は中心）/
  合議型（複数へ並列諮問、裁定は多数決でなく中心。発動条件は高影響判断に限定）
- 劣化動作の連鎖: 合議不成立→相談型へ格下げ→advisor 不在→単独判断（明記付き）

## 協調アダプタ機構

- ハブ＆アダプタ。契約 = collab-contract.md v2（公開契約・後方互換拡張 ENV-CON-002）
- 連携は「契約（役割スキル + metadata.collab 能力宣言）+
  プロジェクト内レジストリ `.claude/bitz-env.local.md`」の疎結合
  （プラグイン同士は相互のファイルを参照できないため）
- bitz-env はアダプタゼロでも完全に機能する（純粋追加式）

### 役割ルーティング（SI-ENV-005 / 契約 v2）

- 固定スキル名（delegate / review / status）の直接呼び出しは複数アダプタ共存で
  グローバル名前空間が衝突するため廃止。レジストリに
  「標準の役割 → 当該アダプタの実スキル名」のルーティングテーブルを記録し、
  env-orchestration はレジストリ経由で委譲先を解決する（ENV-FR-006 v1.1）
- 登録時の名前衝突はアダプタ名プレフィックスで名前空間化し、優先順を明示
- v1 の固定名アダプタ（antigravity 等）は「役割 = 実スキル名」の自明な
  ルーティングとして登録すれば引き続き準拠（移行パス。ENV-CON-002 と整合）

### 防御的協調（SI-ENV-007）

- 検収: 中心は worker の DIGEST（自己申告）のみに依存せず、git diff / git status 等の
  客観的状態変化を自ら取得して検証する（ENV-FR-005 v1.1）。
  collab-contract 第3項の「検収は中心の義務」を客観的手段で具体化
- 再帰ストッパー: worker / advisor からのネスト委譲は禁止（depth = 1）。
  追加委譲の要否は常に中心が判断する。深さカウンタ方式より単純で、
  「裁定は中心」の設計原則とも一致するため flat 禁止を採用

## ライフサイクル（生成・診断・撤去）（SI-ENV-006）

- 生成層はプラグイン無効化後も残留するため、ライフサイクル全体を管理する:
  env-init（生成 + レジストリへの生成物トラッキング）→ env-doctor（差分診断）→
  env-uninstall（ユーザー確認付き撤去。ENV-FR-010。旧名 env-destroy）
- 撤去はマーカー区間のみ除去し、ユーザー自身の記述を保持。レジストリ欠落時は
  推測削除せず候補報告に留める（安全側）。ENV-FR-009（バックアップ）と対
- 撤去対象はプロジェクト内限定（ENV-CON-003）

## rules/*.md の読み込み（設計決定 2026-07-11）

Claude Code はプラグインの `rules/` を公式サポートしない（plugins-reference の
コンポーネント一覧に無し）。一方 SessionStart フックの stdout はコンテキストへ
自動追加される（公式仕様: hooks-guide）。よって rules/*.md は
**Antigravity = ネイティブ rules / Claude Code = SessionStart フック注入**の
二経路で両プラットフォームに読み込ませる（ENV-FR-008、人間裁定）。

## フック同意ダイアログの扱い（設計決定 2026-07-11）

bitz-env が独自の同意ダイアログを設ける必要はない（人間裁定）。両フックは
「破壊的操作をブロックする／ルール文書を注入する」のみで、ユーザーに代わる実行・
外部送信などの危険な代理動作を持たない。フック実行への信頼はインストール操作
（`/plugin install`）が既に担保している。Claude Code が同意を出す仕様なら
ユーザーがその場で判断でき、出さない仕様でも README にフックの内容と限定的な
動作範囲を明記することで透明性を担保する（README「注意事項」に記載済み）。
→ 要検証項目#1 は「不要」に格下げ。実環境での挙動確認は任意。

## 要検証項目（実環境での実測待ち）

1. ~~プラグイン有効化時のフック同意ダイアログの有無~~ → 設計解決（上節）。新要件不要・README で透明性担保
2. ~~Claude Code でのプラグイン内 `rules/*.md` の読み込み挙動~~ → 設計解決（rules 節・ENV-FR-008）。
   実環境での注入確認のみ残
3. 展開先の既存フックとの共存（二重発火）
4. セッション内からの有効プラグイン一覧の取得手段（不能なら手動登録フォールバック）

## 設計判断（ADR / REV-001 反映）

### ADR-1: フックを fail-open にする（SI-ENV-001 / RSK-201）

- **選択**: env_guard.py はパース不能・故障時に `{}`（素通し）を返す。
- **却下案**: fail-safe（故障時に deny）。全 Bash をブロックし開発を止めるため却下。
- **前提と補償**: フックは即効層にすぎず、恒久的防御は env-init が生成する permissions 層が担う。
  したがって「フック＋permissions の二重化」は **env-init 実行済みが前提**。未実行環境では
  フックが単独防御になるため、env-doctor が permissions 層の不在を WARN する（ENV-CON-004）。

### ADR-2: ガードは誤操作抑止でありセキュリティ境界ではない（SI-ENV-001 / RSK-202）

- 正規表現検出はコマンド置換・エンコード・環境変数展開で回避可能。これを前提とし、
  ドキュメント・スキルで「誤操作抑止であってセキュリティ境界ではない」と明示する（ENV-CON-004）。
  plugin-agents の「tools 制限にセキュリティを依存させない」と同じ思想。

### 検証接続の方針（SI-ENV-002 / RVC-201）

- ENV-FR-003〜007・009 の example-test は evals/env-*/ の実体作成（skill-tester 工程）で接続する。
  接続前は各要件を verified に昇格させない。spec_inspect は example-test の実体不在を検出しない
  ため、verified 化の際は evals/ の存在を人手で確認する。
