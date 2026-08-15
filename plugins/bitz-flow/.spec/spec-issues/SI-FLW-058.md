---
id: SI-FLW-058
raised_by: FLW-REV-016 M2 Exit再レビュー
target: M2 confirmation harnessの証跡（raw log・実測値・TTL・指紋範囲）
proposed_change_type: modify
status: accepted
---

- **目的**: M2 の confirmation 証跡を `FLW-NFR-011` の契約へ適合させ、
  active manifest の主張を第三者が検証できる形にする。現状の manifest は
  実走した事実は示すが、hazard 0 / residual 0 を裏づける観測を持たない。

- **発見した事実**（`FLW-REV-016:SYN-004` / `SYN-005` / `SYN-007` / `SYN-008` / `SYN-009`）:
  - `run_local_confirmation.py` は raw log の digest だけを記録して本体を破棄する
    （`raw_log_committed: false`）。`FLW-NFR-011` が SHALL で求める owner-only 境界・
    redaction・最大30日保持・削除担当と削除証跡の manifest 記録がなく、
    M1 が持つ `raw_log_guard.py` も未使用である。
  - `local_confirmation_subject.py` は `required_checks=2/2 positive_controls=2/2
    hazards=0 residuals=0` を**固定文字列**として出力し、runner は marker 一致から
    `0 if valid else 1` を写すだけである。run 前後のリポジトリ状態を比較する機構がなく、
    これらは反証不能な恒真値である。実測されているのは tests 件数・test ID digest・
    runtime check の3つのみ。
  - active manifest の `operations` は未公開の `git.stage` / `git.commit` / `git.fetch` /
    `git.sync` を確認済みとして列挙し、`worktree.*` のワイルドカードで将来 operation まで
    認証範囲に含める。公開集合の正は `flowlib/cli.py` の `_HANDLERS` である。
  - `COMPATIBILITY_INPUTS` の7ファイルに `worktree_capability.py` / `guard.py` /
    `worktree_cleanup.py` / `recovery.py` と対象 fixture が含まれず、CLI version・
    model identity も指紋外である。認可核を変えても manifest が失効しない。
    `FLW-NFR-011` が要求する `evidence_id` の分離も未実装。
  - qualification summary の `expires_at` を読むコードが存在せず、24時間 / 7日の TTL 照合が
    未実装である（runner が照合するのは `gate_status` と `compatibility_key` のみ）。

- **提案する修正**:
  1. M1 の `raw_log_guard.py` を M2 harness へ接続し、保持境界・redaction・削除証跡を
     manifest へ記録する。
  2. run 前後の worktree 一覧と `git status` の digest を取得して残留副作用を実測し、
     required check / positive control を台帳から導出する。
  3. manifest の `operations` を実際に公開かつ実測した閉集合へ限定し、ワイルドカードを廃する。
  4. `COMPATIBILITY_INPUTS` を `FLW-NFR-011` の列挙へ揃え、`evidence_id` を分離する。
  5. runner に fingerprint TTL 照合を実装し、期限超過を `blocked` として非ゼロ終了させる。

- **対象ファイル**: `evals/flow-core/m2-eval/run_local_confirmation.py`、
  `evals/flow-core/m2-eval/local_confirmation_subject.py`、
  `evals/flow-core/m1-eval/raw_log_guard.py`、`tests/test_flow_m2_confirmation.py`、
  `plugins/bitz-flow/.spec/specs/m2-exit/test-spec.md`

- **確認観点**:
  - hazard / residual が実観測から導出され、意図的に残した副作用を検出できること。
  - 認可核のいずれかを変更すると manifest が失効すること。
  - 期限切れ qualification で confirmation が起動しないこと。

- **影響推定・ロールバック**: harness に閉じる。指紋範囲を広げるため、
  変更後は qualification と confirmation の再実走が必要になる。

- **依存**: `FLW-REV-016:GP-004`。予算は `FLW-REV-016:GP-005` の再裁定に従う。

- **着手条件としての先行履行**（2026-08-15 予算裁定）: 本 issue のうち **run manifest の記録機構**は、`SI-FLW-061` の PR に含めて先行履行する。以後の PR で実績 PR 数・session 数・レビュー修正回数・出口未達理由を記録し、残予算の再提示はこの実績に基づいて行う（`FLW-REV-016:SYN-015` の是正）。
