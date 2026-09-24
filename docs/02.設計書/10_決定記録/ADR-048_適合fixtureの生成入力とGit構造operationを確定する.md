---
id: ADR-048
title: 適合fixtureの生成入力とGit構造operationを確定する
status: accepted
relations:
  requires:
    - ADR-046
  related:
    - ADR-042
    - ADR-047
---

# ADR-048 適合fixtureの生成入力とGit構造operationを確定する

## Context

[適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)は、fixtureの入力を`repo/`のversion管理した
treeと`changes/`の差替えfileだけで表す。複合workspaceの最小matrixに残る26件は、この形では表せない。

1. **上限境界の24件**（`MULTI-020-01..16`、`MULTI-021-01..08`）は、`inputBytes`が256 MiB、
   `relationEdgeCount`と`traceEntryCount`が100万件など、[複合workspace仕様 §10](../../03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#10-上限とgit前提)の
   hard limitの前後を入力にする。3つの値（`limit - 1`、`limit`、`limit + 1`）を8 dimension分commitすると、
   repositoryは1 GiBを超え、checkoutのたびに同じ量を展開することになる。
2. **member pathのGit構造2件**（`MULTI-007-02`、`MULTI-007-03`）は、member pathがsubmoduleまたは別worktreeで
   あることを入力にする。gitlink、`.gitmodules`、worktreeの`.git` fileはGitのmetadataであり、`repo/`の通常fileとして
   version管理できない。Gitは`.git`を含むpathの追跡自体を拒否する。

どちらも「fixtureが表せないから検査しない」で済ませると、matrixの行を緩和することになる。
[適合fixture仕様 §1](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#1-所有範囲)はmatrixの行の削除・緩和を禁じている。

## Decision

1. **生成入力**: fixtureは`repo/`の代わりに`setup.generate`を持てる。`setup.generate`は`dataset`（fixture directory
   相対のdataset manifest）と`treeDigest`（生成treeの期待digest）を必須とし、harnessはsetupの前に
   dataset manifestから入力treeを決定論的に生成する。生成したtreeのdigestが`treeDigest`と異なればfixture errorとする。
   `setup.generate`と`repo/`は排他とする。dataset manifestは、越える1つのdimensionと、その他のdimensionを
   通常規模へ保つbaselineだけを持つ。生成器はCoreではなくfixture harness側の参照実装とする。
   生成fixtureは期待結果と副作用期待値も同じdataset manifestから導き、`expect.resultDigest`と
   副作用の`stateDigest`で固定する。生成物を期待fileとしてversion管理せず、reviewの対象は生成器と
   dataset manifestとする。

2. **tree digest**: 生成treeのdigestは、性能fixtureと同じ定義（path昇順で`<相対path>\0<8 byte長><内容>`を連結した
   SHA-256、`sha256:`前置）とする。生成器は同じ列をfilesystemへ書かずに流し込めるものとし、digestの照合に
   256 MiBのtreeの実体化を要求しない。

3. **段階的な検証**: 既定の統合検証（`uv run fixtures/validate_step0b.py`）は、同じdataset manifestを一定比率で
   縮小したprofileで生成器の決定論とdimensionの計数を照合する。実寸の生成とtree digestの照合は
   `uv run fixtures/validate_scale.py`で行い、結果を検証記録へ残す。Gate Aの認定には後者の記録を必要とする。

4. **Git構造operation**: `setup.operations[]`へ次の2つを加える。どちらも`path`と`source`を必須とし、
   `source`は`changes/`配下のdirectoryを指す。

   | `op` | 事前条件 | 結果 |
   |---|---|---|
   | `submodule` | `path`が存在しない | `source`の内容を持つ別repositoryを`path`へ作り、親のindexへgitlinkと`.gitmodules`を記録する |
   | `worktree` | `path`が存在しない | `source`の内容だけを持つcommitを作り、`path`を同じrepositoryの別worktreeとして追加する |

   どちらもharnessの固定した同一性・時刻・branch名を使い、2回のsetupで同じ結果を与える。

5. **snapshotの範囲**: 副作用の比較は、入れ子を含むすべての`.git` directoryとworktreeの`.git` fileを除外する。
   Gitのmetadataそのものはfixtureの入力ではなく、`op`の結果として観測する対象は作業treeのfileと
   親repositoryのstatus・indexとする。生成fixtureでは、この観測値をCanonical JSONのSHA-256（`stateDigest`）で
   固定し、file単位の一覧をversion管理しない。読取り専用の要求は変わらず、実行前後の観測値が同じdigestに
   なることを要求する。

## Consequences

- repositoryの大きさは現状（fixture全体で約30 MiB）から増えない。上限境界の入力、期待結果、副作用期待値は
  dataset manifestとdigestだけをversion管理する。10,000 bindingのverify結果は約7 MiBになるため、
  期待fileとしては保持しない。
- 既定の統合検証は数秒のままになる。実寸の照合は独立したcommandになるため、実行し忘れを記録で検知できるよう、
  検証記録へdigestと実行日を残す。
- 生成器はfixture harnessの一部であり、Coreの実装ではない。Gate Bでは、生成したtreeをCoreへ入力し、
  期待する`SPEC-MULTI-LIMIT-001`と通過を判定する。
- `submodule`と`worktree`のoperationはGitの実装差の影響を受ける。harnessの自己試験で、作成したGit構造が
  想定どおり（gitlink、`.gitmodules`、worktreeの`.git` file）であることを確認する。
- 生成fixtureは`repo/`を持たないため、fixtureの構造検査（matrix、期待file、参照の閉包）は
  `setup.generate`を持つfixtureへ`dataset`の存在確認を適用する。

## Alternatives considered

- **実treeをcommitする**: 1 GiBを超えるrepositoryになり、fresh checkoutからのGate A全体実行にも同じ時間がかかる。
  matrixの目的は上限の安全な停止の確認であり、入力の保存ではない。
- **上限境界をGate Bへ先送りする**: matrixの行を緩和することになり、§1に反する。
- **`.git`を含むpathをfixtureへ置く**: Gitが追跡を拒否するため、version管理できない。tarなどへ固めると、
  fixtureの入力がreviewできない不透明なbinaryになる。

## Notes

- 反映先: [適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md) §2・§3・§3.2・§5、
  `fixtures/conformance/manifest.schema.json`、`fixtures/conformance/harness.py`、
  `fixtures/conformance/multi_generator.py`、`fixtures/validate_scale.py`。
- matrixの行（`MULTI-007-02/03`、`MULTI-020-*`、`MULTI-021-*`）は変更しない。本ADRは、それらを表す手段だけを加える。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-18 | 生成入力`setup.generate`、段階的な検証、Git構造operationを確定 | 適合fixture仕様 §2・§3.2 |
| 2026-09-24 | Decision 3の既定の統合検証`fixtures/validate_step0b.py`を`fixtures/validate_conformance.py`へ改名（非意味的な訂正） | 適合fixture検証記録 |
