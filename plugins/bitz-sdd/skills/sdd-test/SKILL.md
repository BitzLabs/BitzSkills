---
name: sdd-test
description: BitzSDD のテスト・検証工程を行うスキル。EARS 記法の要件からテスト仕様を導出（節種別ごとの導出パターン、verification_method との対応）し、テストを実装・実行して、検証結果とトレース情報を .spec/specs/<feature>/ に記録する。ユーザーが「テストを書いて」「テスト仕様」「EARS からテスト」「検証して」「verified にして」と言及したとき、または sdd-implement の実装完了後に検証フェーズへ移行するときに使用する。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-29"
---

# SDD Test — EARS 要件からのテスト導出と検証

実装された要件を機械検証で充足させる工程です。「テストなき要件は存在せず、要件なきテストも存在しない」を規律とします。

## 前提

*   検証体系（L1: 仕様 / L2: コード / L3: プロセス）と verification_method の統制語彙・green 基準は
    `sdd-core` の references/verification.md が正。本スキルはそれを実行工程に落とす。
*   対象要件が `implementing`（sdd-implement のタスクに紐づけ済み）であること。

## 実行手順

1.  **テスト仕様の導出**: `references/test-derivation.md` に従い、EARS 節種別
    （Ubiquitous / Event-Driven / State-Driven / Unwanted Behavior / Optional）ごとの
    導出パターンで要件をテストケースへ変換する。verification_method との対応表に従う。
2.  **テストの実装**: テストケース名・タグに要件 ID を含める（例: `test_FR012_...`）。
    テストコードの配置はタスクの `boundary` 宣言内に収める。
3.  **記録**: 通常フローではテスト仕様書を `.spec/specs/<feature>/` に定型フォーマットで記録する
    （対象要件・EARS 節・導出元種別・verification_method・テストケース一覧・検証ステータス）。
    軽量レーンは `sdd-core` の lifecycle.md に定める STATE.md 正本 + PR がある場合の実出力で
    代替でき、既存の verified 要件へ遡及追加しない。
4.  **実行と判定**: テストを `spec_verify.py record` 経由で実行し、実出力から機械可読証跡を
    生成する（下記）。red の場合は `sdd-core` の references/failure-protocol.md に従う
    （テストを黙って弱めない）。全 green + `spec_inspect.py` の traceability 検証 PASS で
    要件の `verified` 遷移を人間に提案する。

## 検証証跡の記録（機械判定の正）

green 判定の正は **`.spec/verification/` の証跡**であり、test-spec 本文の数値ではない
（SDD-FR-151）。検証コマンドはラッパー経由で実行し、実出力から証跡を生成する:

```bash
python3 scripts/spec_verify.py record <workspace> \
  --command-id pytest --implements XX-FR-001 --implements XX-FR-002 \
  -- .venv/bin/pytest -q
```

- 証跡は `.spec/verification/<command-id>--<commit短縮>.json` に書かれ、
  **同一 commit・同一 command-id の再実行は同じファイルを上書き**する（冪等）
- 安定項目（commit・終了コード・件数・tool version）と観測値（実行時間）を分離し、
  実行時間は `observed` に隔離する。**実行時間の揺れだけでは diff が出ない**
- raw stdout/stderr・環境変数は保存しない。秘密値らしき引数や実行者のホームを含む
  絶対パスが渡された場合はコマンドを実行せず拒否する（SDD-FR-152）
- 未コミットの変更がある状態では拒否する。暫定記録が要るときだけ `--allow-dirty` を明示する
- `spec_inspect.py` が証跡を検査する（SDD-FR-153）。schema 不正・必須キー欠落・
  非ゼロ終了・failed 件数・参照切れは **FAIL**。HEAD と違う commit の証跡、
  証跡が無い verified 要件は **WARN**（加法的導入のため FAIL にしない）
- 集計は `sdd-report` が status-report.md の「検証証跡」節へ反映する（SDD-FR-154）

test-spec 本文の件数はナラティブであり、証跡と食い違っても**証跡が正**。
再実行のたびに test-spec の数値を手で追随させる必要はない。

## 軽量レーンの証跡チェックリスト

軽量レーンで `.spec/specs/<feature>/test-spec.md` を省略する場合、verified 遷移前に実行エージェント、
PR がある場合は reviewer が次を全項目確認する:

- [ ] STATE.md に対象リビジョン、秘匿情報を除いた実行コマンド、収集した期待件数、
      成功・失敗・スキップ件数、終了コード、機械チェック結果、実行日がある
- [ ] 実績件数の合計が期待件数と一致し、必須検証がすべて green である
- [ ] スキップごとに理由と許容根拠があり、未許容スキップがゼロである
- [ ] version 管理証跡の token・credential・その他の秘密値がプレースホルダー化されている
- [ ] PR がある場合、秘匿情報を除いた実出力が本文にあり STATE.md と一致する
- [ ] PR がない場合、STATE.md の情報だけで結果を再判定できる

1項目でも満たさない場合は verified へ遷移しない。verified 後に PR を提出・更新した場合も
STATE.md と再照合し、不一致が解消するまでマージしない。完全ログは version 管理へ複製せず、
必要なら最小権限で保護され監査期間中に参照できる CI run または保護ログを参照する。

## 検収規律（実行範囲の最小要件）

テストの green は「実行した範囲での green」に過ぎない。検収（`done` / `verified` 提案）の前に、
変更の**影響範囲に見合った実行範囲**を確保する（sdd-implement の implementation-discipline.md 6章と同一基準。SDD-FR-112）:

*   **共有スクリプト変更時は全スイート実行**: 変更が共有スクリプト（`scripts/` 配下・プラグイン同梱スクリプト・
    複数の呼び出し元から参照される契約）に触れる場合、対象要件のテストのみの部分実行で検収を完了とせず、
    **全テストスイートの実行**を必須とする。広く参照される変更は他 fixture の回帰を招くため、実行範囲を影響範囲に合わせる。
*   **環境固有前提の不在はスキップ**: 検査が特定ファイル（例: `CLAUDE.md`）の実在を前提とする場合、
    その前提を持たない環境・fixture では不在を検査違反ではなく**スキップ**として扱う。

## 後続工程

*   verified 後の promoted 遷移（docs/ への知見還流）は Promotion Gate（`sdd-core`）が管轄する。
*   検証状況の集計は `sdd-report` が `.spec/reports/status-report.md` に自動反映する。
