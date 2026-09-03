---
id: ADR-034
title: TASK完了終端とdone起点操作の確定
status: accepted
relations:
  related:
    - ADR-024
    - ADR-028
    - ADR-029
---

# ADR-034 TASK完了終端とdone起点操作の確定

## Context

ADR-024はTASKの許可遷移を`open -> done`とし、ADR-029はTASK起点の`implement`／`verify`で
`requires`先TASKがすべて`done`であることを要求した。しかしSmall FlowとFull Flowには起点TASKを
`done`へ遷移させる段階がなく、完了した作業を`open`のまま残すと後続TASKが恒久的に`blocked`となる。

既存の`Post-check`後にTASKを`done`へ変更してそのままGitへ記録すると、状態遷移とRevision Historyを
変更後の入力で検査しない経路も生じる。一方、VerifyまたはHuman Reviewより前に`done`へ変更すると、失敗や
否決があった作業を終端状態へ置くことになる。

またContext Resolutionの状態表は`done` TASKをHistoryへ分類するだけで、`implement`、`verify`、
`interpret`の起点にした場合の結果を区別していなかった。追加作業には新しいTASKを使うという終端規則と、
完了済み作業をCIやレビューで再検証する需要を両立させる必要がある。

## Decision

1. Small FlowとFull Flowの8段階は維持し、TASK起点の`Done`を次の順序で実行する。
   1. Verifyの成功後にHuman Reviewを完了する。
   2. 起点TASKを`open -> done`へ変更し、同じdiffでRevision Historyを更新する。
   3. 変更後の入力に対して`bitz check <TASK-ID>`を実行する。
   4. checkがフローの通過条件を満たした場合だけ、完了結果をGitへ記録する。
2. 手順3のcheckは通常の明示TASK検査であり、状態遷移、Frontmatter、本文構造、関係、変更境界を検査する。
   TASK自身のファイルは`changes`境界の比較対象から除くが、状態遷移と文書検査の対象からは除外しない。
3. CoreはTASKのstatusを自動変更しない。`open -> done`は人間またはAIクライアントが確認可能なdiffとして行う。
   checkが通過しない場合はGitへ記録せず、原因を修正する。未記録の`done`編集を取り消して基準版と同じ
   `open`へ戻すことは、記録済みTASKに対する`done -> open`遷移とは扱わない。
4. 後続TASKのフローは先行TASKの完了結果をGitへ記録した後に開始する。これはAI-SDDフローの運用契約とし、
   Coreへ新しいコミット操作またはGit履歴ゲートを追加しない。
5. `done` TASKをpurpose別に次のとおり扱う。

   | purpose | 起点としての結果 | TASKの区分 |
   |---|---|---|
   | `implement` | `CTX-STATE-001`／error／`blocked` | History |
   | `verify` | 許可 | History |
   | `interpret` | 許可 | History |

   `implement`では新しいTASKの作成を`suggestedAction`へ示す。`verify`では`done` TASKの`addresses`から
   target statementまたは規範文なしTECHを導出し、TASK自身を規範として適用せず作業履歴として返す。
   `addresses`先と`requires`閉包には通常の適用可能性検査を行う。
6. `done` TASKを`verify`の起点にした場合も、`requires`先TASKに`open`が残ればADR-029どおり
   `CTX-TASK-DEPENDENCY-001`／error／`blocked`とする。`interpret`は停止せず、未完了先行TASKをWorkとして返す。
7. `bitz check <done TASK>`は許可する。checkは文書の現在状態とGit基準版からの遷移を検査する操作であり、
   `purpose=implement`の開始ではない。
8. `CTX-STATE-001`の条件を「起点または強い依存先が、指定purposeに対して適用不能」へ拡張する。
   新しいDiagnosticコードと公開操作は追加しない。
9. 本決定はADR-024 Decision 5、ADR-028 Decision 1および4、ADR-029 Decision 1を置き換えず、状態遷移、
   フロー終端、purpose別適用可能性の接続を補完する。

## Consequences

- TASKを`done`にし忘れて後続作業が停止する経路を、通常フローの中で解消できる。
- `done`化した入力をGitへ記録する前に状態遷移と文書構造を検査できる。
- 完了済みTASKから追加実装を再開できない一方、同じ対象の再検証と履歴参照は継続できる。
- Coreは状態を自動変更せず、Git commitも強制しないため、既存の責務境界を維持する。
- TASK起点ではHuman Review後に最終checkが1回増える。変更後のTASK状態を検査するために必要な呼出しである。

## Alternatives

1. **Verify前にTASKを`done`へ変更する**: Verify失敗時に終端状態だけが先行するため採用しない。
2. **Human Review前にTASKを`done`へ変更する**: 否決時に記録済み`done` TASKを再利用する圧力が生じるため採用しない。
3. **Human Review後に`done`へ変更してcheckせず記録する**: 状態遷移とRevision Historyを変更後の入力で検査できないため採用しない。
4. **`done` TASKの全purposeを禁止する**: 完了済み作業の再検証と履歴参照を妨げるため採用しない。
5. **`done` TASKから`implement`を許可する**: `done`を終端とするADR-024と矛盾するため採用しない。

## Notes

- 本ADRは2026-09-01のフロー終端・遷移条件レビューUC-FLOW-009およびUC-FLOW-012に対する裁定である。
- checkのフロー通過条件は`passed`または`passed_with_warnings`とすることを
  [ADR-035](ADR-035_check空対象とフロー通過statusの確定.md)で確定した。
- 完了しない取り止めは[ADR-036](ADR-036_フロー取り止めと不採用履歴の保持.md)が定める`cancelled`と
  `Stopped`を使う。本ADRの`Done`と`done`の契約は変更しない。
- 関連文書: [04_SDDプロセス設計](../03_SDDフロー.md),
  [06_運用設計](../04_運用手順.md),
  [08_実装ロードマップ](../../04.提案資料/12_Core-1.0実装計画.md),
  [09_ユースケース設計](../05_ユースケース.md),
  [SPECファイル規定/05](../../03.詳細設計/02_SPECモデル/03_文書種別・本文テンプレート.md),
  [SPECファイル規定/06](../../03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md),
  [SPECファイル規定/10](../../03.詳細設計/03_操作仕様/01_context.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-01 | TASK完了終端と`done`起点操作を確定 | `UC-FLOW-009`, `UC-FLOW-012` |
| 2026-09-01 | TASK完了時checkの通過statusをADR-035へ接続 | `ADR-035` |
| 2026-09-01 | 取り止め終端ADR-036との境界を追記 | `ADR-036` |
| 2026-09-03 | ADR-039の再編に合わせて関連文書linkを現構造へ更新（非意味的訂正） | 提案24 G8 |
