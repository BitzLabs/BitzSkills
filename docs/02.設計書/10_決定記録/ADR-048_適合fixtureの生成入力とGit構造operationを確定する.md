---
id: ADR-048
title: 適合fixtureの生成入力とGit構造の準備の処理を確定する
status: accepted
relations:
  requires:
    - ADR-046
  related:
    - ADR-042
    - ADR-047
---

# ADR-048 適合fixtureの生成入力とGit構造の準備の処理を確定する

## Context

[適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)は、fixtureの入力を`repo/`のバージョン管理した
木構造と、`changes/`の差替えファイルだけで表す。複合ワークスペースの最小matrixに残る26件は、この形では表せない。

1. **上限境界の24件**（`MULTI-020-01..16`、`MULTI-021-01..08`）は、`inputBytes`が256 MiB、
   `relationEdgeCount`と`traceEntryCount`が100万件などの、[複合ワークスペース仕様 §10](../../03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#10-上限とgitの前提)の
   絶対上限の前後を入力にする。3つの値（`limit - 1`、`limit`、`limit + 1`）を8つの次元の分だけコミットすると、
   リポジトリは1 GiBを超え、チェックアウトのたびに同じ量を展開することになる。
2. **メンバーのパスのGit構造2件**（`MULTI-007-02`、`MULTI-007-03`）は、メンバーのパスがサブモジュールまたは別のワークツリーで
   あることを入力にする。gitlink、`.gitmodules`、ワークツリーの`.git`ファイルはGitのメタデータであり、`repo/`の通常ファイルとして
   バージョン管理できない。Gitは`.git`を含むパスの追跡自体を拒否する。

どちらも「fixtureが表せないから検査しない」で済ませると、matrixの行を緩和することになる。
[適合fixture仕様 §1](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#1-本書の範囲)はmatrixの行の削除・緩和を禁じている。

## Decision

1. **生成入力**: fixtureは`repo/`の代わりに`setup.generate`を持てる。`setup.generate`は`dataset`（fixtureのディレクトリからの
   相対パスで指定するデータセットのマニフェスト）と`treeDigest`（生成した木構造の期待するハッシュ値）を必須とし、
   harnessは準備手順の前に、データセットのマニフェストから入力の木構造を決定論的に生成する。
   生成した木構造のハッシュ値が`treeDigest`と異なればfixtureのエラーとする。
   `setup.generate`と`repo/`は排他とする。データセットのマニフェストは、越える1つの次元と、ほかの次元を
   通常の規模に保つベースラインだけを持つ。生成器はCoreではなく、fixtureのharness側の参照実装とする。
   生成fixtureは期待結果と副作用の期待値も同じデータセットのマニフェストから導き、`expect.resultDigest`と
   副作用の`stateDigest`で固定する。生成物を期待ファイルとしてバージョン管理せず、レビューの対象は生成器と
   データセットのマニフェストとする。

2. **木構造のハッシュ値**: 生成した木構造のハッシュ値は、性能fixtureと同じ定義（パスの昇順で`<相対path>\0<8 byte長><内容>`を連結した
   SHA-256に、`sha256:`を前置する）とする。生成器は同じ列をファイルシステムへ書かずに流し込めるものとし、ハッシュ値の照合に
   256 MiBの木構造の実体化を要求しない。

3. **段階的な検証**: 既定の監査（`uv run fixtures/validate_step0b.py`）は、同じデータセットのマニフェストを
   一定の比率で縮小した規模の設定で、生成器の決定論と次元の計数を照合する。実寸の生成と木構造のハッシュ値の照合は
   `uv run fixtures/validate_scale.py`で行い、結果を検証記録へ残す。Gate Aの認定には後者の記録を必要とする。

4. **Git構造の準備の処理**: `setup.operations[]`へ次の2つを加える。どちらも`path`と`source`を必須とし、
   `source`は`changes/`配下のディレクトリを指す。

   | `op` | 事前条件 | 結果 |
   |---|---|---|
   | `submodule` | `path`が存在しない | `source`の内容を持つ別のリポジトリを`path`へ作り、親のインデックスへgitlinkと`.gitmodules`を記録する |
   | `worktree` | `path`が存在しない | `source`の内容だけを持つコミットを作り、`path`を同じリポジトリの別のワークツリーとして追加する |

   どちらもharnessの固定した同一性・時刻・ブランチ名を使い、2回の準備手順のどちらでも同じ結果を与える。

5. **スナップショットの範囲**: 副作用の比較は、入れ子を含むすべての`.git`ディレクトリと、ワークツリーの`.git`ファイルを除外する。
   Gitのメタデータそのものはfixtureの入力ではなく、`op`の結果として観測する対象は作業ツリーのファイルと
   親リポジトリの状態・インデックスとする。生成fixtureでは、この観測値を正規JSONのSHA-256（`stateDigest`）で
   固定し、ファイル単位の一覧をバージョン管理しない。読取り専用の要求は変わらず、実行の前後の観測値が同じハッシュ値に
   なることを要求する。

## Consequences

- リポジトリの大きさは現状（fixture全体で約30 MiB）から増えない。上限境界の入力、期待結果、副作用の期待値は、
  データセットのマニフェストとハッシュ値だけをバージョン管理する。10,000個のテスト割当てを持つ`verify`の結果は約7 MiBになるため、
  期待ファイルとしては保持しない。
- 既定の監査は数秒のままになる。実寸の照合は独立したコマンドになるため、実行し忘れを記録で検知できるよう、
  検証記録へハッシュ値と実行日を残す。
- 生成器はfixtureのharnessの一部であり、Coreの実装ではない。Gate Bでは、生成した木構造をCoreへ入力し、
  期待する診断`SPEC-MULTI-LIMIT-001`と通過を判定する。
- 準備の処理`submodule`と`worktree`はGitの実装差の影響を受ける。harnessの自己試験で、作成したGitの構造が
  想定どおり（gitlink、`.gitmodules`、ワークツリーの`.git`ファイル）であることを確認する。
- 生成fixtureは`repo/`を持たないため、fixtureの構造検査（matrix、期待ファイル、参照の閉包）は
  `setup.generate`を持つfixtureへ`dataset`の存在確認を適用する。

## Alternatives considered

- **実際の木構造をコミットする**: 1 GiBを超えるリポジトリになり、新しいチェックアウトからのGate A全体の実行にも同じ時間がかかる。
  matrixの目的は上限の安全な停止の確認であり、入力の保存ではない。
- **上限境界をGate Bへ先送りする**: matrixの行を緩和することになり、§1に反する。
- **`.git`を含むパスをfixtureへ置く**: Gitが追跡を拒否するため、バージョン管理できない。`tar`などへ固めると、
  fixtureの入力がレビューできない不透明なバイナリになる。

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
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
