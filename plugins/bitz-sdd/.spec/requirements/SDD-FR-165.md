---
id: SDD-FR-165
version: 1.0
status: verified
domain: workflow
priority: medium
origin: SI-SDD-033（裁定K。.spec/reports/decision-2026-07-30-order8-design-foundation.md）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-165 共有作業ツリーでの汚染経路を並列運用規律で塞ぐ

- **説明**: `sdd-core/references/parallel-git.md` の既存節（ブランチ規約・マージ競合の構造的
  回避・並列サブエージェントのスコープ・権限マトリクス）は、いずれも**各作業者が隔離されて
  いる前提**で書かれていた。実際には複数のエージェントセッションが同一リポジトリのメイン
  作業ツリーを共有し、他セッションの作業途中のファイルがそこに現れる。この経路が未定義で
  あったため、2026-07-29 に次の事故が起きた。

  1. 広いパス指定（`git add -A -- <ディレクトリ>`）が他セッションの未コミット変更
     30ファイル・約2570行を無関係な PR へ巻き込み、main へ先行マージした
  2. チェックアウト中のブランチから派生させたため、後続の PR も他セッションのコミット内容を
     引き継いだ。squash マージでは祖先関係が残らず、重複・衝突として後から現れた
  3. 成果物へ記録する測定値を作業ツリーから読んだため、並行作業の途中状態を確定値として
     記録し、後に訂正が必要になった

  再発防止はリポジトリ固有の運用ルール（`AGENTS.md`）へ反映済みだが、**配布物である
  プラグイン側の規律には入っていない**ため、bitz-sdd の利用者は同じ事故を踏む。
  本要件は規律を配布物へ入れる。**単一セッション・単一 worktree の利用者に追加手順を
  課さない**ことを制約とする。

  機械強制（ステージ内容が宣言した `boundary:` を超えていないかの pre-commit 検査）は
  本要件の範囲外とする（裁定K）。Git 運用の実行責任を bitz-flow へ移す方針であり、
  強制層の所有者が変わる前提で bitz-sdd 側へ実装すると二重管理になる。
- **受入基準 (EARS)**:
  - WHERE 複数のセッションが同一の作業ツリーを共有しうる環境である THEN `parallel-git.md` は
    共有作業ツリーの節を持ち、①稼働中の作業ツリーの把握（`git worktree list`）
    ②既定ブランチのリモート追跡からの明示的なブランチ生成 ③広いパス指定でステージしない
    ④コミット直前のステージ内容の確認、の4点を規定すること SHALL
  - WHERE 単一セッション・単一 worktree で作業している THEN 共有作業ツリーの節は
    不要であることが本文から判別できること SHALL（追加手順を無条件には課さない）
  - WHEN `.spec/` の成果物へ件数などの測定値を記録する THEN 規律は確定した ref から読むこと
    （`git show <ref>:<path>` 等）と、測定の出典となる ref の併記を求めること SHALL
  - WHEN 権限マトリクスを参照する THEN 他セッションの作業中ファイルは全ロールで
    読み取りのみ許され、変更・移動・削除・コミットは人間だけであることが表から読めること SHALL
  - THEN 機械強制（`boundary:` 逸脱の pre-commit 検査）が本書の範囲外であり、
    bitz-flow への移管後に所有者を裁定することが明記されていること SHALL
- **検証手段**: manual-check。`parallel-git.md` を目視し、上記5項が記載されていることを
  確認する（規律文書であり自動検証の対象にできないため。機械強制を導入する場合は
  そのときに verification_method を見直す）。あわせて `release_check.py` と
  `spec_inspect.py --workspace . plugins/*` が PASS することを確認する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-033 と裁定K から導出。提案1〜3 のみを対象とし、
    提案4（機械強制）は bitz-flow への Git 運用移管後に裁定する。
  - 1.0 (2026-07-30) 代行可視化経路で approved 化
    （裁定記録 `.spec/reports/decision-2026-07-30-order8-design-foundation.md` 裁定K）。
  - 1.0 (2026-07-30) 実装完了により verified 化。**manual-check の実施記録**:
    `parallel-git.md` を目視し受入基準5項の所在を確認した — 共有作業ツリー節の4点
    （`git worktree list` / `origin/<default>` からの明示的分岐 / 広いパス指定の禁止 /
    `git diff --cached --name-only` の確認）、単一セッションでは不要である旨の明記、
    測定値を確定 ref から読む規律と出典 ref の併記、権限マトリクス末尾2行
    （他セッション作業中ファイルの読み取り可・変更は人間のみ）、機械強制が本書の範囲外で
    あることと bitz-flow 移管後に裁定する旨。あわせて
    `spec_inspect.py --workspace . plugins/*` PASS / `release_check.py` PASS /
    pytest 778 passed を確認した。
