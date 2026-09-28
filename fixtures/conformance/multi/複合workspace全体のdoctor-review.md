# 複合workspace全体のdoctor fixture review

## 1. 目的

`doctor --all-workspaces`の全体事前検査が成功した後、rootと全memberのworkspace固有検査を実行し、
memberの非成功を正しい所有位置へ置いて全体へ集約する公開契約を固定する。

## 2. case

| fixture | 独立した原因 | 必須確認 |
|---|---|---|
| `MULTI-026-01` | なし | rootを先頭、api、webのID順で3 workspaceを返し、global checkをmemberへ複製しない |
| `MULTI-026-02` | api memberのcommand実行file不在 | apiだけをblockedにし、後続webを診断して、最上位をblocked／2へ集約する |

両caseはmember配下を探索起点とし、同じGit rootとroot workspaceを発見できることも固定する。
`MULTI-026-02`は既定text出力を使い、最上位と全memberのcheck合計21件、member Diagnostic 1件を要約へ含める。

## 3. 入力と副作用

入力はroot catalogとapi、webの設定3件だけとし、SPEC文書を置かない。`MULTI-026-02`だけがapiの
`verify.commands.backend.argv`へ存在しない相対実行fileを指定する。doctorはcommandを実行せず、両caseとも
repository、Git index、home、cache、一時directoryを変更しない。

## 4. 期待値の根拠

- [doctor仕様 §3](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md#3-検査順序)
- [doctor仕様 §7](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md#7-結果)
- [複合workspace仕様 §8](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#8-全体操作の共通規則)
- [結果・Diagnostic・終了コード §2.3](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#23-doctorの全体結果)
