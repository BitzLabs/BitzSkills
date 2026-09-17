# registry閉包 fixture review

2026-09-14。SINGLE-089〜095の7件を追加し、matrix §6.9を完了する。
根拠は[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[doctor仕様](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md)、
[EARS-AI言語仕様](../../../docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)、
[workspace・設定仕様](../../../docs/03.詳細設計/02_SPECモデル/01_workspace・設定仕様.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の各matrix IDである。

| ID | 操作 | 唯一の条件 | status／終了コード | 検査文書／句 |
|---|---|---|---|---|
| SINGLE-089 | check | 理由なし`SHOULD` | passed_with_warnings／0 | 1／1 |
| SINGLE-090 | check | `related`先のTECH-999不在 | passed_with_warnings／0 | 1／1 |
| SINGLE-091 | check | 設定YAMLのanchor | error／3 | 0／0 |
| SINGLE-092 | doctor | 設定`language`の型不正 | error／3 | — |
| SINGLE-093 | doctor | Git不在 | passed_with_warnings／0 | — |
| SINGLE-094 | check | `.spec/bitz.yaml`不在 | blocked／2 | 0／0 |
| SINGLE-095 | check | 未対応EARS-AI major | blocked／2 | 0／0 |

SINGLE-089は既存の有効文書の規範強度だけを`MUST`から`SHOULD`へ替え、`[REASON]`を付けない。
診断位置は固定byte列から再計算した1始まりcode point位置（15行49列、`[SHOULD]`の開始）で照合する。
warningは`continue`のため、文書1件・規範文1件を検査したまま集計する。
SINGLE-090は`relations.related`だけを足し、strong relationを混ぜない。参照先IDはcorpusのどのfileにも存在させない。

SINGLE-091は最小設定との差分をanchor 1個に限り、aliasを同居させない。設定を解釈できないため
workspace同一性はnull、検査件数は0である。SINGLE-092はSINGLE-004-01の査読済み入力をそのまま使い、
同じ条件をdoctorで呼ぶ。doctor固有のconfig codeは返さず`SPEC-CONFIG-SCHEMA-001`だけとする。
`checks[]`はdoctor仕様§3の処理順に従い、設定を解釈できない時点で依存checkを実行しないため、
core／workspace／config／gitの4件だけを置く。SINGLE-002の設定不在と同じ扱いである。

SINGLE-093はSINGLE-001との差分をGit不在だけにし、`checks[]`は同じ8件のまま`git`だけをwarningへ替える。
`lostGuarantees`の4つの安定名はdoctor仕様§6へ追記して固定し、review台帳のsource hashを更新した。
Git不在は隔離setupで観測した性質として扱い、setupはGitを初期化せず、副作用snapshotの`git`はnullとする。
成功したGit statusの空文字列でGit不在を表さない。

SINGLE-094は設定を置かない空の非SPEC fileだけをcommitし、`SPEC-WORKSPACE-MISSING-001`をcheckの
environment sourceで返す。doctor専用の`SPEC-DOCTOR-WORKSPACE-001`はここでは使わない。
SINGLE-095は最小設定との差分を`earsAi`のmajorだけに限る。Schema majorの`SPEC-CONFIG-SCHEMA-001`と
異なるcodeであること、設定自体は妥当なためworkspace同一性が確定することを固定する。

入力byte列・manifest・完全結果・副作用Schemaを検証し、隔離Git repositoryを2回setupして固定snapshotへ照合する。
副作用は全件読取り専用とし、Git snapshotの有無が査読した環境と一致することも検査する。
回帰試験は位置・severity・同一性・doctor check status・`lostGuarantees`・code・副作用の改変を拒否し、
さらに各入力を修復した場合とSINGLE-094へworkspaceを足した場合も拒否する。
YAML parser、Git検出、doctorの検査手順、Coreは実装も実行もしない。実際のcheck継続とdoctor出力はGate Bで受け入れる。
