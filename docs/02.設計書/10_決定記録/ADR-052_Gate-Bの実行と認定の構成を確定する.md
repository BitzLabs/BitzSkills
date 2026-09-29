---
id: ADR-052
title: Gate Bの実行と認定の構成を確定する
status: accepted
relations:
  requires:
    - ADR-046
    - ADR-049
  related:
    - ADR-051
---

# ADR-052 Gate Bの実行と認定の構成を確定する

## Context

[ADR-046](ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)と
[適合fixture仕様 §3.5・§4・§5](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#35-検査対象と実行環境)は、
harnessが検査対象Coreをどう受け取り、どの環境で起動し、何を比較するかを定めた。
[ADR-049](ADR-049_Coreのsource配置と試験の構成を確定する.md)の`Decision`の5番目の項目は、マニフェストを実行する参照harnessを
`fixtures/`に置き、Coreを引数で受け取って`bitz`をインポートしないとした。しかし、Gate Bを実際に判定するには次が
決まっていない。

1. 参照harnessの入口と、Stepまたはfixtureの選び方
2. 各Stepの完了fixtureは[実装計画](../../04.提案資料/12_Core-1.0実装計画.md)の散文にしかなく、機械で読めない
3. Step nのGate Bで、Step 1からn−1の完了fixtureを再実行するか
4. Step 2のGate Bは、参照harnessの結果に加えて、Core固有の構文解析器のアダプター（`tests/bitz-core/`、
   [適合fixture仕様 §4.1](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#41-内部の構文解析器受入)）の結果を要する。
   ADR-049の`Decision`の6番目の項目により`fixtures/`は`tests/`を参照できない
5. Step 1ではCoreがまだないため、参照harness自身が正しく合否を判定できることを確かめる手段がない

## Decision

1. **参照harnessの入口**: `fixtures/run_conformance.py`を入口とし、実装は`fixtures/conformance/`に置く。
   `--core`で検査対象Coreのソースのディレクトリまたはwheelを受け取り、`--step`または`--fixture`で対象を選ぶ。
   fixtureごとの合否と差分の要約をJSONで出力し、選んだfixtureがすべて通過した場合だけ終了コード0とする。
2. **Step一覧の機械可読な写し**: 各Stepの完了fixtureを`fixtures/conformance/steps.json`に置く。
   公開結果を比較する`fixtures`と、構文解析器の受入だけを行う`parserChecks`を分ける。正本は実装計画のままとし、
   監査（`validate_conformance.py`）が両者の一致、matrixのすべてのIDへの公開結果の比較の割当て、`parserChecks`を持つ
   すべてのfixtureへの構文解析器の受入の割当てを検査する。
3. **累積の判定**: Step nのGate Bは、Step 1からnまでのすべての`fixtures`と`parserChecks`を通過することを条件とする。
4. **認定コマンド**: Gate Bの認定は`tests/bitz-core/certify_gate_b.py`が行う。`HEAD`から独立したクローンを2つ作り、
   それぞれで`plugins/bitz-core`をビルドし、参照harnessと、Step 2以降では構文解析器のアダプターを実行して、
   結果がクローンの間で一致し、すべて通過することを求める。結果と実行環境を記録へ残す。
   `tests/`から`fixtures/`への参照はADR-049の`Decision`の6番目の項目が許す向きである。
   CIでの分割実行と独立2組の集約による同等の認定は[ADR-056](ADR-056_適合試験の分割実行とCIのGate-B集約を確定する.md)に従う。
5. **参照harnessの自己試験**: `fixtures/`に、期待出力をそのまま返す偽のCoreを置く。参照harnessは偽のCoreで
   全fixtureを通過とし、出力を1箇所改変した偽のCoreでは該当fixtureを不通過とすることを、監査試験で確かめる。

## Consequences

- 参照harnessはCoreに依存せず、Coreに固有の手順（ビルド、構文解析器のアダプター）は認定コマンドだけが持つ。
- 実装計画の完了条件を書き換えると、`steps.json`を同時に直さなければ監査が失敗する。
- 後のStepの実装が前のStepの機能を壊すと、そのStepのGate Bは通過しない。
- Step 1で、Coreより先に参照harnessと偽のCoreを作ることになる。参照harnessの欠陥をCoreの欠陥と取り違えない。
- 認定はクローンごとにCoreのビルドと全対象fixtureの実行を行うため、Gate Aの認定より時間がかかる。

## Alternatives

1. **Step一覧を実装計画の散文から毎回読む**: 写しは不要だが、Gate Bの実行が文書の書式に依存する。
   `steps.json`を置き、散文との一致を検査する方が、実行と検査の責務が分かれる。採用しない。
2. **`steps.json`を正本にする**: 実装計画はGate条件の正本であり、一覧だけを別の正本にすると所有が2か所になる。
   採用しない。
3. **Step nのGate BでStep nの完了fixtureだけを実行する**: 後のStepの変更による後退を検出できない。採用しない。
4. **認定コマンドを`fixtures/`に置く**: 構文解析器のアダプターを呼ぶには`tests/`を参照する必要があり、ADR-049の`Decision`の6番目の項目に反する。
   採用しない。
5. **偽のCoreを置かず、本物のCoreで参照harnessを試す**: Step 1の時点で合否の誤りを検出できず、
   参照harnessとCoreの欠陥が区別できない。採用しない。

## Notes

- 反映先: [Core 1.0実装計画 §1.1・§4](../../04.提案資料/12_Core-1.0実装計画.md#11-進行状態とgate)、
  `fixtures/conformance/steps.json`、`fixtures/conformance/step_assignment.py`、`fixtures/validate_conformance.py`。
- 参照harness、偽のCore、認定コマンドの実装はStep 1で行う。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-24 | 参照harnessの入口、Step一覧の機械可読な写し、累積の判定、認定command、偽のCoreによる自己試験を確定 | 実装計画 §1.1・§4 |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
