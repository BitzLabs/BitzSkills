---
id: SI-CORE-033
raised_by: 2026-07-21 SI-CORE-018 完了後の振り返りで発見
target: sdd-core の正規語彙（PHASE_CODES 等）と SKILL.md / references 記載の一致検証
proposed_change_type: modify
status: accepted
---
- **優先度（推薦）**: **中**。実害は既に2件発生しているが、いずれも個別には修正済み
  または起票済み。本 issue はその**再発を止める型**の話であり、緊急度より重要度が高い。
- **目的**: 正規語彙（フェーズ・status の定義）が**コードと文書に二重で存在し、一致を機械検証
  していない**ため、乖離が静かに発生し続ける。同一セッション内で同種の不整合を2件検出した。

  | 事象 | 内容 | 状態 |
  |---|---|---|
  | `bitz-sdd:SI-SDD-020` | `sdd-core/SKILL.md` の `Discuss` と `determine_phase()` の語彙が乖離 | 修正済み（PR #86） |
  | `bitz-sdd:SI-SDD-021` | `sdd_report.py` のタスク集計語彙が正規語彙と乖離（`blocked` が消える） | 未裁定 |

  - **修正済み側にも穴が残っている**: SI-SDD-020 の修正で導入した `SDD-FR-137` 条文6
    「`sdd-core/SKILL.md` のフェーズ・ルーティング表と `references/gates.md` は
    `determine_phase()` が返す7語と同一の語彙を用いる」は、**検証手段が目視のまま**である。
    2026-07-21 時点で `PHASE_CODES` を参照するのはテスト2本（`test_spec_status.py` /
    `test_spec_labels.py`）だけで、`scripts/release_check.py` は SKILL.md の記載を
    一切参照していない（該当0件）。したがって**同じ乖離が再び起こりうる**。
  - 一方、同 PR で導入した対訳辞書は
    「SSOT（`spec_labels.py`）＋複製＋`release_check.py` による一致検証」という型で
    機械検証されており、**型としては成立している**。これを文書側にも適用したい。
- **提案する修正**:
  1. `scripts/release_check.py` に、コード上の正規語彙と文書記載の一致検査を追加する。
     最小の対象は `spec_status.py` の `PHASE_CODES` と、`sdd-core/SKILL.md` の
     フェーズ・ルーティング表および `references/gates.md` に現れるフェーズ名。
  2. 文書側に**機械抽出できる目印**を与える（表の特定列、または
     `<!-- phase-vocabulary -->` 等のマーカー）。自由文から語を推定する実装にしない
     — 誤検出で運用が形骸化するため。目印の形式は Design Gate で裁定する。
  3. 同じ型を status 語彙へ拡張するかを判断する（`spec_update.py` の `TRANSITIONS` と
     `lifecycle.md` の状態遷移表の一致）。範囲に含めるかは裁定時に決める。
  4. 回帰テストを先行追加する（文書側の語を1つ改竄した状態で `release_check.py` が
     非ゼロ終了すること。`SDD-FR-137` の辞書一致検査テストと同じ流儀）。
- **対象ファイル**: `scripts/release_check.py`、`tests/test_release_check.py`、
  `plugins/bitz-sdd/skills/sdd-core/SKILL.md`（目印の付与）、
  `plugins/bitz-sdd/skills/sdd-core/references/gates.md`（同）、
  `plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`（`PHASE_CODES` の公開位置の確認）、
  bitz-sdd の3マニフェスト。
- **確認観点**:
  - 文書側の語を改竄すると `release_check.py` が FAIL すること（検査が実際に効くこと）
  - 語彙を正しく追加した場合は FAIL しないこと（加算的変更を妨げないこと）
  - 検査対象の抽出が自由文の推定に依らないこと（誤検出ゼロ）
  - bitz-sdd を含まないリポジトリでは SKIP されること（`SDD-FR-137` の辞書検査と同じ扱い）
  - `.venv/bin/pytest` / `spec inspect --workspace . plugins/*` / `release_check.py` が PASS
- **影響推定・ロールバック**: `release_check.py` に検査が増えるのみで、`.spec/` の
  データ移行は不要。文書側に目印を入れる場合は該当2ファイルの見た目が変わりうる。
  ロールバックは `release_check.py` と文書の revert で戻る。
- **依存**: `bitz-sdd:SI-SDD-021`（タスク集計語彙の修正）とは独立。ただし両者は同じ根本原因
  （語彙の分散と機械検証の不在）に対する対処であり、本 issue が再発防止、SI-SDD-021 が
  既存乖離の是正という関係にある。
  **ワークスペース**: 検査の実体が共有スクリプト `scripts/release_check.py` に入り、
  bitz-sdd の文書を対象とするためルートに起票する（サブ→ルートのエスカレーション相当。
  `SI-CORE-018` が `release_check.py` の変更をルート issue から委任した先例に倣う）。
- **可否の予備判定（推薦）**: **accept 推薦**。根拠:
  - 既存要件との矛盾: なし。`SDD-FR-137` 条文6 の検証手段を目視から機械検証へ引き上げる方向
  - ガードレール抵触: なし
  - 影響範囲: `release_check.py` と sdd-core の文書2ファイル
  - 軽量レーン適否: **不可**。文書への目印の付与形式が設計判断であり Design Gate を要する
    （目印なしの自由文推定は誤検出で形骸化するため、形式の裁定が本 issue の核心）
- **裁定**: 2026-07-22 人間裁定により accepted 化（チャット指示）。Design Gate で目印形式＝HTML コメントマーカー、
  検査範囲＝フェーズ語彙のみ（status 語彙は後続 issue）に裁定。
- **実施**: 2026-07-22 サブ（bitz-sdd）へ委任し **SDD-FR-140** として要件化（derived_from: SDD-FR-136, SDD-FR-137）
  → **SDD-TSK-024** で実装・検証。`scripts/release_check.py` に `check_phase_vocabulary` を追加し、
  `sdd-core/SKILL.md` と `references/gates.md` に `<!-- phase-vocabulary: ... -->` マーカーを付与。
  マーカー語集合が `spec_status.py` の `PHASE_CODES` と過不足なく一致すること、加えて可視の散文リスト
  （バッククォートのスラッシュ区切り）がマーカーと一致することを境界付き文字列比較で検証（自由文推定なし）。
  bitz-sdd 不在では SKIP。回帰テスト8件を `tests/test_release_check.py` に追加（改竄・欠落・余剰・散文ドリフト・
  マーカー欠落・加算的変更・SKIP を網羅）。全 pytest(303) / release_check / spec inspect PASS。
  bitz-sdd を 2.7.2 に、sdd-core スキルを 2.5.1 に bump。
- **status 語彙への拡張（提案3）**: 本 PR の範囲外。必要なら後続 spec-issue で
  `spec_update.py` の TRANSITIONS ⇔ `lifecycle.md` の一致検査として裁定する。
