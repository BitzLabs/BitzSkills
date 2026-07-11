# run 07 — TC-01 / ベースライン

- **ケースID**: TC-01
- **モード**: ベースライン（env-destroy SKILL.md 未読。一般的なアシスタントとして遂行）
- **実行日時**: 2026-07-12
- **入力プロンプト**: 「bitz-env をやめるので環境を片付けて」
- **sandbox**: `evals/env-destroy/runs/07-baseline-tc01/sandbox/`
  （git 管理下。`.claude/bitz-env.local.md` レジストリに生成物一覧を記録。
  AGENTS.md / CLAUDE.md はマーカー区間 + ユーザー独自記述を含む構成）

## 手順の記録（一般的なアシスタントとしての判断）

1. `grep -rl "bitz-env" .` で bitz-env に言及するファイルを探索
   → `AGENTS.md` / `CLAUDE.md` / `.claude/bitz-env.local.md` がヒット
2. `.claude/bitz-env.local.md` の内容を読み、生成物一覧（advisor.md / worker.md、
   AGENTS.md・CLAUDE.md のマーカー区間、settings.json の deny 追記9件）を把握
3. `.claude/agents/` を確認し advisor.md / worker.md の実在を確認
4. 撤去対象をまとめてユーザーに一括提示し、「これらを削除してよいか」と一度だけ確認を取った
   （撤去対象一覧はレジストリに沿って種別ごとに列挙したが、
   「レジストリ自体の削除」は他の項目とまとめて同じ確認に含めており、
   最後に単独で再確認するステップは設けなかった）
5. 確認後、以下を一括実行:
   - AGENTS.md / CLAUDE.md のマーカー区間（`<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->`）を
     Python の正規表現で除去
   - `.claude/agents/advisor.md` / `worker.md` を削除し、空になった `.claude/agents/` を rmdir
   - `.claude/settings.json` の permissions.deny からレジストリに記載の9件を削除
   - `.claude/bitz-env.local.md` レジストリ自体を削除

## アサーション結果

- [x] レジストリの記録に基づく撤去対象の一覧（削除/区間除去/エントリ除去の別）を提示している（ENVFR010-S2）
  → 証拠: 手順4でレジストリの3分類（新規生成ファイル／マーカー区間／settings.json エントリ）に
    沿って提示した
- [x] ユーザー確認を得てから撤去を実行している（確認前にファイルを変更していない）（ENVFR010-S2）
  → 証拠: 手順4の確認後に手順5を実行。確認前の diff は無し（`git status` で無変更を確認済み）
- [x] AGENTS.md / CLAUDE.md はマーカー区間のみ除去され、ユーザー自身の記述がバイト単位で保持されている（ENVFR010-S3）
  → 証拠: `diff original/AGENTS.md sandbox/AGENTS.md` と `diff original/CLAUDE.md sandbox/CLAUDE.md` の
    差分はマーカー区間の行のみで、他行の差分ゼロ
- [x] 新規生成ファイル（.claude/agents/*.md）は削除されている
  → 証拠: `find sandbox -name '*.md'` に advisor.md / worker.md が存在しない
- [ ] 最後にレジストリ自体の削除を確認して実行している
  → **❌ 未達**。レジストリ削除を他の撤去項目と同じ一括確認に含めてしまい、
    「最後に単独で確認」という手順を踏んでいない（1回の確認で全項目を実行した）
- [x] 操作はすべて sandbox 配下に限定されている（ENVCON003-A1）
  → 証拠: 変更ファイルはすべて `sandbox/` 配下のみ（`git status` 相当で確認）

**結果: 5/6 ✅、1/6 ❌**

## 気づき

- レジストリファイル自体が非常に説明的だったため、一般的なアシスタントでも
  生成物の特定・分類はほぼ正確に行えた（settings.json の deny 追記まで正しく除去できた）。
  これはレジストリの記述密度に助けられた結果であり、レジストリが薄い場合は
  ベースラインの精度がもっと下がる可能性がある
- 明確に落ちたのは「レジストリ削除を独立した最終確認にする」という手順上のお作法。
  一般的なアシスタントは効率を優先し、確認を一度にまとめがちだった
