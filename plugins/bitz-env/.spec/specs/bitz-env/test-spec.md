# テスト仕様書: bitz-env（v0.3.0 時点）

sdd-test 工程で EARS 要件から導出したテスト仕様。導出規則は sdd-test
references/test-derivation.md、green 基準は sdd-core references/verification.md に従う。

- 実行コマンド（自動テスト）: `.venv/bin/pytest tests/test_env_guard.py`
- 最終実行: 2026-07-11 — **40 passed** (0.61s)

---

## A. 自動検証（pytest 実装済み）

### テスト仕様: ENV-FR-001 同梱フックによる破壊的操作の deny

- **対象要件**: ENV-FR-001
- **EARS 節**:
  - WHEN ツール実行の引数が破壊的操作5種のいずれかに一致する THEN プラットフォームの契約に従い deny 応答を返す SHALL
  - WHEN 引数がいずれのパターンにも一致しない THEN 空応答 `{}` を返し実行に介入しない SHALL
- **導出元種別**: Event-Driven（BDD シナリオ + パラメータ化テスト）
- **Verification Method**: example-test
- **テストケース一覧**（tests/test_env_guard.py）:
  - `test_claude_denies_destructive` × 破壊的コマンド8種（deny 5パターンの変種含む）
  - `test_antigravity_denies_destructive` × 同8種
  - `test_claude_passes_safe` / `test_antigravity_passes_safe` × 安全コマンド6種（誤検知なし）
- **検証ステータス**: green（2026-07-11、28ケース PASS）

### テスト仕様: ENV-FR-002 プラットフォーム自動判別と安全な失敗

- **対象要件**: ENV-FR-002
- **EARS 節**:
  - WHEN stdin に toolCall キーを含む JSON THEN Antigravity の契約（decision）で応答 SHALL
  - WHEN stdin に tool_name / tool_input キーを含む JSON THEN Claude Code の契約（hookSpecificOutput.permissionDecision）で応答 SHALL
  - IF stdin が JSON としてパースできない THEN 空応答 `{}` を返し正常終了 SHALL
- **導出元種別**: Event-Driven（契約判別）+ Unwanted Behavior（fail-open 異常系）
- **Verification Method**: example-test
- **テストケース一覧**:
  - `test_platform_detection_claude_contract` / `test_platform_detection_antigravity_contract`
  - `test_fail_open_on_invalid_or_unknown` × 4（非JSON・空・`{}`・unknown 形状）
  - `test_unknown_shape_still_denies_destructive`（unknown 形状でも保守側に倒す）
- **検証ステータス**: green（2026-07-11、7ケース PASS）

### テスト仕様: ENV-FR-008 rules/*.md の両プラットフォーム読み込み

