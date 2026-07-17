---
id: SI-ENV-008
raised_by: skill-evaluator（evals/env-init/report.md TC-02節）
target: plugins/bitz-env/.spec/requirements/ENV-FR-004
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: ENVFR004-S1 は「CLAUDE.md / AGENTS.md への挿入はマーカー区間内の
  みで、区間外の既存記述がバイト単位で不変」と定めるが、env-init（skill あり実行,
  evals/env-init/runs/6）を検証したところ、既存記述そのものはバイト単位で無傷
  （`head -c $(stat -c%s original/AGENTS.md) sandbox/AGENTS.md | cmp - original/AGENTS.md`
  で完全一致を確認）である一方、既存内容の末尾と `<!-- bitz-env:begin -->` の間に、
  原文に存在しなかった区切りの空行が1行、**マーカー区間の外側**に追加されていた
  （AGENTS.md・CLAUDE.md 双方で再現。同種の入力＝既存ファイルへの追記全般で毎回発生する
  構造的な挙動と推定される）。ENVFR004-S1 を文言どおり厳密に読むと「挿入はマーカー区間
  内のみ」という条件を満たしておらず、要件と実装の間に解釈の揺れがある
  （evals/env-init/report.md TC-02節に詳細な byte-level 証拠と判定根拠を記載）。
- **提案する修正**: (a) ENV-FR-004 の受入基準に「区切りに必要な空白・改行はマーカー
  開始タグの内側（`<!-- bitz-env:begin -->` の直後）に含める。マーカー区間外へは
  一切新規バイトを追加しない」ことを明記する。(b) env-init の SKILL.md
  （既存ファイルへの追記手順）に、区切り整形をマーカー内側で行う実装ルールとして
  反映する。過学習を避けるため、AGENTS.md/CLAUDE.md 固有ではなく「マーカーで管理する
  既存ファイルへの追記全般」に適用される一般規則として記述する。
- **影響推定**: ENV-FR-004 の受入基準1件の文言追加・明確化。env-init の追記ロジック
  （区切り改行の挿入位置）の修正が必要。既存テスト（evals/env-init/cases.md
  ENVFR004-S1）は文言のまま再検証可能。他要件への影響なし。
- **裁定記録**: 2026-07-12 人間裁定（チャット指示「highの3件について進めましょう」）により accepted。提案どおり反映する。
- **実施**: 2026-07-18（事後確認・SI-ENV-022）`ENV-FR-004.md` にマーカー内側整形ルールの
  記述が実在することを確認済み。
