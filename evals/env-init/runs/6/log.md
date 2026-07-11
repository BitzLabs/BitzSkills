# TC-02 実行ログ（スキルあり）

- **ケースID**: TC-02（既存ファイルありの再展開）
- **モード**: スキルあり（SKILL.md + references/permissions.md, templates/* に忠実）
- **実行日時**: 2026-07-12

## 前提条件
- sandbox は git 管理下（README なし、既存3ファイルをコミット済み）
- 独自内容の AGENTS.md・CLAUDE.md（マーカー区間なし）
- 独自 deny（"Bash(npm publish:*)"）・ask（"Bash(git push:*)"）を含む .claude/settings.json

## 手順の記録（時系列）
1. ユーザープロンプト「環境をセットアップして。すでに AGENTS.md とかはあるけどいい感じにマージして」を受領。
2. SKILL.md 手順1に従い、プラットフォームをユーザーに質問 → シミュレート回答「Claude Code」。
3. 既存ファイルの有無を確認 → `.claude/settings.json` / `AGENTS.md` / `CLAUDE.md` は存在、
   `.claude/agents/` は存在しない。
4. Git リポジトリか確認 → 既に git 管理下（初期コミット済み）。
5. 手順2（書き込み前チェック）: git 管理下のため `.bak` 作成は省略可 → 省略。
6. 手順3（中心モデルと役割の割り当て）: ユーザーに中心モデルを質問
   → シミュレート回答「Sonnet（中位）」。表に従い advisor=Opus, worker=Haiku を提案
   → シミュレート承認。
7. 手順4（生成、すべて確認付き）: 書き込み**前**に以下のマージ案を提示した
   （この時点でファイルへは一切書き込んでいない）。
   - `.claude/settings.json`: 既存 deny/ask を残したまま、references/permissions.md の
     テンプレート deny 8件・allow 8件を和集合として追加する案（ask の
     "Bash(git push:*)" は既存と重複するため追加しない）
   - `AGENTS.md`: 既存10行の末尾に `<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->` の
     ガードレール節を追記する案（既存記述は一切変更しない）
   - `CLAUDE.md`: 既存6行の末尾に同様のマーカー区間で協調運用節を追記する案
   → シミュレート承認を得てから、上記の内容で実際に書き込みを行った。
8. `.claude/agents/advisor.md`（model: opus）・`.claude/agents/worker.md`（model: haiku）を
   新規生成（表の規則どおり、中心が中位のため両方生成）。
9. 手順5（生成物トラッキング）: `.claude/bitz-env.local.md` を新規作成し、
   新規生成ファイル一覧・マーカー区間の位置・settings.json のマージ内容・
   バックアップ有無（今回は不要）・割り当てを記録した。
10. 手順6（検証と報告）: `python3 -m json.tool .claude/settings.json` でパース確認 → 成功。

## 成果物一覧
- sandbox/.claude/settings.json（既存 deny/ask を保持したままテンプレートと和集合マージ）
- sandbox/AGENTS.md（既存10行はそのまま、末尾にマーカー区間付きで追記）
- sandbox/CLAUDE.md（既存6行はそのまま、末尾にマーカー区間付きで追記）
- sandbox/.claude/agents/advisor.md（model: opus）
- sandbox/.claude/agents/worker.md（model: haiku）
- sandbox/.claude/bitz-env.local.md（レジストリ）

## 機械確認結果
- `diff <(head -n 10 sandbox/AGENTS.md) original/AGENTS.md`: 差分なし（既存10行完全一致）
- `diff <(head -n 6 sandbox/CLAUDE.md) original/CLAUDE.md`: 差分なし（既存6行完全一致）
- `head -c <original size> sandbox/AGENTS.md | cmp - original/AGENTS.md`: 一致
  （既存部分がバイト単位で不変であることを確認）
- `head -c <original size> sandbox/CLAUDE.md | cmp - original/CLAUDE.md`: 一致（同上）
- `grep "npm publish" sandbox/.claude/settings.json`: 検出（既存 deny エントリ保持）
- `python3 -c "json.load(...)['permissions']['ask']"`: `['Bash(git push:*)']`
  （重複追加されていない。既存の1件のみ）
- `python3 -m json.tool sandbox/.claude/settings.json`: JSON valid
- `grep -c "bitz-env:begin" sandbox/AGENTS.md sandbox/CLAUDE.md`: 各1件確認
- 全成果物パスが `sandbox/` 配下であることを `find` で確認

## アサーション結果
- [x] 既存ファイルを上書きせず、diff とマージ案を提示している → ✅（ENVFR003-S2）
  証拠: 手順7で書き込み前にマージ案（settings.json の和集合案、AGENTS.md/CLAUDE.md の
  追記案）を提示し、承認後に書き込んだ。書き込み前の sandbox は original/ と同一。
- [x] permissions のマージで既存の deny/ask エントリ（npm publish）が削除されていない
  → ✅（ENVFR003-S3）。証拠: grep で "Bash(npm publish:*)" が sandbox/.claude/settings.json
  内に残存を確認。
- [x] CLAUDE.md / AGENTS.md への挿入はマーカー区間内のみで、区間外の既存記述が
  バイト単位で不変 → ✅（ENVFR004-S1）。証拠: `head -c` + `cmp` で既存部分の
  先頭バイト列が original/ と完全一致することを確認。マーカーはともに1件のみ検出。

## 備考
- スキルありでは、書き込み前にマージ案を提示するという原則（SKILL.md「原則」節）が
  ワークフロー上の手順4に明記されているため、ベースライン実行（runs/2, ENVFR003-S2/S4/ENVFR004-S1が❌）
  で欠落していた「事前提示」「マーカー管理」の両方が満たされた。
- ask 配列で "Bash(git push:*)" が既存と生成テンプレートで完全一致する値だったため、
  和集合マージの結果は重複なしの1件になった。SKILL.md には重複排除の明記はないが、
  「既存を削除しない」という原則から見て自然な解釈として処理した。今後、値が
  完全一致しないが意味的に重複するケース（例: 表記ゆれ）の扱いは SKILL.md に
  明記がなく、判断が実行者依存になる懸念がある。
