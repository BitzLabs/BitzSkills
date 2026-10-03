---
id: ADR-036
title: SDDフローの取止めと不採用履歴の保持
status: accepted
relations:
  related:
    - ADR-024
    - ADR-029
    - ADR-034
---

# ADR-036 SDDフローの取止めと不採用履歴の保持

## Context

開発フローには完了と再作業の経路がある一方、検討の途中で提案または設計を取り止める終端がない。
未採用のREQまたはTECHを削除すると、判断の理由、比較した選択肢、再検討の条件が失われ、将来の設計で同じ検討を
繰り返す。反対に、`draft`または`outdated`のまま残すと、作業中または再確認待ちの契約と、採用しないと決めた
履歴を区別できない。

TASKにも完了せずに閉じる状態がないため、取り止めた作業が`open`のまま残り、後続のTASKの依存の判定を曖昧にする。
取止めは人間の判断であり、Coreが本文や作業の停滞から推測してはならない。

## Decision

1. 人間は、工程`Done`へ到達する前の任意の段階で、フローを明示的に取り止められる。フロー上の終端の名前を
   `Stopped`とする。`Stopped`はCore共通の操作の結果の状態でも、仕様文書の状態（`status`）でもなく、進行支援上の結果である。
   Coreは取止めを推測せず、文書の削除、状態の変更、コミットを自動で実行しない。
2. REQとTECHへ終端状態`rejected`を追加する。作成するときは`draft`、`approved`、`rejected`を許可し、
   `draft -> approved|rejected`、`approved -> draft|outdated`、`outdated -> draft|approved`と、同一状態の維持を
   許可する。`approved -> rejected`は禁止し、一度適用した契約を廃止または見直す場合は`outdated`を使う。
   `rejected`からほかの状態への遷移は禁止し、再検討するときは新しいIDのREQまたはTECHを作成して関連付ける。
3. `rejected`のREQとTECHには、空でない条件付き必須のH2`Rejection Rationale`を置く。採用しなかった理由、
   根拠またはトレードオフ、再検討の条件を記録し、元の`Acceptance Criteria`または`Contract`と
   `Verification`を保持する。理由がない`rejected`の文書は構造違反とする。
4. `rejected`のREQとTECHは、目的`interpret`で履歴の区分として返し、`check`の構造、ID、関係の検査の対象とする。
   目的`implement`または`verify`の起点として、また強い依存先としては、診断`CTX-STATE-001`（重大度`error`、結果への効果`blocked`）とする。
   `related`による履歴の参照は許可する。
5. `rejected`の文書の`implements`、`tests`、`verify`は、過去の判断を理解するために保持するが、コードとテストの
   所有の逆索引、検証対象の選択、カバレッジ、パスの存在の検査、検証コマンドの解決から除外する。型、文書ID、
   ローカルID、EARS-AIの構文、本文の構造、関係の参照先の存在と型は、通常どおり検査する。
6. TASKへ終端状態`cancelled`を追加する。作成するときは`open`だけを許可し、`open -> done|cancelled`と、同一状態の
   維持だけを許可する。`done`と`cancelled`は終端であり、`cancelled`を完了済みとして扱わない。
7. `cancelled`のTASKには、空でない条件付き必須のH2`Cancellation Rationale`を置き、取止めの理由、既に得た
   知見、再開または再計画の条件を記録する。`Objective`、`Work`、`Completion Criteria`は履歴として保持する。
8. `cancelled`のTASKは、目的`interpret`で履歴の区分として返し、明示対象を指定した`check`を許可する。目的`implement`または
   `verify`の起点では、診断`CTX-STATE-001`（重大度`error`、結果への効果`blocked`）とする。別のTASKの`requires`の参照先にある場合は未充足とし、
   診断`CTX-TASK-DEPENDENCY-001`（重大度`error`、結果への効果`blocked`）で、依存の除去または代替TASKへの更新を案内する。
9. 文書を伴う取止めでは、人間が状態と理由を同じ変更へ記録し、`bitz check <ID>`が`passed`または
   `passed_with_warnings`であることを確認してからGitへ記録する。TASKを起点とする場合は`open -> cancelled`を検査する。
   該当するREQ、TECH、TASKのいずれもない取止めは、Coreの保証の外の作業記録として扱う。
10. 本ADRは、[ADR-024](ADR-024_仕様文書の状態遷移契約.md)の`Decision`の1、2、5番目の項目だけを置き換える。
    ADR-024の`Decision`の3、4、6、7番目の項目は変更しない。ADR-029の依存ガードとADR-034の完了終端は置き換えず、
    `cancelled`および`Stopped`の契約を追加する。

## Consequences

- 不採用の提案・設計を、理由とともに検索できる履歴として保持できる。
- `rejected`を現行の契約の所有権、検証、カバレッジから分離し、過去のパスの情報による誤選択を防げる。
- TASKの完了と取止めを区別し、取り止めた依存を自動的に充足扱いしない。
- 取止めのときにも、明示的な状態の変更と検査が必要になり、理由の記録なしに文書を閉じられない。
- 終端の文書を再利用せず、新しいIDで再検討するため、過去の判断と新しい判断の境界が残る。

## Alternatives

1. **取り止めた文書を削除する**: 判断の理由と再検討の条件が失われ、同じ設計の検討を繰り返すため採用しない。
2. **`draft`のまま残す**: 作業中と不採用を区別できず、未決事項として残り続けるため採用しない。
3. **REQまたはTECHを`outdated`へ変更する**: 一度適用された契約の再確認待ちと、採用前の否決を混同するため採用しない。
4. **`rejected`の文書のパスと検証の情報も現行の索引へ含める**: 過去の候補が、現行のコードの所有者または検証対象として
   選ばれるため採用しない。
5. **`cancelled`のTASKを依存の充足とみなす**: 必要な作業が完了していないまま後続の作業を開始できるため採用しない。

## Notes

- 本ADRは2026-09-01のP2の追加レビューUC-FLOW-016「flow途中の提案・設計取止め」に対する裁定である。
- `Rejection Rationale`と`Cancellation Rationale`は履歴の説明であり、EARS-AIの規範文やカバレッジの意味集合へ
  含めない。
- 2026-09-01の実装前の異常ケースのレビュー`EDGE-002`で、実装の後に残るコードとテストの差分の処遇を明確化した。
  人間が破棄、保持、別のTASKへの引継ぎ、スパイクへの隔離を選び、Coreとスキルは自動で削除しない。この明確化は
  `Decision`の1番目と9番目の項目の人間の判断とGitへの記録を具体化するもので、状態や必須のスキーマを追加しない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-01 | flow取止め、REQ／TECHの不採用履歴、TASKの中止終端を確定 | `UC-FLOW-016` |
| 2026-09-01 | Implement後の差分処遇とphase checkpointを明確化 | `EDGE-002` |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
