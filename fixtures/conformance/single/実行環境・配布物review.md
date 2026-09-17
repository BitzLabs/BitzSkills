# 実行環境・配布物fixture review

2026-09-17。SINGLE-127-15〜19の5件を追加する。作成前に適合harnessの外部仕様を
[提案27](../../../docs/04.提案資料/27_適合harness外部仕様の検討.md)で検討し、
[ADR-046](../../../docs/02.設計書/10_決定記録/ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)として裁定した。
根拠は[Core実行環境・CLI基盤契約 §2・§4](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#2-実行環境と配布物)、
[doctor仕様 §3.1・§6](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md#31-実行環境の下限)、
[適合fixture仕様 §3・§3.4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#34-検査対象と実行環境)である。

## 入力と期待値

| ID | runner／起動 | 環境指定 | 期待 |
|---|---|---|---|
| SINGLE-127-15 | bitz `doctor --format json` | `gitVersion: "2.29.0"` | passed_with_warnings／0、`SPEC-DOCTOR-GIT-001`、git checkはwarningと失われる保証4件 |
| SINGLE-127-16 | bitz `doctor --format json` | `gitVersion: "2.30.0"` | passed／0、git checkはpassed |
| SINGLE-127-17 | package `metadata` | — | accepted／0 |
| SINGLE-127-18 | package `dependencies` | — | accepted／0 |
| SINGLE-127-19 | bitz `doctor --format json` | `python: "3.11"` | passed／0 |

全件が最小設定（SINGLE-001と同じ`bitz.yaml`）だけのunborn repositoryを使う。

127-15／16の版は、実行環境契約の「Gitは2.30以上」から下限の直前（2.29.0）と下限（2.30.0）として導き、
fixture側へ数値を直書きしない。127-15はGitを起動できるが下限未満なので、SINGLE-093のGit不在と同じ縮退結果
（同じDiagnostic、同じ`lostGuarantees`）になる。Gitは存在するのでrepositoryは作るが、doctorはGit状態を
出力しない。127-16はSINGLE-001と同じ成功結果である。shimは`git --version`にだけ偽装した版を返し、他の呼出しは
実Gitへ渡すため、127-16ではdoctorがGitを通常どおり使える。`env.PATH`を同時に変えず、原因を版だけに限る。

127-19は実行環境契約の「CPython 3.11以上」から`python: "3.11"`を導く。doctorを下限versionで起動して成功することを
確認する。3.11で使えない構文・APIへの依存がないことは、Gate Cで全matrixを3.11でも通す条件で担保する。

127-17／18の出力は`{"outcome": "accepted"}`である。caseの内容は適合fixture仕様 §3のrunner表が定め、
監査はcase名が同表にあることと、matrix行が`package test`であることを確認する。

## 準備検証

`environment_fixtures.py`は、manifest・期待結果・副作用期待値のSchema、入力byte列、規範本文から読み取った下限値と
manifestの一致、原因を混ぜない環境指定を確認し、2回の隔離setupでunborn状態とsnapshotの一致を確認する。
統合検証は、bitz以外のrunnerの期待結果が`{"outcome": ...}`だけで、終了コードがoutcomeと対応することも確認する。
回帰試験は、版の入替え、縮退Diagnosticの欠落、Python versionの変更、outcomeの変更、caseの入替え、
`gitVersion`と`env.PATH`の併用、bitz以外のrunnerでの環境指定を拒否する。

shimの生成、`uv`による環境構築、`runner: package`の参照実装は未作成である。Step 0Bでは期待値と規則の整合だけを
固定し、実際の起動と判定はCore実装後のGate Bで確認する。
