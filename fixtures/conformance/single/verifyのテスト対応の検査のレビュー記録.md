# `verify`が使うテスト対応の検査のfixtureのレビュー記録

[適合fixture仕様 §6.18](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#618-verifyが使うテスト対応のテストのパスとcoversの検査)の
`SINGLE-175-01`〜`SINGLE-175-08`と、[§7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-062-01`〜`MULTI-062-07`（置き場は`fixtures/conformance/multi/`）を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/verify_test_check_fixtures.py`である。

## 追加の理由

実装の確認事項N2・C92と、PR-cの独立レビューのM1に対応する。

- N2・C92: `verify`は、検証対象が使うテスト対応のテストのパスの存在と所有境界も、`covers`の妥当性も検査していなかった。単一ワークスペースでは、存在しないパスやディレクトリのテストを起動して`passed`にし、
  不正な`covers`（推移的な`refines`など）を数えて`passed`にした。複合ワークスペースの`verify`は、所有領域の外のパスも判定せずに起動した（`check`は同じ入力を`failed`にする）。
- ユーザーの決定により、規範を明記した（コミット`d4f11daa`。診断レジストリへの`VERIFY-TEST-PATH-INVALID`・`VERIFY-TEST-COVERAGE-INVALID`の追加と、`MULTI-OWNERSHIP`への`verify`の追加を含む。
  診断の網羅表への反映は`2a766add`）。Coreは、コミット`19e28f32`で直した。単体試験は`tests/bitz-core/test_verify_test_checks.py`が押さえる。
- 既存のfixtureが押さえていたのは、`check`の`implements`と`tests[].path`の検査（`SINGLE-024`、`MULTI-008`、`SINGLE-174`、`MULTI-061`）、`verify`の実効`cwd`の包含（`SINGLE-167`、`SINGLE-174-07`〜`10`）、
  `check`の`covers`の検査（`SINGLE-026`、`MULTI-046`）だけである。`verify`が使うテスト対応のパスと`covers`を検査すること自体は、押さえていなかった。

## 根拠の規範文

- `verify` §4の4.と、その後の段落、§9: 検査の対象は、検証対象が使うテスト対応だけである。テストのパスの存在と所有境界は`check`と同じ規則、`covers`の妥当性はテスト対応の規則で判定し、
  違反は`check`と同じ診断を検証対象の`diagnostics`へ返す。その検証対象は`failed`、`bindingRefs: []`、テストを起動せず、独立した検証対象は続ける（`skip-target`）。
  検証対象が使わないテスト対応と`implements`は検査しない。
- 関係・トレースモデル §9、ワークスペース・設定仕様 §9、複合ワークスペース仕様 §5.1: テストのパスの存在（通常のファイル）と所有境界（実パスがワークスペースの所有領域の中）。
- 文書・フロントマター・状態仕様のテスト対応の規則: `covers`は、(a)自身の規範文、(b)規範文を持たない文書は自身のID、(c)直接`refines`する文書の規範文、または直接`refines`する規範文。
  複合ワークスペースの横断の`covers`は、宣言する文書が直接`refines`する場合だけ。
- 診断レジストリ: `VERIFY-TEST-PATH-INVALID`（`SPEC-PATH-INVALID-001`）、`VERIFY-TEST-COVERAGE-INVALID`（`SPEC-TEST-COVERAGE-001`）、`MULTI-OWNERSHIP`（`SPEC-MULTI-OWNERSHIP-001`、`verify`を含む）。いずれも`error`／`failed`、`file`、`skip-target`。
- `verify` §8: `contextDigest`が`null`になるのは、コンテキストを構成できない場合だけ。

## 入力と起動

| fixture | 入力 | 結果 | 修正前のCore |
|---|---|---|---|
| `SINGLE-175-01` | TECH-001の`tests[2].path`が存在しない`tests/nope.py`（`AC-01`を`covers`。`tests[0]`・`[1]`は正しい）。`verify REQ-001` | `failed`／1。`SPEC-PATH-INVALID-001`、キー`tests[2].path`。`commands`は空 | `passed`／0 |
| `SINGLE-175-02` | `tests[2].path`がディレクトリ`tests/suite` | 同上 | `passed`／0 |
| `SINGLE-175-03` | `tests[2].path`が`ext/env`。`ext -> /usr/bin`（リポジトリの外） | 同上 | `blocked`／2（実効`cwd`の包含で遮断） |
| `SINGLE-175-04` | TECH-002が`TECH-001`だけを`refines`し、`REQ-001:AC-02`を`covers`する（推移的） | `failed`／1。`SPEC-TEST-COVERAGE-001`（TECH-002、キー`tests[0].covers`、証拠`REQ-001:AC-02`） | `passed`／0 |
| `SINGLE-175-05` | 規範文のないTECH-001の文書単位の`tests[2].path`が存在しない。`verify TECH-001` | `failed`／1。`SPEC-PATH-INVALID-001`、`statements`は空 | `passed`／0 |
| `SINGLE-175-06` | `SINGLE-175-01`の入力に、独立したREQ-002とTECH-003を足す。`verify REQ-001 REQ-002` | `failed`／1。`REQ-001`は`failed`、`REQ-002`は`passed`で起動する。`REQ-001`の正しいテストは起動しない | `passed`／0（`tests/nope.py`を含む4件を起動） |
| `SINGLE-175-07` | `SINGLE-175-06`と同じ入力。`verify REQ-002`（対照） | `passed`／0 | `passed`／0 |
| `SINGLE-175-08` | TECH-001の`implements`が存在しない`src/gone.py`（対照） | `passed`／0 | `passed`／0 |
| `MULTI-062-01` | `web`のREQ-101の`tests[1].path`が`ext/test_x.py`。`apps/web/ext -> ../../tests`。`verify web::REQ-101` | `failed`／1。`SPEC-MULTI-OWNERSHIP-001`（`web`、キー`tests[1].path`） | `blocked`／2（実効`cwd`の包含で遮断） |
| `MULTI-062-02` | `tests[1].path`が存在しない | `failed`／1。`SPEC-PATH-INVALID-001`（`web`） | `passed`／0 |
| `MULTI-062-03` | ルートのREQ-001の`tests[1].path`が`apps/web/t.py`。`verify REQ-001` | `failed`／1。`SPEC-MULTI-OWNERSHIP-001`（`platform`） | `passed`／0 |
| `MULTI-062-04` | `web::TECH-010`が`web::TECH-005`だけを`refines`し、`platform::REQ-001:AC-01`を`covers`する。`verify REQ-001` | `failed`／1。`SPEC-TEST-COVERAGE-001`（`web`、証拠`platform::REQ-001:AC-01`） | `passed`／0 |
| `MULTI-062-05` | `web::TECH-010`が`platform::REQ-001:AC-01`を直接`refines`する（対照） | `passed`／0。`platform::default`と`web::default`を起動 | `passed`／0 |
| `MULTI-062-06` | `web`のREQ-101は`tests[1].path`が不在、`api`のREQ-201は正しい。`verify --all-workspaces` | `failed`／1。`web::REQ-101`は`failed`、`api::REQ-201`は`passed`で起動 | `passed_with_warnings`／0 |
| `MULTI-062-07` | `MULTI-062-05`の入力に、使わない`web`のREQ-102（不在のパス）を足す（対照） | `passed`／0 | `passed`／0 |

- 単一のケースは`SINGLE-042`のcorpus（コマンド`default`、REQ-001の`MUST`と`SHOULD`の規範文、規範文のないTECH-001）を基に、`SINGLE-174-07`〜`10`と同じくインデックスへステージして`verify`を実行する。
  複合のケースは、ルート`platform`、メンバー`web`、`api`（`MULTI-008`、`MULTI-039`と同じ構成）を基準版のコミットへ入れる。
- **1つの原因だけを持つ**。違反するエントリは、ほかの正しいエントリと同じ規範文を`covers`する。違反したエントリをカバレッジに数えるかどうかを規範が定めていない（下）ので、結果がその解釈に依存しないようにした
  （正しいエントリが全規範文を数える）。`SINGLE-175-04`は、TECH-001の正しいテスト2件が全規範文を`covers`し、TECH-002は同じ規範文の`AC-02`だけを重ねて`covers`する。
- リポジトリの外のディレクトリは、fixtureがサンドボックスの外へ書けないので、ホストの`/usr/bin`を指す絶対パスのシンボリックリンクで置く（`SINGLE-175-03`だけ。`SINGLE-174-01`と同じ前提で、
  `/usr/bin/env`がファイルへ解決することを監査が確かめる）。ホストに依存しない所有境界の違反は、複合ワークスペース（`MULTI-062-01`・`03`）が押さえる。
- `SINGLE-175-06`の`REQ-001`の正しいテスト（`tests/test_auth.py`、`tests/test_session.py`）も起動しない。`skip-target`は検証対象を丸ごと実行計画へ入れない（`verify` §4の4.）。
  `MULTI-062-06`も同じで、`web`は`commands`を持たない。

## 診断の文言

承認済みの文言だけを使い、新しい文言はない。

| 対象 | 文言 | 出典 |
|---|---|---|
| `tests[].path`の不在・外へ解決 | テストのパスが存在しません | 承認済み（出力文言のレビュー記録の#121。`SINGLE-174-01`が使う） |
| 所有境界の違反 | パス{path}の解決先がワークスペース{workspace_id}の所有領域の外です | 承認済み（同#105。`MULTI-008`、`MULTI-061`が使う） |
| `covers`の参照先が不正 | フィールドcoversの参照先が存在しないか、対応できません | 承認済み（C67の節。`SINGLE-026`、`MULTI-046`が使う） |

## 期待値の導き方（Coreの出力を根拠にしない）

1. **使うテスト対応と違反の参照計算**。`reference_target`が、入力の木構造から、閉包（`multi_binding_missing_fixtures.verify_closure`。具体化文書を推移的に含む）、対象規範文、使うテスト対応
   （対象規範文を`covers`するエントリ。規範文のないTECHは起点の`tests`すべて）を導く。テストのパスは`os.path.realpath`で求めた実パスの文字列のセグメントの包含で、`covers`は(a)〜(c)（`allowed_covers`）で判定し、
   診断の`code`・`summary`・`source`・`evidence`を組み立てる。Coreの`os.path.samestat`や`relations.check_paths`・`multirelate.coverage_diagnostics`は使わない。期待結果の診断と一致することを要求する。
2. **起動するテストの参照計算**。通過した検証対象が使う、正しいテスト対応のパスだけを、ワークスペースごとに集め、期待結果の`commands[].tests`と一致することを要求する（違反した検証対象のテストは含まない）。
3. **欠陥を検出できる入力であること**。違反のあるケースだけが`defective`であることを、参照計算の違反の有無から要求する（`defective`は、修正前のCoreが違反を見ずに通すこと）。
4. **ハッシュ値**。`contextDigest`は、リテラルの参照計算A（単一は`SINGLE-042`のレビュー済みの材料に、`implements`、`tests`、TECH-002、REQ-002・TECH-003を足す。複合は文書のリテラルの記述から、
   到達したワークスペースの設定と使うコマンドだけを収録する）と、入力の木構造から導く参照計算B（単一は`digest_crosscheck.build`、複合は`multi_binding_missing_fixtures.derived_material`）の両方で照合する。
5. **入力の構成**。追跡するエントリは通常のファイル（`100644`）とシンボリックリンク（`120000`）だけで、`reviewed_inputs`・`reviewed_links`と一致する。
6. **副作用なし**。リポジトリ、`git status`、`HOME`、キャッシュ、`TMPDIR`の読取り専用の実行前後を固定し、準備手順を2回適用して固定したスナップショットと照合する。

## 規範から決まらず、既存の形と仕様の該当箇所で決めた点

1. **違反した検証対象の`contextDigest`と`statements`**。コンテキストは完成するので、値を持つとした（`verify` §8は、`contextDigest`が`null`になるのをコンテキストを構成できない場合だけとする。
   `CTX-COVERAGE-TEST-001`、`VERIFY-BINDING-MISSING`の検証対象と同じ）。
2. **違反したテスト対応をカバレッジに数えるか**。作業の時点では規範から決まらなかったが、`verify` §4に「3.のカバレッジは宣言どおりのテスト対応で判定し、
   4.で違反が見つかった検証対象は`failed`」と明記した（2026-11-08、司令塔の判断。違反したエントリだけが唯一のカバーでも、`CTX-COVERAGE-TEST-001`ではなく本当の原因の診断で`failed`になる）。
   fixtureは、違反したエントリのほかに正しいエントリが全規範文を`covers`する入力にしてあり、この判断に依存しない。
3. **違反と、ほかのテスト割当ての欠落**。`verify` §4に明記した。違反したテスト対応はテスト割当ての解決から外すので、同じテスト対応のコマンドの定義の不足は判定しない。
   別のテスト対応でコマンドの定義の不足（`VERIFY-BINDING-MISSING`、`blocked`）が重なれば両方の診断を返し、`failed`が`blocked`より重いので検証対象は`failed`にする。fixtureは、この重なりを持たない（単体試験が押さえる）。
4. **`key`の形**。`SPEC-PATH-INVALID-001`と`SPEC-MULTI-OWNERSHIP-001`は`tests[i].path`、`SPEC-TEST-COVERAGE-001`は`tests[i].covers`（`check`と同じ。`SINGLE-026`、`MULTI-008`）にした。
   発生元は、テスト対応を宣言した仕様文書（`verify` §4の4.）。複合ワークスペースの`workspaceId`は、その文書を所有するワークスペース。
5. **`workspace`、`scope`、`revision`**。`verify`の最上位の形は既存のfixture（`SINGLE-174-07`〜`10`、`MULTI-039`）に合わせた。単一はインデックスにステージだけでコミットがないので`revision`は`null`、複合は基準版のコミットを置く。
6. **Stepの割当て**。同じ操作・同じ診断の既存のfixtureに合わせた。単一の`verify`は`SINGLE-174-07`〜`10`と同じStep 4、複合は`MULTI-039`と同じStep 5。実装計画の完了条件の2箇所に足した。
7. **規範が列挙するが、fixtureで押さえなかったもの**。テスト対応の`covers`が文書IDを指す(b)の違反は、`check`の`SINGLE-026`が押さえるので、ここでは足していない。
   複合ワークスペースで、テストを宣言する文書が検証対象と別のワークスペースにある場合の所有境界は、`MULTI-062-04`・`05`の`web`の文書（パスは正しい）が通る側だけを押さえた。

## 検証の記録

- 修正後のCore（このブランチ）では、15件すべてが`passed`となる。期待値は規範から導いたもので、Coreに合わせて曲げていない。食い違いはなかった。
- 修正前のCore（`origin/main`の`plugins/bitz-core`）では、欠陥の11件（`SINGLE-175-01`〜`06`、`MULTI-062-01`〜`04`、`06`）が失敗し、対照の4件（`SINGLE-175-07`・`08`、`MULTI-062-05`・`07`）は通る。
  失敗の内訳は上の表のとおり（状態と終了コード、`commands`の件数、診断の有無）。

## 既存のfixtureの期待値の訂正

`MULTI-039-03`と`04`の入力を訂正した。理由と内容は[複合ワークスペースのテスト割当ての欠落のレビュー記録](../multi/複合ワークスペースのテスト割当ての欠落のレビュー記録.md)の2026-11-08の節に記録した。
ほかの適合fixtureは、修正後のCoreですべて通過し、期待値は変わらない。
