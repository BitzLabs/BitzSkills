---
id: FLW-FR-013
version: 1.1
status: implementing
domain: workflow
priority: high
origin: SI-FLW-006, SI-FLW-029
verification_method: unit-test
derived_from: FLW-FR-004
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-013 失敗resultの安全な契約内復帰

- **説明**: 失敗resultからの復帰候補を、operationの副作用とreconcile状態に応じた安全なdomain/actionへ限定し、回復不能時は契約内で人間停止を表現する。
- **受入基準 (EARS)**:
  - WHEN操作が失敗する THEN bitz-flowはoperation、phase、stage、code、cause、reconcile stateからrecovery classを決定し、そのclassで許可された`next_actions`だけを返すこと SHALL
  - WHEN read-onlyで安全に回復可能な入力失敗が起きる THEN bitz-flowは許可されたdomain/actionと秘密値を含まない正規化引数だけを復帰候補として返すこと SHALL
  - WHEN writeがPARTIAL、INDETERMINATE、STALEまたは副作用不明になる THEN bitz-flowはread-onlyのinspect/reconcileまたは人間停止だけを返し、apply、代替ref/path補完、blind retryを提示しないこと SHALL
  - WHEN writeの出力上限超過または分類不能failureを検出する THEN bitz-flowは観測causeとoperation別postconditionを分離し、照合不能時は`INDETERMINATE`とtarget quarantineで再applyを禁止すること SHALL
  - WHEN安全な機械復帰候補が無い THEN bitz-flowは空の`next_actions`と構造化された`stop_reason`、`required_human_input`を返すこと SHALL
  - WHEN失敗入力を診断へ含める THEN bitz-flowは引数名、repo相対の安全表現、長さ、digest、許容候補だけを返し、絶対path、URL userinfo、token pattern、改行・制御文字を公開しないこと SHALL
  - WHEN 非okのresultを組み立てる THEN bitz-flowは`cause`、`recovery_class`、`next_actions`をrecovery matrixと許可語彙から決定して載せ、いずれかを欠く非okのresultを組み立て時に拒否すること SHALL
  - WHEN recovery classが`human-stop`である THEN bitz-flowは`next_actions`を空にし、`required_human_input`を必須で載せること SHALL
  - WHEN 新しい失敗経路を追加する THEN 上記の充足検査はoperation個別ではなくresult組み立て層で行われること SHALL
- **検証手段**: cause単位の一律NEXT生成を負の対照とし、recovery matrix、write再apply 0件、入力sanitizer、空NEXT時のhuman guidanceをunit testする。
- **Revision History**:
  - 1.1 (2026-08-17) 非okのresultに`cause`/`recovery_class`/`next_actions`を必須化し、検査をresult組み立て層へ置く要件を追加（`SI-FLW-075`。裁定参照: .spec/reports/decision-2026-08-17-si-flw-072-073-075.md）
  - 1.0 (2026-08-11) FLW-REV-008を受け、verified FLW-FR-004を改訂せず独立要件としてdraft起票
