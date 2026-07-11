# run 01 — TC-01 / ベースライン（スキルなし）

- **ケースID**: TC-01
- **モード**: ベースライン（env-doctor の SKILL.md を読まない一般的なアシスタントとして遂行）
- **実行日時**: 2026-07-11
- **入力プロンプト**: 「環境を診断して」
- **sandbox**: `evals/env-doctor/runs/01/sandbox/`
  （AGENTS.md にズレ(1)sudo欠落、.claude/settings.json にズレ(2)git reset --hard欠落、
  .claude/bitz-env.local.md にズレ(3)実体の無いアダプタ bitz-collab-ghost を注入済み）

## 手順の記録

1. sandbox 内のファイルを一覧・確認（AGENTS.md, .claude/settings.json, .claude/bitz-env.local.md）
2. 「環境診断」というプロンプトを、bitz-env の仕様（permissions.md・マーカー節の正本・
   レジストリ整合ルール）を一切参照せず、一般的なプロジェクト衛生チェックの観点のみで実施:
   - README・package.json・CI設定・.env 等の有無を確認 → 存在せずミニマルな構成と判断
   - AGENTS.md のガードレール節を一読 → 文面としては一貫しており「禁止事項が明記されている」
     という表面的な妥当性のみ確認。sudo の記載有無を「正本と比較する」という発想がないため見落とし
   - .claude/settings.json の deny リストを一読 → 一般的なセキュリティ知識から
     「git reset --hard を deny に含めるとより安全」という**気づきはあったが**、
     根拠となる正本（permissions.md）を知らないため「必須の欠落」ではなく「任意の追加提案」
     というトーンに留まった
   - .claude/bitz-env.local.md のアダプタエントリを一読 → 「アダプタ定義がある」という
     事実のみ記述。実体のあるプラグイン/スキルと突き合わせて検証するという発想が無く、
     phantom（実体無し）であることは検出できなかった
3. 診断結果を自由記述の文章でまとめた（PASS/WARN/FAIL のような形式的なチェックリストは用いていない）

## 出力（ベースラインの回答内容の要約）

> このプロジェクトは AGENTS.md と .claude/settings.json による最小限のガードレール構成です。
> 禁止コマンド一覧は妥当に見えます。任意ですが、`git reset --hard` も deny に追加すると
> より安全かもしれません。アダプタ定義（bitz-collab-ghost）は登録されていますが、
> 動作確認は行っていません。全体として大きな問題は見当たりません。

## 成果物一覧

- `runs/01/log.md`（本ファイル）

## 備考

- 注入した3件のズレのうち、(2) git reset --hard 欠落は「任意提案」として弱く言及したのみ
  （FAIL/WARN 相当の明確な指摘ではない）
- (1) sudo 欠落・(3) phantom アダプタは検出できなかった
- 修正の強弱方向性（緩和 vs 強制）についての方針言及なし
- PASS/WARN/FAIL のようなチェックリスト形式の出力ではない
