---
id: ADR-053
title: CPythonの下限を3.12へ引き上げる
status: accepted
relations:
  requires:
    - ADR-051
  related:
    - ADR-045
    - ADR-046
    - ADR-049
---

# ADR-053 CPythonの下限を3.12へ引き上げる

## Context

[ADR-045](ADR-045_実行環境と配布物の確定.md) Decision 1はCore 1.0の対象をCPython 3.11以上とし、
3.10以下を「EOLまたはEOL間近」であることを理由に対象から外した。性能の基準環境もCPython 3.11.xと定めた。

2026-09時点でCore 1.0はまだ実装に着手しておらず（Gate A `Allowed`、Step 1未着手）、releaseはこの後になる。
CPython 3.11のsecurity supportは2027-10に終わり、Core 1.0のrelease時点では同じ理由で「EOL間近」にあたる。
一方、CPython 3.12は2028-10までsupportされ、Ubuntu 24.04 LTSの標準Pythonでもある。
Coreは標準libraryとYAML library 1つだけを使うため、3.11と3.12で利用できる機能に実質的な差はない。

下限は利用者が環境を選ぶ条件であり、release後の変更はCore minor以上の変更になる（ADR-045 Decision 6）。
未releaseの今が、下限をsupport期間の長い版へ合わせる最も安い時点である。

## Decision

1. **実行環境の下限**: Core 1.0はCPython 3.12以上を対象とする。doctorの検査1はこの下限と比較し、
   下限未満を`SPEC-DOCTOR-CORE-001`／`blocked`とする。実装は3.12で動作する構文と標準library APIだけを使い、
   より新しいversionでのみ利用可能な機能へ依存しない。性能の基準環境はCPython 3.12.xとする。
   本項は[ADR-045](ADR-045_実行環境と配布物の確定.md) Decision 1を置き換える。
2. **適合harnessの下限版**: `SINGLE-127-19`は`python: "3.12"`でdoctorを起動する。Gate Cでは、全matrixを
   下限CPython 3.12と基準環境の2環境で通すことを要求する。`python`を指定したfixtureは指定versionだけで判定する。
   本項は[ADR-046](ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md) Decision 2のうち下限版の値だけを
   置き換え、`invocation.python`の意味、環境の作り方、skipしない規則は変えない。
   `runner: package`の`metadata` caseが検査するrequires-pythonも3.12以上を許すことへ改める。
3. **source treeの宣言**: `plugins/bitz-core/pyproject.toml`はrequires-python `>=3.12`を宣言する。
   本項は[ADR-049](ADR-049_Coreのsource配置と試験の構成を確定する.md) Decision 1の図にある
   requires-pythonの値だけを置き換え、配置は変えない。
4. ADR-045のDecision 2〜6、ADR-046のDecision 1、3〜5、ADR-049のDecision 2〜6は変更しない。

## Consequences

- Core 1.0のsupport期間中に下限がEOLへ達する時期が1年遅くなり、release直後に下限を引き上げる必要がなくなる。
- CPython 3.11だけを使える環境はCore 1.0の対象外になる。`uv`などでCPython 3.12を導入すれば利用できる。
- `SINGLE-127-19`のmanifestと、実行環境・配布物のfixture reviewを変更する。fixtureの変更として
  Gate Aを再認定する（[ADR-051](ADR-051_適合fixtureの変更手続きを確定する.md)）。
- 性能の基準環境の`pythonVersion`が変わる。性能baselineはまだ取得していないため、比較不能になる過去の測定はない。

## Alternatives

1. **下限を3.11のまま保つ**: 規範の変更は不要だが、Core 1.0のrelease時点で下限がEOL間近になり、
   ADR-045自身の選定理由と合わない。release後の引上げはminor以上の変更になる。採用しない。
2. **下限を3.13へ引き上げる**: support期間はさらに1年長いが、Ubuntu 24.04 LTSの標準Pythonで動かなくなり、
   多くの利用者に別途の導入を求める。3.13でだけ使える標準library APIへの需要もない。採用しない。

## Notes

- 変更の根拠は規範文（ADR-045 Decision 1の選定理由）の側にあり、Core実装の観測出力ではない。
  fixtureの変更は、規範文を先に変更したうえでの期待値の訂正にあたり、人間の管理者が2026-09-24に承認した。
- 反映先: [Core実行環境・CLI基盤契約 §2](../../03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#2-実行環境と配布物)、
  [doctor仕様 §3.1](../../03.詳細設計/03_操作仕様/04_doctor.md#31-実行環境の下限)、
  [適合fixture仕様 §3・§6.11](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、
  [Core 1.0実装計画 §9.1](../../04.提案資料/12_Core-1.0実装計画.md#91-gate-c-core-10-release受入)、
  `fixtures/conformance/single/SINGLE-127-19/manifest.json`、`fixtures/performance`の基準環境。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-24 | CPythonの下限と性能の基準環境を3.12へ引き上げ、ADR-045 Decision 1、ADR-046 Decision 2、ADR-049 Decision 1の該当値を部分改訂 | ADR-045、ADR-046、ADR-049 |
