# 裁定記録 — SI-SDD-026 の採用と監査 baseline 設計の確定

- **日付**: 2026-07-29
- **対象ワークスペース**: `plugins/bitz-sdd`
- **裁定者（人間）**: hide
- **裁定の形式**: セッション内の対話裁定。「SDD の残件」提示に対し `SI-SDD-026 を進めましょう` で
  採用を指示。続けて実装前の設計3点（baseline 方式 / degrade 方針 / 検出範囲）を選択肢提示のうえ裁定
- **代行実行者（エージェント）**: claude-code
- **遷移**: `SI-SDD-026: open → accepted`

## 採用理由

`spec_inspect.py` の `check_state_events()` は、STATE の構造化 event を起点に
`events_by_artifact` を構築し、その辞書に載る artifact だけを現 status と照合する。
event が1件も無い artifact は走査対象に入らないため、frontmatter の `status` を
`spec update` を通さず直接書き換えても検査を素通りする。

実際にルートワークスペースで CORE 要件 26 件が無記録のまま `verified → promoted` へ遷移し、
`spec inspect` と `release_check.py` の両方が PASS して main へマージされた（`b96245f` で revert 済み）。
「人間裁定必須遷移を CLI が構造強制する」という SDD-FR-143 の中核価値が、
CLI を迂回しただけで事後検出すら不能になるため、採用する。

## 設計裁定（issue が実装の前提として要求していた3点）

### 1. 監査 baseline の与え方 → **案A（git ベース宣言）**

workspace の `.spec/PROJECT.md` に監査開始点をコミット SHA で宣言し、
**baseline..HEAD で `status:` 行が変化した artifact にのみ** event を必須化する。

- 採用理由: 既存 105 件（root 26 / bitz-sdd 56 / bitz-env 19 / bitz-ddd 2 / bitz-flow 2）への
  一括マーキングが不要で、監査機構導入以前の資産を violation として誤報しない
- 案B（artifact への `audit_baseline: pre-transaction` マーカー付与）を採らない理由:
  全件更新のコストに加え、マーカー自体が手編集対象の frontmatter 内にあり、
  status を手編集できる経路はマーカーも同時に書ける（検出力が baseline として弱い）

### 2. baseline 未宣言 / git 利用不可のときの挙動 → **未宣言は無検査、git 不可は WARN**

- `audit_baseline` の宣言が無い workspace は**従来どおり一切検査しない**（PASS）。
  監査は宣言したワークスペースのオプトイン機能とし、通常の inspect 経路を git 必須にしない
- 宣言済みだが git で判定できない場合（git 不在・shallow clone・baseline SHA 未解決）は
  **WARN**（FAIL にしない）。「監査したつもりで空振りしていた」状態を黙って通さないため
- SDD-FR-144 の fail-closed 方針は採らない。前提が異なる（FR-144 は ID 衝突という
  不可逆な統合事故の防止、本件は事後監査であり誤検知コストのほうが高い）

### 3. event 不在を violation と断定する範囲 → **人間裁定必須の到達状態のみ**

権限マトリクス上エージェント単独では到達できない遷移に限定する。証跡不在＝規律違反と
断定できるものだけを FAIL にする。

- requirement: `draft→approved` / `verified→promoted` / 任意 `→deprecated`
- spec-issue: `open→accepted` / `open→rejected` / `accepted→rejected` / `accepted→superseded`
- 対象外: `approved→implementing→verified`（エージェント権限で正当に到達可能）

## 確認観点への回答（issue「確認観点」節）

- **既存要件との矛盾**: なし。SDD-FR-143 の既存 EARS 節は変更せず**追加**で足りるため
  `bump`（2.0 → 2.1）とする。lifecycle.md の基準「その変更は既存の green なテストを red にし得るか」
  に対し No（追加節は新規テストで検証し、既存 9 節の意味は不変）
- **誤検知**: 設計裁定 1・2 により、baseline 未宣言のワークスペースと baseline 以前の
  status 変更はいずれも検査対象外。監査機構導入以前の要件は violation にならない
- **git 非依存性**: 案A は `check_state_events()` に git 依存を持ち込むが、
  `audit_baseline` 宣言時のみ git を呼ぶ。未宣言時は git を一切呼ばず、
  `integration_preflight()` と同様に失敗を握りつぶして degrade する
- **ガードレール**: 本裁定（accept 化）と SDD-FR-143 の bump はいずれも人間専権であり、
  本記録がその裁定の所在となる。エージェントは代行可視化経路で実行する
- **軽量レーン**: 不可（公開 CLI の判定結果と監査契約に触れる）。要件 bump → タスク → 実装 →
  unit-test の正規レーンで進める

## 残余リスク

- 案A の baseline は「宣言以降」の監査であり、宣言前に既に発生していた無記録遷移は検出しない。
  ルートで発生した事故（26 件）は `b96245f` で revert 済みのため実害は解消しているが、
  他ワークスペースの既存 non-draft 要件が正規経路で遷移したことの証明にはならない
- `audit_baseline` の宣言値そのものを後退させれば監査を無効化できる。PROJECT.md の
  改変はレビューで検出する運用に依存する（CLI では強制しない）
- git 履歴の書き換え（rebase / squash）で baseline SHA が失効すると WARN に落ちる。
  本リポジトリは squash merge 運用のため、baseline は main 上の到達可能な SHA を指定する
