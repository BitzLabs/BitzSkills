# run 01 — TC-01（契約準拠アダプタの登録）

- ケースID: TC-01
- モード: ベースライン（env-register SKILL.md 未読、一般的アシスタントとして遂行）
- 実行日時: 2026-07-11

## 手順の記録

1. 入力プロンプト「bitz-collab-example という協調アダプタを入れたので登録して」を受領。
2. sandbox 内を確認: `plugins/bitz-collab-example/plugin.json` に `metadata.collab.agent` と
   `metadata.collab.skills.{delegate,review}` の宣言を発見。
3. 「協調アダプタ」を管理する仕組みが sandbox 内に明示的に存在しない（専用レジストリファイルなし）ため、
   CLAUDE.md 内の `<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->` マーカー区間にある
   「協調アダプタ」表セルのプレースホルダをそのまま更新することにした。
4. 契約準拠性の明示的なチェック（能力宣言の形式検証、delegate 役割の有無確認など）は行わず、
   plugin.json の存在確認のみで登録可と判断した。
5. ユーザーへの確認は取らず、そのまま CLAUDE.md を編集した。
6. `.claude/bitz-env.local.md` のような専用レジストリファイルは作成しなかった
   （そのような規約を知らないため）。

## 成果物一覧

- `sandbox/CLAUDE.md`（協調アダプタ行を `bitz-collab-example` に更新。マーカー区間内のみ変更）
- `.claude/bitz-env.local.md` は作成せず

## 備考（アサーション事前チェック）

- 契約チェック: 実施していない（plugin.json の存在確認のみ）
- ユーザー確認: 取っていない（無確認で直接編集）
- routes（役割→実スキル名）の記録: なし。delegate: ex-delegate 等の対応関係はレジストリに残っていない
- CLAUDE.md マーカー区間内のみ更新・区間外不変: 区間内のプレースホルダ1箇所のみ変更（後段で diff により機械確認）
- 書き出し先が sandbox 配下: 全て sandbox 配下（違反なし）
