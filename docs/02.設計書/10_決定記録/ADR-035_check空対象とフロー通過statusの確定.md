---
id: ADR-035
title: check空対象とフロー通過statusの確定
status: accepted
relations:
  related:
    - ADR-019
    - ADR-027
    - ADR-028
    - ADR-031
    - ADR-034
---

# ADR-035 check空対象とフロー通過statusの確定

## Context

ADR-031は、引数なし`bitz check`で変更code/test pathをFrontmatter逆索引から所有REQ/TECHへ正規化し、
未所有pathを検査対象外として件数だけ結果へ残すと定めた。この結果、変更集合が空の場合だけでなく、
SPEC未整備のcode/test pathだけを変更した場合にも検査対象文書が0件となる正常経路が生じた。しかし、
対象0件時のstatusと結果Schemaは定義されていなかった。

引数なし`verify`は空のCIを成功扱いしないため、対象0件を`SPEC-VERIFY-BLOCKED-002`／`blocked`とする。
checkがこの規則を流用すると、検査対象SPECがない通常のコード変更までCIを停止する。checkとverifyでは
対象0件の意味が異なる。

またADR-028は「Post-checkが非成功のままVerifyへ進まない」と定め、ADR-034はTASK完了時checkが
「フローの通過条件」を満たしてからGitへ記録すると定めたが、`passed_with_warnings`を成功側へ含めるかを
明示していなかった。共通結果形式では`passed`と`passed_with_warnings`がともに終了コード0であり、Core 1.0は
warningをerrorへ昇格する`--strict`を提供しない。

## Decision

1. 引数なし`bitz check`の変更範囲を正規化した結果、検査対象文書が0件であり、設定・索引・Git縮退を含む
   他のDiagnosticがない場合は`passed`／終了コード0とする。対象0件専用のDiagnosticは追加しない。
2. 対象0件でも、`bitz.yaml`のSchemaと互換性、全SPECの軽量Frontmatter索引、IDと関係の索引、Git変更集合、
   対象外code/test pathの集計を実行する。これらからDiagnosticが生じた場合は共通順位で集約し、0件を理由に
   `passed`へ上書きしない。
3. Decision 1は引数なしの変更範囲`check`だけに適用する。明示対象、`--full`、`--all-workspaces`の対象選択は
   変更しない。`check --all-workspaces`は従来どおり`--full`を含意する。
4. check結果へ、`scope: changed`で使用する次のcheck固有フィールドを追加する。

   ```json
   {
     "selection": {
       "changedPathCount": 3,
       "targetDocumentCount": 0,
       "excludedCodeTestPathCount": 3
     }
   }
   ```

   - `changedPathCount`は正規化したGit変更集合のchange entry数とする。
   - `targetDocumentCount`は所有文書IDへ正規化して重複排除した後の検査対象文書数とする。
   - `excludedCodeTestPathCount`はどの`implements`／`tests[].path`逆索引にも該当せず対象外となった
     code/test change entry数とする。

   text出力も同じ3件数を1行で示す。対象外pathそのものは通常結果へ列挙しない。
5. 引数なし`verify`の対象0件は従来どおり`SPEC-VERIFY-BLOCKED-002`／`blocked`とし、契約を変更しない。
   checkの0件は「今回完全解析すべき変更SPECがない」、verifyの0件は「実行して保証すべき検証対象がない」
   ことを表す。
6. Pre-check、Post-check、ADR-034のTASK完了時checkのフロー通過statusを`passed`または
   `passed_with_warnings`とする。構造化クライアントはstatus、CLI利用者は同値である終了コード0を判定に使う。
7. `failed`、`blocked`、`error`を非成功とし、次段階へ進まない。引数不正の終了コード4は操作statusを
   生成しないが、同じく次段階へ進まない。
8. warningはDiagnostic、text／JSON出力、明示レポートへ保持するが、Core 1.0のフローでは自動昇格しない。
   Core 1.0へ`--strict`を追加しない。人間レビューまたはCore外のCI policyがwarningを理由に停止することは
   妨げない。
9. 本決定はADR-028 Decision 4の「非成功」とADR-034 Decision 1の「フローの通過条件」を明確化し、
   ADR-031 Decision 2の対象外件数を結果Schemaへ具体化する。既存Decisionを置き換えない。

## Consequences

- SPEC未整備のcode/test変更だけで通常checkとCIが停止しない。
- 対象0件でも設定と全体索引の不適合を見逃さない。
- checkとverifyの空集合が、各操作の保証目的に応じて異なるstatusを持つ。
- warningを残したままSmall/Full Flowを継続でき、終了コードとフロー判定が一致する。
- 対象選択の件数がJSONで安定し、text表示とfixtureを同じ値から生成できる。

## Alternatives

1. **check対象0件を`blocked`にする**: ADR-031が正常経路として除外した未所有code/test変更でCIが停止するため採用しない。
2. **check対象0件をwarningにする**: 未所有pathをwarningにしないADR-031の決定を実質的に覆すため採用しない。
3. **0件時は設定と索引を省略する**: 対象選択に必要な設定・索引の不適合を空成功で隠すため採用しない。
4. **`passed_with_warnings`をフロー非成功にする**: 終了コード0との意味が分かれ、通常発生するwarningでフローが完了しないため採用しない。
5. **`--strict`でwarningを昇格する**: Core 1.0の共通終了コードを操作別policyで変えるため採用しない。

## Notes

- 本ADRは2026-09-01のフロー終端・遷移条件レビューUC-FLOW-010およびUC-FLOW-013に対する裁定である。
- 関連文書: [01_共通アーキテクチャ](../01_システム構成.md),
  [04_SDDプロセス設計](../03_SDDフロー.md),
  [05_QA品質保証設計](../02_品質属性と安全境界.md),
  [08_実装ロードマップ](../../04.提案資料/12_Core-1.0実装計画.md),
  [09_ユースケース設計](../05_ユースケース.md),
  [SPECファイル規定/06](../../03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-01 | check空対象とフロー通過statusを確定 | `UC-FLOW-010`, `UC-FLOW-013` |
| 2026-09-03 | ADR-039の再編に合わせて関連文書linkを現構造へ更新（非意味的訂正） | 提案24 G8 |
