# EARS-AI構文・候補抽出fixtureレビュー

2026-09-08。SINGLE-007、008、009-01/02/03、010-01/02、011、012-01/02/03、013の12件を対象とする。
入力・期待結果の準備レビューであり、CoreのParserやScannerの実装・実行結果ではない。

## 単一原因と期待結果

全fixtureは独立した最小設定とREQ-001を持つ。正常なFrontmatter、対応するH1、非空の必須H2、
正常な規範文AC-01を共通の土台にし、16行目だけに検査対象を置く。007と008はFrontmatterのstatusだけが異なる。
code・test・関係・bindingを置かず、入力全体を固定metadataでcommitし、check --full --base HEAD --format jsonで検査する。
正常文を残すことでapproved REQの妥当規範文0件を別原因として混ぜない。

| ID | 検査対象 | Diagnostic | status / exit | 完全検査した文書 / 規範文 |
|---|---|---|---|---|
| SINGLE-007 | approvedでMUST直後にREASON | EAI-CORE-SYNTAX-001 / error | failed / 1 | 0 / 0 |
| SINGLE-008 | 同じ本文をdraftにする | EAI-CORE-SYNTAX-001 / warning | passed_with_warnings / 0 | 1 / 1 |
| SINGLE-009-01 | REQ-01:AC-02（桁不足） | EAI-CORE-ID-001 / error | failed / 1 | 0 / 0 |
| SINGLE-009-02 | UNKNOWN-001:AC-02（未知prefix） | EAI-CORE-ID-001 / error | failed / 1 | 0 / 0 |
| SINGLE-009-03 | REQ-001:AC-02:R-01（3階層） | EAI-CORE-ID-001 / error | failed / 1 | 0 / 0 |
| SINGLE-010-01 | - [x] で始まるcheckbox | なし | passed / 0 | 1 / 1 |
| SINGLE-010-02 | list本文先頭のcode span内の角括弧 | なし | passed / 0 | 1 / 1 |
| SINGLE-011 | draftでAC-01を2回定義 | EAI-CORE-ID-002 / error | failed / 1 | 0 / 0 |
| SINGLE-012-01 | CONSTRAINT tagの閉じ角括弧だけ欠如 | EAI-CORE-SYNTAX-004 / error | failed / 1 | 0 / 0 |
| SINGLE-012-02 | operation本文のcode spanだけ未閉鎖 | EAI-CORE-SYNTAX-005 / error | failed / 1 | 0 / 0 |
| SINGLE-012-03 | 行末句点だけ欠如 | EAI-CORE-SYNTAX-006 / error | failed / 1 | 0 / 0 |
| SINGLE-013 | quality namespaceのopaque extension | EAI-EXT-UNKNOWN-001 / warning | passed_with_warnings / 0 | 1 / 2 |

009系はすべてdraftとし、ID系がwarningに降格しないことも固定する。形式不正IDは候補に残し、
本文への読み替えや自動修正を許可しない。010系の説明行は規範文の件数へ加えない。
010-02はinline codeから始まるため、行頭の正確な `- [` に一致しない。
規範文内部のcode span解析の全般的な網羅をこの1件で証明するものではない。

011では規範文全体を同じIDで再掲し、重複以外のsyntax違反を作らない。draftでもID errorを維持する。
012系はapprovedとし、正常なAC-01を残す。012-01は閉じ角括弧の欠如、012-02は終了backtickの欠如だけを原因とする。
これらに伴うtag不足や句点を認識できない問題は同じraw原因からの派生であり、registryのprimaryだけを1件返す。
012-03はcode spanやtagをすべて閉じ、句点だけを削除する。
013はIDとACTORの間に `[quality:LEVEL="basic"]` を挿入する。extensionを除いてもCoreの意味が成立し、
未知namespaceを保持して警告した後、正常なAC-01とAC-02の両方を完全検査する。
checkの公開結果にIRはないため、実装によるopaque値保持そのものの確認はGate BのIR検証へ委ねる。

## 完全期待JSONの選択

- 構文errorとID errorはregistryのskip-documentに従い、その文書を後段の完全検査へ進めない。
  したがって失敗fixtureのcheckedDocumentCountとcheckedStatementCountは0。先に読んだ正常文を完了件数へ加えない。
- draftの順序warningはcontinueであり、正常なAC-01を1件として完全検査する。不正なAC-02は妥当規範文に数えない。
- extension warningは構文不適合ではないため、013では拡張を含むAC-02も規範文の件数へ加える。
- Diagnosticは原因ごとに1件だけ。sourceはfile、workspaceIdはroot、pathは.spec/requirements/REQ-001.md。
  tag順序は16行61列のREASON開始角括弧、ID形式は16行3列のID開始角括弧へ位置を固定する。
  61列は日本語を含む行のUnicode code point数であり、UTF-8 byte offsetではない。
- 追加5件も16行目を指す。011は2回目のID開始3列、012-01は未閉鎖tag開始56列、
  012-02は開始backtickの73列、012-03は句点の挿入位置である行末の次の79列、013はextension開始19列。
  句点欠落に文字そのものはないため、行末+1を今回の受入期待値として固定する。
- summaryは各expected/check.jsonの固定文字列とし、specRefs、evidence、suggestedAction、source.keyは付加しない。
  未定義の規範文IDを確定した参照として出力しない。
- Git IDとdurationだけは既存の共通normalizerで比較する代表値を置く。配列、件数、Diagnostic位置は除外しない。

これらは今回固定した受入期待値であり、既存Coreから採取した結果ではない。
根拠は[言語仕様 §4・§5・§8](../../../docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)、
[文書テンプレート §2](../../../docs/03.詳細設計/02_SPECモデル/03_文書種別・本文テンプレート.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[結果契約](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)。

## 準備検証と残る受入

ears_fixtures.pyは限定された固定入力とのbyte一致、3つのplain-string Frontmatter fieldのREQ Schema適合、
完全期待JSON、manifest、read-only副作用期待値を検査する。汎用YAML解析やEARS構文判定は実装しない。
Diagnosticが指すtoken位置はPythonのUnicode文字列から独立に数え直す。
各入力を2つの隔離directoryへsetupし、repository、Git status/index、HOME/cache/TMPDIRが固定before snapshotと一致することを確認する。
after snapshotはbeforeと同一の期待値であり、Core実行後の実測値ではない。

回帰試験では列・行の変更、draft severityの変更、Diagnostic欠落、検査件数の変更、誤検出したstatus、
正常規範文の削除を拒否する。実際の候補抽出、構文検査、停止・継続、stdout、終了コード、副作用はGate Bで受け入れる。
追加回帰試験では重複IDのwarning降格、未閉鎖tagのcode取り違え、code spanと行末の位置違い、
extension警告による後続解析の省略を表す件数改変を拒否する。
2026-09-11追記: 導入・設定9件と[文書構造・UTF-8の9件](document-review.md)、[関係・path・coverageの6件](trace-review.md)と合わせて36/311件を準備済み。
残275件とgolden Context Digest等があるためGate AはBlockedのままとする。
