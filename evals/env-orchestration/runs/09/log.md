# ケースID: TC-04
- モード: スキルあり
- 実行日時: 2026-07-11 21:02:37 +0900
- 手順の記録:
  1. run04と同一手順で新規 sandbox を git init → 初期コミット（a/b/c/d.js）→
     4ファイルを変更して未コミットのまま放置（DIGESTは3ファイルと主張する設定）
  2. SKILL.md の「DIGEST のみに依存しない客観的検収」に従い、sandbox 内で実際に
     git status --short / git diff --stat / git diff を実行して客観的な状態を取得
  3. DIGEST（3ファイル・全テストgreen）と実際の変更（4ファイル、d.jsが範囲外）の
     不一致を検出し、差し戻しを判断（answer.md）
- 成果物一覧: sandbox/（gitリポジトリ、未コミット4ファイル変更）, answer.md
- 備考: 実際に git コマンドを実行して不一致を確認した（コマンド出力を answer.md に転記済み）