- **対象要件**: ENV-FR-008
- **EARS 節**:
  - WHEN Claude Code のセッションが開始される THEN SessionStart フックで rules/*.md を stdout へ出力しコンテキストに注入 SHALL
  - WHEN Antigravity でプラグインが有効 THEN rules/*.md はシステムルールへマージされる SHALL
  - IF rules/ が空または読めない THEN フックはエラーでセッションを妨げない SHALL
- **導出元種別**: Event-Driven + Optional Feature（プラットフォーム構成別）
- **Verification Method**: example-test
- **テストケース一覧**:
  - `test_hooks_json_defines_sessionstart_rules_injection`（hooks.json の SessionStart 定義）
  - `test_sessionstart_command_outputs_rules_content`（注入コマンドの実行出力にルール本文を含む）
- **検証ステータス**: yellow — 自動テストは green（2026-07-11、2ケース PASS）だが、
  要件の検証手段に含まれる**実環境での注入確認（プラグインインストール後）が未実施**
  （ENV-TSK-005 備考の残タスク）。Antigravity ネイティブ rules マージはプラットフォーム
  仕様のため同確認に含める。完了まで verified 提案を保留。

### テスト仕様: ENV-NFR-001 ガードの応答時間

- **対象要件**: ENV-NFR-001
- **EARS 節**: WHEN env_guard.py が1回のフック呼び出しを処理する THEN 通常環境で 200ms 以内に応答を返す SHALL
- **導出元種別**: 性能要件（benchmark。要件本文に数値閾値 200ms 明記済み）
- **Verification Method**: benchmark
- **テストケース一覧**:
  - `test_env_nfr_001_hook_response_time_within_200ms` × 3（allow / deny / 不正 JSON。
    subprocess 起動込み 7回計測の最小値 < 200ms で判定 — 偶発ジッタに強い方式）
- **検証ステータス**: green（2026-07-11、3ケース PASS）

---

## B. スキル振る舞い検証（evals/ シナリオテスト — 2026-07-12 実施済み。各 evals/<skill>/report.md 参照）

以下は SKILL.md 駆動のエージェント振る舞いが対象のため、skill-tester による
evals/<skill>/ シナリオテストで検証する（要件の検証手段欄に規定済み）。
2026-07-12 に全25ケースを実行し skill-evaluator が採点済み（各 evals/<skill>/report.md）。
改善提案は SI-ENV-008〜017/020/021 として起票（高3件は同日 accepted・反映済み）。

### テスト仕様: ENV-FR-003 env-init のユーザー確認付き生成

- **導出元種別**: Event-Driven / **Verification Method**: example-test（evals/env-init/）
- **導出テストケース**:
  - `ENVFR003-S1_新規生成は承認後にのみ書き出す`（承認前に書き出しがないこと）
  - `ENVFR003-S2_既存ファイルは上書きせずdiffとマージ案を提示`
  - `ENVFR003-S3_permissionsマージで既存deny/askを削除しない`
- **検証ステータス**: green（2026-07-12、evals/env-init TC-01/02。report.md 参照）

### テスト仕様: ENV-FR-004 マーカー区間による再生成

- **導出元種別**: Event-Driven + Unwanted Behavior / **Verification Method**: example-test（evals/env-init/・evals/env-register/）
- **導出テストケース**:
  - `ENVFR004-S1_更新はマーカー区間内側のみ書き換え`（区間外バイト列不変のアサーション。
    要件 v1.1 で「区切り空白・改行は開始タグの内側に含め、区間外へ新規バイトを追加しない」
    ことまで含むと明確化 — SI-ENV-008）
  - `ENVFR004-S2_マーカー不在時はenv-init実行を案内し区間を新設しない`
- **検証ステータス**: green（2026-07-12、evals/env-init TC-02 再テスト runs/10（v1.1 基準）・env-register TC-04）

### テスト仕様: ENV-FR-005 モデル非依存の役割割り当てと劣化動作・防御的協調

- **導出元種別**: Event-Driven + Unwanted Behavior（劣化系）+ Optional Feature（WHERE 節） / **Verification Method**: example-test（evals/env-init/・evals/env-orchestration/）
- **導出テストケース**:
  - `ENVFR005-S1_中心モデル確認とadvisor/worker割り当て案の提示・ユーザー確定`
  - `ENVFR005-S2_advisor利用不可時は相談スキップで続行し成果物に明記`（劣化動作）
  - `ENVFR005-S3_合議1名時は相談型へ格下げ`
  - `ENVFR005-S4_検収はDIGEST非依存でgit_diff等の客観状態を中心が取得`
  - `ENVFR005-S5_worker/advisorからのネスト委譲を拒否`
- **検証ステータス**: green（2026-07-12、evals/env-orchestration TC-02〜05・env-init TC-01）

### テスト仕様: ENV-FR-006 協調アダプタの契約チェックと登録・役割ルーティング

- **導出元種別**: Event-Driven + Unwanted Behavior（非準拠拒否） / **Verification Method**: example-test（evals/env-register/・evals/env-orchestration/）
- **導出テストケース**:
  - `ENVFR006-S1_準拠アダプタの登録とルーティングテーブル記録・委譲マトリクス更新`
  - `ENVFR006-S2_delegate役割または能力宣言を欠く候補は理由報告のうえ登録しない`
  - `ENVFR006-S3_スキル名衝突は名前空間プレフィックスと優先順で解決`
  - `ENVFR006-S4_委譲先解決はレジストリ経由で固定スキル名を直接呼ばない`
  - `ENVFR006-S5_アンインストール済みアダプタはユーザー確認のうえエントリ削除`
- **検証ステータス**: green（2026-07-12、evals/env-register TC-01〜03/05・env-orchestration TC-01）

### テスト仕様: ENV-FR-007 env-doctor による3層同期診断

- **導出元種別**: Event-Driven + Unwanted Behavior + State-Driven（WHILE 未承認） / **Verification Method**: example-test（evals/env-doctor/）
- **導出テストケース**:
  - `ENVFR007-S1_診断はPASS/WARN/FAILで報告しFAIL/WARNに修正案を付す`
  - `ENVFR007-S2_層間不一致は強い方に揃える提案のみ（緩和方向を自動提案しない）`（ズレ注入）
  - `ENVFR007-S3_ユーザー承認前は修正を実施しない`（状態 ON/OFF 分岐）
- **検証ステータス**: green（2026-07-12、evals/env-doctor TC-01〜03）

### テスト仕様: ENV-FR-009 env-init 生成物の復旧可能性

- **導出元種別**: Event-Driven + Unwanted Behavior / **Verification Method**: example-test（evals/env-init/）
- **導出テストケース**:
  - `ENVFR009-S1_git管理外では書き込み前に.bakを作成`
  - `ENVFR009-S2_git管理下では.bak省略可`
  - `ENVFR009-S3_git未管理ならgit_initを案内`
- **検証ステータス**: green（2026-07-12、evals/env-init TC-03）

### テスト仕様: ENV-FR-010 生成物のトラッキングと env-uninstall（旧名 env-destroy）による撤去

- **導出元種別**: Event-Driven + Optional Feature（WHERE 節）+ Unwanted Behavior（レジストリ欠落） / **Verification Method**: example-test（evals/env-destroy/）
- **導出テストケース**:
  - `ENVFR010-S1_env-initは生成一覧とマーカー区間位置をレジストリに記録`
  - `ENVFR010-S2_env-destroyは記録に基づく一覧提示とユーザー確認後の撤去`
  - `ENVFR010-S3_既存ファイルはマーカー区間のみ除去しユーザー記述を保持`
  - `ENVFR010-S4_レジストリ欠落時は推測削除せず候補報告に留める`
- **検証ステータス**: green（2026-07-12、evals/env-init TC-01・env-destroy TC-01〜03）

### テスト仕様: ENV-CON-003 生成・記録は対象プロジェクト内に限定

- **導出元種別**: Ubiquitous（不変条件）→ 各シナリオへの横断アサーション / **Verification Method**: manual-check（+ evals/ 横断アサーション）
- **導出テストケース**:
  - `ENVCON003-A1_全evalsシナリオで書き出し先パスがプロジェクトルート配下`（B節の各シナリオに横断適用）
  - コードレビュー（PR）でプロジェクト外書き込みが無いことを確認
- **検証ステータス**: green（2026-07-12、evals/ 全スキルの sandbox 限定書き込みアサーション）

---

## C. manual-check（人間の実施記録が green 条件）

### テスト仕様: ENV-CON-001 deny セットは普遍的最小集合に限定

- **導出元種別**: Event-Driven（変更時レビュー）+ Optional Feature / **Verification Method**: manual-check
- **チェック手順**: DENY_PATTERNS 変更を含む PR で、追加パターンが普遍的破壊的操作で
  あることをレビュー確認。pass ケース（誤検知なし）テストの維持を CI で担保。
- **証跡**: pass ケース 12件 green（tests/test_env_guard.py）。パターンは v0.1.0 の5種から不変。
- **検証ステータス**: 記録待ち（人間のレビュー記録）

### テスト仕様: ENV-CON-002 アダプタ契約の後方互換拡張

- **導出元種別**: Event-Driven + Unwanted Behavior / **Verification Method**: manual-check
- **チェック手順**: collab-contract.md 変更時、既存準拠アダプタが非準拠にならないことを
  確認。破壊的変更時は契約バージョン更新と移行方針の明記を確認（Design Gate 対象）。
- **証跡**: v1→v2 改訂（ENV-TSK-006）で互換節に v1 固定名アダプタの移行パス
  （役割=実スキル名の自明ルーティング）を明記済み。
- **検証ステータス**: 記録待ち（人間による v2 互換性の確認記録）

### テスト仕様: ENV-CON-004 ガードの位置づけ（誤操作抑止・二重化前提）

- **導出元種別**: Optional Feature（WHERE 節）+ Event-Driven / **Verification Method**: manual-check
- **チェック手順**: README / ENV-DSN-001 / env-doctor SKILL.md に「誤操作抑止であり
  セキュリティ境界ではない」旨の明示があることを目視確認。env-doctor に permissions 層
  不在の WARN 診断項目があることを確認。
- **証跡**: ENV-TSK-011 実施記録（WARN 診断項目追加・位置づけ追記、司令塔検収済み）。
- **検証ステータス**: 記録待ち（人間の目視確認記録）

### テスト仕様: ENV-NFR-002 rules 注入サイズの節度

- **導出元種別**: Optional Feature + Unwanted Behavior / **Verification Method**: manual-check
- **チェック手順**: rules/*.md の内容がガードレール本文に限定されていることと
  合計サイズの節度を目視確認。
- **証跡**: rules/ は 00-guardrails.md の1ファイルのみ（ENV-TSK-011 で方針明文化済み）。
- **検証ステータス**: 記録待ち（人間の目視確認記録）

---

## 判定サマリ（2026-07-12）

| 要件 | method | ステータス | verified 提案 |
|------|--------|-----------|---------------|
| ENV-FR-001 | example-test | green（28ケース） | **verified 済**（2026-07-11 人間承認） |
| ENV-FR-002 | example-test | green（7ケース） | **verified 済**（2026-07-11 人間承認） |
| ENV-NFR-001 | benchmark | green（3ケース） | **verified 済**（2026-07-11 人間承認） |
| ENV-FR-003〜007 / 009 / 010 | example-test | green（evals/ 25ケース・各 report.md） | **verified 済**（2026-07-12 人間承認） |
| ENV-CON-003 | manual-check + evals 横断 | green（sandbox 限定書き込み全確認） | **verified 済**（2026-07-12 人間承認） |
| ENV-FR-008 | example-test | yellow（自動 green・実環境確認待ち） | 保留 |
| ENV-CON-001 / 002 / 004, ENV-NFR-002 | manual-check | 記録待ち（人間） | 不可 |
