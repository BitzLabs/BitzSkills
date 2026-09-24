---
id: ADR-051
title: 適合fixtureの変更手続きを確定する
status: accepted
relations:
  requires:
    - ADR-046
  related:
    - ADR-049
    - ADR-050
---

# ADR-051 適合fixtureの変更手続きを確定する

## Context

[適合fixture仕様 §1](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#1-所有範囲)は、実装が追加fixtureを持つことを許し、
matrixの行の削除・緩和を禁じている。しかし、仕様の側でmatrixやfixtureを直す手続きは定めていなかった。
前例は、設定の64 KiB上限により到達できない条件を裁定でmatrixから削除した`SINGLE-126-06`の1件だけであり、
これはGate Aの認定前に行われた。

Step 1からは、Coreの実装と、仕様・fixtureの保守が同じ作業の流れの中で行われる。実装者はAIであり、
Coreがfixtureを通過しないときに、fixtureを誤りとみなしてCoreの出力へ期待値を合わせると、Gate Bが意味を失う。
これは[ADR-046](ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)と
[ADR-050](ADR-050_契約Schemaの正本を詳細設計へ置く.md)が避けた自己申告と同じ構造である。
一方で、Coreを実装するとfixtureの本当の誤りも見つかり得るため、直す経路は必要である。

## Decision

1. **変更の種類**: Gate Aの認定後のmatrixとfixtureの変更を、追加、期待値の訂正、削除・緩和、非意味的な変更の
   4種類に分け、種類ごとの条件を適合fixture仕様 §1.1に定める。
2. **根拠**: 期待値の訂正、削除、緩和の根拠は規範文だけとする。Core実装の観測出力を根拠にしない。
   規範文自体を直す必要がある場合は、先に規範文を変更し、Decisionに関わる場合はADRを起こす。
3. **承認**: 期待値の訂正と削除・緩和には、人間の管理者の明示的な承認を要する。追加と非意味的な変更は
   通常のreviewでよい。
4. **緩和の定義**: 期待するstatus、終了コード、Diagnostic、report、副作用の制約を弱めること、
   入力を変えてfixtureが検査する条件を成立させなくすること、normalizerまたは比較の範囲を広げることを緩和とする。
5. **共通の手順**: 変更の根拠と内容をfixture群のreviewへ記録し、fixtureの変更とCore実装の変更を同じcommitに
   含めず、Gate Aを`certify_gate_a.py`で再認定する。再認定が通過するまでGate Aは`Blocked`とする。
   Gate Bが`Passed`のStepに属するfixtureを変更した場合は、そのGate Bを判定し直す。

## Consequences

- Coreがfixtureを通過しないとき、まずCoreの欠陥として扱う。fixtureを直すには、規範文との食い違いを
  Coreとは独立に示し、人間の承認を得る必要がある。
- fixtureの変更がcommit単位で分かれるため、reviewで期待値の変更とCoreの変更を取り違えない。
- fixtureを変更するたびに再認定（約3分）と検証記録の追記が必要になる。
- 過去にPassedとしたGate Bは、fixtureの変更によって判定し直しになり得る。

## Alternatives

1. **手続きを定めない**: fixtureの誤りを直す経路がないまま、実装の都合で期待値が変わる危険が残る。採用しない。
2. **Gate A後はfixtureを一切変更しない**: fixtureの本当の誤りを直せず、誤った期待値にCoreを合わせることになる。
   採用しない。
3. **全種類の変更に人間の承認を要する**: 追加と非意味的な変更は検査を弱めないため、承認の負担に見合わない。
   採用しない。

## Notes

- 反映先: [適合fixture仕様 §1.1](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#11-matrixとfixtureの変更)、
  [Core 1.0実装計画 §1.1](../../04.提案資料/12_Core-1.0実装計画.md#11-進行状態とgate)。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-24 | Gate A後の適合fixtureの変更を4種類に分け、根拠、承認、緩和の定義、共通の手順を確定 | 適合fixture仕様 §1.1 |
