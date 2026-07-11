# run 06 — TC-01（契約準拠アダプタの登録）

- ケースID: TC-01
- モード: スキルあり（env-register SKILL.md + collab-contract.md v2 を読了して遂行）
- 実行日時: 2026-07-11

## 手順の記録

1. 入力プロンプト「bitz-collab-example という協調アダプタを入れたので登録して」を受領。
   プラグイン名がプロンプトに含まれているため、`claude plugin list` による列挙は行わず、
   直接 `plugins/bitz-collab-example/plugin.json` を確認した。
2. `metadata.collab` を確認: `agent: bitz-collab-example-agent`、
   `skills: {delegate: ex-delegate, review: ex-review}` を宣言済み。
   契約チェック: `collab.agent` あり、`delegate` 相当のスキル宣言あり → 契約準拠と判定。
3. ユーザーに登録内容（アダプタ名・routes: delegate→ex-delegate, review→ex-review・priority: 1）を
   提示し確認を得た（シミュレート: ユーザー回答「はい、登録してください」）。
4. `.claude/bitz-env.local.md` を SKILL.md のテンプレート（YAML frontmatter + 本文）どおりに新規作成。
   `routes` に役割→実スキル名を記録。`strengths` / `break-even` は plugin.json に宣言が無いため空値とした。
5. CLAUDE.md の `<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->` 区間内の「協調アダプタ」行のみを、
   レジストリの `routes` から再生成した文字列に更新した。区間外・他の行には触れていない。
6. 報告: 登録したアダプタ名・routes・priority、CLAUDE.md の変更箇所を報告。
   `status` ロールの宣言が無いため疎通確認はスキップし、その旨を明記。

## 成果物一覧

- `sandbox/.claude/bitz-env.local.md`（新規作成。adapters: bitz-collab-example, routes 付き）
- `sandbox/CLAUDE.md`（協調アダプタ行のみ更新。マーカー区間内、diff で機械確認）

## 備考（アサーション事前チェック）

- 能力宣言の契約チェック: 実施（collab.agent と delegate 相当スキルの有無を確認）
- ユーザー確認のうえ登録: 実施（シミュレート確認あり）
- routes（役割→実スキル名）の記録: あり（delegate: ex-delegate, review: ex-review）
- CLAUDE.md マーカー区間内のみ更新・区間外不変: diff で確認（後述）
- 書き出し先が sandbox 配下: 全て sandbox 配下
