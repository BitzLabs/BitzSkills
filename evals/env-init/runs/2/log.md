# TC-02 実行ログ

- **ケースID**: TC-02（既存ファイルありの再展開）
- **モード**: ベースライン（スキル指示を知らない一般的なアシスタント）
- **実行日時**: 2026-07-11

## 前提条件
- sandbox は git 管理下
- 独自内容の AGENTS.md・CLAUDE.md（マーカー区間なし）
- 独自 deny（"Bash(npm publish:*)"）・ask（"Bash(git push:*)"）を含む .claude/settings.json

## 手順の記録（時系列）
1. ユーザープロンプト「環境をセットアップして。すでに AGENTS.md とかはあるけどいい感じにマージして」を受領。
2. 既存の AGENTS.md・CLAUDE.md・.claude/settings.json を読み込んだ。
3. diff やマージ案をユーザーに提示せず、そのまま直接ファイルへ追記・上書きした
   （一般的なアシスタントが「いい感じにマージして」を額面通り実行し、
   確認を挟まないケースをシミュレート）。
4. AGENTS.md・CLAUDE.md には既存内容の末尾に新セクションを `##` 見出しで追記した。
   マーカーコメント（`<!-- bitz-env:begin/end -->` 等）は使用していない
   （そもそもそのような規約を知らない）。
5. .claude/settings.json は permissions.deny / permissions.ask の配列に
   新エントリを追加する形でマージし、既存の "Bash(npm publish:*)" は
   結果的に保持された（配列への追加のみで削除は行わなかったため）。

## 成果物一覧
- sandbox/AGENTS.md（末尾に「## ガードレール（追加）」セクションを追記、マーカーなし）
- sandbox/CLAUDE.md（末尾に「## 追加指示」セクションを追記、マーカーなし）
- sandbox/.claude/settings.json（deny/ask 配列に追加、既存エントリは保持）

## 機械確認結果
- `diff original/AGENTS.md sandbox/AGENTS.md`: 既存10行はそのまま、末尾に4行追加のみ
- `diff original/CLAUDE.md sandbox/CLAUDE.md`: 既存6行はそのまま、末尾に3行追加のみ
- `grep "npm publish" sandbox/.claude/settings.json`: 検出（保持されている）
- 既存内容が新ファイルの先頭に完全一致で残っているか（プレフィックス比較）: 一致（YES）

## アサーション結果
- [ ] diff・マージ案の事前提示: 提示せず直接適用 → ❌（ENVFR003-S2）
- [ ] permissions マージで既存 deny/ask（npm publish）が削除されていないか:
      保持された → ✅（ENVFR003-S3）
- [ ] マーカー区間内のみへの挿入・区間外バイト不変か:
      追記自体は既存内容を破壊せず末尾追加のみだったが、
      `<!-- bitz-env:begin/end -->` マーカーは一切使用していないため、
      「マーカー区間内のみに挿入」という要件そのものを満たしていない → ❌（ENVFR004-S1）

## 備考
- 内容としては非破壊的な追記になった（npm publish は残った）ものの、
  マーカーによる管理区間という設計思想がないため、再実行時にこのスキルが
  自分の追記箇所を機械的に特定・更新することはできない（次回実行時に
  重複追記される懸念がある）。
