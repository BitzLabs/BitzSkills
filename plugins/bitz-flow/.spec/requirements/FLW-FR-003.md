---
id: FLW-FR-003
version: 1.0
status: implementing
domain: tooling
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-003 単一dispatcherと公開結果契約

- **説明**: bitz-flow v2の全通常操作を単一dispatcherへ集約し、compactとJSONで同じ判定を返す。
- **受入基準 (EARS)**:
  - WHEN 利用者またはエージェントが公開operationを要求する THEN bitz-flowは`flow-core/scripts/flow.py`を唯一の公開実行入口として使用すること SHALL
  - WHEN dispatcherがoperation結果を返す THEN bitz-flowはschema、operation、code、exit code、snapshot、result digest、data、audit、invocation、warnings、truncated、next actionsを公開result契約に従って返すこと SHALL
  - WHEN compact形式を選択または省略する THEN bitz-flowは固定token、固定field順、1項目1行のrendererで結果を返すこと SHALL
  - WHEN JSON形式を選択する THEN bitz-flowはoperation別JSON Schemaを満たすresult objectを返すこと SHALL
  - WHEN operationまたはcapabilityが未対応である THEN bitz-flowは`UNSUPPORTED`を返し、生のGitまたはghコマンドを代替案として出力しないこと SHALL
  - WHEN 件数上限によりresultを省略する THEN bitz-flowはshown、total、snapshot拘束cursor、絞込みnext actionを返すこと SHALL
  - WHEN 状態変更判断に全件確認が必要でresultが省略される THEN bitz-flowはapplyを`BLOCKED`にすること SHALL
- **検証手段**: 公開入口、result schema、renderer順序、終了コード、truncation、raw fallback不在をunit testとgolden fixtureで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) Design Gate承認済みFLW-DSN-003/012/014からdraft起票
