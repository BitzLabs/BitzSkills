# 操作仕様

## 1. 所有境界

各操作仕様は自身のCLI/MCP入力、対象選択、処理順、操作固有結果、Diagnosticを所有する。
共通status、Diagnostic field、report条件は[共通契約](../00_共通契約/01_結果・Diagnostic・終了コード.md)、
関係とcoverageは[関係・トレースモデル](../02_SPECモデル/04_関係・トレースモデル.md)を使用する。

## 2. 一覧

| 操作 | 文書 | 主目的 |
|---|---|---|
| `context` | [01_context.md](01_context.md) | 完全Contextとstale防止 |
| `check` | [02_check.md](02_check.md) | 静的検査とGit差分保護 |
| `verify` | [03_verify.md](03_verify.md) | statement対応test実行 |
| `doctor` | [04_doctor.md](04_doctor.md) | 導入・互換性・環境診断 |

## 3. 共通原則

- Core 1.0は単一workspaceと、同一Git repository内の明示的なモノレポ連合を扱う。
- 連合の修飾ID、所有境界、全体操作は[モノレポSPEC連合仕様](../02_SPECモデル/05_モノレポSPEC連合仕様.md)を使う。
- networkとLLMを合否処理に使わない。
- 同じ入力とversionから同じ対象、順序、Diagnosticを返す。
- CoreはSPEC、code、test、Gitを変更しない。`check`と`verify`のfile書込みは明示`--report`だけとする。
