---
implements: FLW-NFR-011
depends_on: []
boundary: evals/flow-core/m1-eval/
status: done
---

### M1開始時の予算・実績・出口条件・縮退境界をrun manifestへ記録する

- **作業内容**: milestone 開始時に予算と出口を機械可読な形で記録する規律（FLW-FR-012）を M1 について
  実施する。`evals/flow-core/m1-eval/run-manifest-m1-entry.json` を新設し、FLW-DSN-014 v1.14 を正として
  次の5区画を記録する。

  - **総枠**: 6 PR / 20 session。
  - **区分配賦**: 公開契約 1 PR / 3 session、qualification 1 / 4、Git 実装 2 / 7、
    evidence 合成 1 / 3、confirmation 1 / 3。
  - **M0 実績**（外挿根拠）: 実装 1 PR に対し検証 12 PR、eval 14 ラウンド、
    eval 反復 : 実装 = 3 : 5。
  - **M1 出口条件**: M1 所属 operation の contract 全行、fault fixture、重複 commit 0。
  - **縮退境界**: M0 read-only prerelease だけを維持し、Git write と doctor v2 は公開しない。
    ledger / qualification を無効化して write だけ公開する縮退は認めない。

  停止規則（PR 予算か session 予算のどちらかを先に使い切った時点で停止し人間へ再提示する。
  進行中 milestone の上限を暗黙延長しない）と、区分間は未使用 session だけを後続へ移送できる規則も
  field として持たせる。実績消費（PR 数・session 数・レビュー修正回数・出口未達理由）は
  M1 進行中に追記できる構造にする。
- **完了条件**: manifest が JSON として妥当で、上記5区画と停止規則をすべて持つこと。
  区分配賦の合計が総枠（6 PR / 20 session）と一致することを機械的に確認できること。
  `python3 <リポジトリ>/scripts/release_check.py` が PASS すること。
- **備考**: 本タスクは記録のみで、予算そのものの再校正は行わない（正は FLW-DSN-014）。
  `evals/flow-core/m0-eval/` 配下は読み取りのみとし変更しない。
