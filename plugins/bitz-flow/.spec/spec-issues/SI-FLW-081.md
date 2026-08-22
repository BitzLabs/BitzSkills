---
id: SI-FLW-081
raised_by: FLW-TSK-107実装前検査
target: FLW-NFR-014のUNSUPPORTED_APPROVAL_MODE公開result写像
proposed_change_type: modify
status: accepted
---
- **目的**: FLW-NFR-014の`UNSUPPORTED_APPROVAL_MODE`を、既存result-v1のclosed code/cause契約を
  破らず公開CLIへ写像できるようにする。
- **発見した事実**:
  - `UNSUPPORTED_APPROVAL_MODE`は現行result-v1の`code`閉集合に存在しない。
  - `unsupported-approval-mode`も現行`cause`閉集合に存在しない。
  - FLW-TSK-107のpure validatorは内部reasonを返せるが、TSK-109/114でそのまま公開resultへ載せると
    schema違反になる。無言でplan-digestへ降格することは要件違反である。
- **提案する修正**: **accept推薦**。公開resultは既存の`code: UNSUPPORTED`を維持し、closed causeへ
  `unsupported-approval-mode`を追加する。内部validatorのreason codeは`UNSUPPORTED_APPROVAL_MODE`とし、
  TSK-109/114のadapterで上記公開形へ一意に写像する。FLW-NFR-014とFLW-DSN-017の記述も
  「内部reason / 公開code+cause」の区別を明記する。
- **対象ファイル**: `.spec/requirements/FLW-NFR-014.md`、`.spec/design/FLW-DSN-017.md`、
  `.spec/tasks/FLW-TSK-107.md`、`109.md`、`114.md`、`schemas/result-v1.schema.json`、
  `references/output-contract.md`、`flowlib/result.py`と対応test。
- **確認観点**: signed宣言、capability file、trusted registry入力、宣言の存在可能・観測不能で
  `UNSUPPORTED` + `unsupported-approval-mode`、Git副作用0件、未知cause 0件。
- **影響推定・ロールバック**: result codeは加算しないためconsumerの大分類は維持する。causeの加算は
  additive contract変更であり、旧consumerは`UNSUPPORTED`だけでも安全側へ停止できる。
- **依存**: FLW-NFR-014、FLW-DSN-017 v2.1、FLW-TSK-107、FLW-TSK-109、FLW-TSK-114。
