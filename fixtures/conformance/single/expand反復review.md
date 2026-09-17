# expand反復fixtureレビュー

2026-09-14。SINGLE-127-03とSINGLE-127-04を追加する。
根拠は[CLI基盤契約 §5](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#5-共通cli-argv解析)、
[context仕様](../../../docs/03.詳細設計/03_操作仕様/01_context.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の該当IDである。

| ID | 入力のexpand値（指定順） | 期待projection.expanded |
|---|---|---|
| SINGLE-127-03 | TECH-001、REQ-001 | REQ-001、TECH-001 |
| SINGLE-127-04 | TECH-001、TECH-001 | TECH-001 |

異なる値は意図的に辞書順の逆で渡し、入力順のまま返す実装を区別する。同値反復は拒否せず1件へまとめる。
非反復optionがエラーになるSINGLE-127-01/02と対をなす。
単一workspaceでは非修飾IDを使用し、連合での修飾ID解決はこの2件の検証対象に含めない。

入力byte列と副作用snapshotはSINGLE-042と同一。purposeはverifyで、REQ-001とTECH-001はいずれも
完全解決集合内に存在する。REQ-001は既にrootとしてfull提示だが、明示expandの正規化集合には保持する。
TECH-001もverify目的でfull提示であるため、本文やcoverageが変わらないことも固定する。
期待結果はpassed／0、Diagnosticなし、report生成0件。projection.expanded以外はgolden結果と一致する。
SINGLE-127-04の全結果は単一expandのSINGLE-043-02とも一致する。

既存Digest検証へ組み込み、独立2系統のreference計算、Canonical JSONとgolden Digestのbyte一致、
入力・完全期待JSON・副作用Schema、各fixtureの2回隔離setupを確認する。
回帰試験ではexpandedの順序逆転・重複残存、反復引数の欠落を拒否する。
Coreのtarget展開やCLI解析は実装・実行せず、Coreの実結果と副作用はGate Bで別途受け入れる。
