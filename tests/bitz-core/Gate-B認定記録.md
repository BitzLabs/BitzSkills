# Gate B認定記録

[ADR-052](../../docs/02.設計書/10_決定記録/ADR-052_Gate-Bの実行と認定の構成を確定する.md)に従い、
`uv run tests/bitz-core/certify_gate_b.py --step N`でStep 1からNまでの完了fixtureをCoreへ通した結果を記録する。
各Stepの完了fixtureは[実装計画](../../docs/04.提案資料/12_Core-1.0実装計画.md)が正本であり、
`fixtures/conformance/steps.json`はその機械可読な写しである。

## 2026-09-24: Step 1

commit `28c3cd1a50616e6136fd68aecf61cc2e59ca3872`に対して`uv run tests/bitz-core/certify_gate_b.py --step 1`を実行し、
`gateB: {"step": 1, "result": "Passed"}`、error 0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1の完了fixture 34件（`SINGLE-001`〜`006`、`073`〜`074`、`078`、`091`〜`095`、`104-04`、`125-02`、`127-01`〜`02`、`127-05`〜`07`、`127-11`、`127-14`〜`19`） |
| 参照harness | 2つのcloneで各cloneの`plugins/bitz-core`をbuildし、34件すべてpassed。所要時間と検査対象のpathを除いた結果のSHA-256は両方`64306f9c0d2da97a7e72ee29e2e03ac3ef5efbd9add4b18e49999f891b0699ba` |
| Parser adapter | Step 1では不要 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

参照harnessの判定能力は、期待出力を返す偽のCoreによる自己試験（`fixtures/conformance/test_fake_core.py`）で別に確かめた。
偽のCoreは代表48件をすべて通過し、標準出力のJSON、text、終了コード4の標準エラー、reportの内容をそれぞれ1箇所改変すると、
改変したfixtureだけが不通過になった。

Core固有の単体試験（`uv run --project plugins/bitz-core python -m unittest discover -s tests/bitz-core`）は72件がすべて成功した。

Step 1のCoreが後続Stepへ残した暫定実装は次のとおりである。いずれも該当Stepの完了fixtureで判定する。

- `check`の明示対象（`scope: selected`）と引数なし（`scope: changed`）は未実装で、終了コード3を返す。
- `check`はSPEC文書を解析せず、`checkedDocumentCount`と`checkedStatementCount`を0とする。
- `check --report`はreportを保存せず終了コード3を返す（黙って無視しない）。
- `context`と`verify`は引数の検査だけを行い、本体は未実装で終了コード3を返す。
- unborn repositoryの`check --full`は`revision: null`を返すが、Git縮退の詳細はStep 3で扱う。
- 設定の未知keyの警告は最上位keyだけを対象とする。
- 参照harnessは生成fixture（`setup.generate`）、`stateDigest`形式の副作用期待値、実行環境に依存するprocess出力の抜粋の正規化に
  まだ対応しておらず、該当fixtureはerrorとなる。いずれもStep 4以降の完了条件に属する。
