# 初回実fixture: 導入と設定

2026-09-08。対象は `SINGLE-001`、`002`、`003`、`004-01`、`004-02`、`005-01`、`005-02`、`006-01`、`006-02`。
この9件は入力・唯一の期待JSON・副作用期待値を持つ。Coreの実行結果ではない。

## 設計と単一原因レビュー

| ID | 独立原因 | 実行 | status / exit |
|---|---|---|---|
| SINGLE-001 | なし。最小設定だけ | doctor --format json | passed / 0 |
| SINGLE-002 | 設定不在だけ | doctor --format json | blocked / 2 |
| SINGLE-003 | schemaVersionをstringの2.0に変更 | check --full --base HEAD --format json | blocked / 2 |
| SINGLE-004-01 | languageをintegerの42に変更 | check --full --base HEAD --format json | error / 3 |
| SINGLE-004-02 | 必須earsAiだけを削除 | check --full --base HEAD --format json | error / 3 |
| SINGLE-005-01 | 未知key futureOptionだけを追加 | check --full --base HEAD --format json | passed_with_warnings / 0 |
| SINGLE-005-02 | 予約key profilesだけを追加 | check --full --base HEAD --format json | passed_with_warnings / 0 |
| SINGLE-006-01 | command実行fileだけが不在 | doctor --format json | blocked / 2 |
| SINGLE-006-02 | command cwdだけが不在 | doctor --format json | blocked / 2 |

最小設定はdoctor仕様の `schemaVersion: "1.0"`、`language: ja`、`earsAi: "1.0"`。
code、test、SPEC文書、monorepo宣言は置かず、別原因のDiagnosticを混ぜない。
command bindingは006系だけにdefaultを1件置く。
checkは入力を固定metadataでcommitして明示HEADを比較基準にする。Git不在・unbornの縮退を混ぜない。
doctorはGit利用可能なunborn repositoryで実行し、履歴差分の検査は要求しない。
SINGLE-002の空repoをGitで保持するためだけに `.gitkeep` を置き、setupで除去してから実行する。
すべてのcopyは物理的に独立し、共通入力へのlinkは使わない。

根拠は[適合fixture仕様 §6.1](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#61-導入と設定)、
[設定仕様 §5](../../../docs/03.詳細設計/02_SPECモデル/01_workspace・設定仕様.md#5-schema)、
[doctor仕様](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md)、
[結果契約 §2・§5](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)。

## 今回固定する完全期待値

従来の仕様が語彙・意味だけを規定していた部分も、今回のfixtureは次の一意な値で固定する。
比較時にsummary、suggestedAction、checks、任意fieldを除外する規則は追加しない。

- SINGLE-001のchecksは処理順に `core, workspace, config, schema, ears, git, command, impact`。
  `impact` はinfo、他はpassed。plugin要求がなく、単一workspaceなのでplugin・Capability要求・catalogの項目は置かない。
  command定義0件はcommand check成功、影響候補0件はimpact checkのinfoとし、追加Diagnosticは出さない。
- SINGLE-002は `core: passed, workspace: blocked, git: passed`。
  独立なGit確認を続け、設定に依存する後続checkは出力しない。連合の依存遮断Diagnosticは単一workspaceへ追加しない。
- 未知majorのSINGLE-003は構造的に有効な設定から既定identity `root` を確定後、互換性検査で停止する。
  型不正・必須key欠如・設定不在のケースはidentity確定前なので `workspace.id: null`。
- checkのDiagnosticは `source.key` をそれぞれ `schemaVersion`、`language`、`earsAi` とする。
  line・column、evidence、specRefs、extensions、suggestedActionはこの3件では付加しない。
  summaryは各 `expected/check.json` の日本語文字列を固定値とする。
- 設定不在はenvironment sourceの `component: workspace, identifier: .` とし、
  suggestedActionへ作成先・貼付け可能な最小設定・gitignore追記・次のcheckを含める。
- 005系は `SPEC-CONFIG-UNKNOWN-001` / warning / passed_with_warningsを1件だけ返す。
  `source.key` はそれぞれ `futureOption`、`profiles`。未知keyの値 `preserve-me` と予約keyの値
  `legacy-profile` は保持し、profilesを設定機能として解釈しない。文書0件のfull checkは両checked countを0とする。
- 006系は `SPEC-DOCTOR-COMMAND-001` / error / blockedを1件だけ返す。
  sourceはregistryどおりfileで、`workspaceId: root`、`path: .spec/bitz.yaml`、keyはそれぞれ
  `verify.commands.default.argv`、`verify.commands.default.cwd`。line・column・evidence・修復案は付加しない。
  checksは001と同じ順序でcommandだけblocked。独立なimpact checkは続けてinfoとし、別のDiagnosticは追加しない。
  005・006系ともsummaryは各expected JSONの固定文字列とする。
- durationは0、Core patchは0、Git commit IDは40桁の0を期待JSONの代表値とする。
  実値は既存の共通normalizerだけで比較する。Gitのdirty、Core major/minorやCapability順序は除外しない。

これらは今回追加した受入期待値の選択であり、既存Coreで観測した値ではない。
将来変更する場合は仕様との整合をレビューし、期待値とレビュー記録を同じ変更で更新する。

## 副作用期待値と検証

各fixture直下の `side-effects.json` は `side-effects.schema.json` に従う補助証拠。
manifestの公開fieldは増やさず、期待出力の `expected/` とは分離する。
`before` と `after` にrepositoryの全path・種別・実行bit・SHA-256、Git porcelain v1 statusとstage index、
HOME / XDG_CACHE_HOME / TMPDIRの3隔離treeを固定する。許可書込みは0件で、beforeとafterは完全一致する。
`.git` 内部fileは既存snapshot契約に従って除外し、Git statusとindexは別に比較する。
report directory、永続cache、lock、作業fileの残存を許可しない。明示reportを許すfixtureはこのSchemaの対象外。

`uv run fixtures/validate_step0b.py` の `initial_fixtures` は次を検査する。

1. manifest / result / side-effectsのSchema適合、操作・status・終了コード・単一原因との整合。
2. 各入力を新しい隔離directoryに2回setupし、各回が固定before snapshotと一致すること。
3. 入力byte列がレビュー済みの単一原因と一致し、read-onlyの期待afterがbeforeと一致すること。
4. 回帰試験でstatus、source.key、argv、修復手順、副作用期待値の破損を拒否すること。
5. 005系のwarningをerrorへ変更した場合やDiagnosticの重複、006系の原因keyやcheck statusの破損を拒否すること。

006-01は `argv: ["./missing-command"]`、`cwd: .`。実行fileの明示pathが存在しないことを確認し、
hostのPATHに同名commandがあっても結果が変わらない構成とする。
006-02は `argv: ["/bin/true"]`、`cwd: missing-directory`。このfixture環境はLinux/POSIXで
`/bin/true`が通常の実行可能fileとして利用可能であることを要求し、未導入・実行不可は準備検証のerrorとする。
実効cwdが不在でも実行fileの絶対pathは独立に確認できる。PATHは上書きせず、Git利用を壊さない。
準備検証でcommandを起動することはない。実際のdoctorがcommandを起動しないことはGate Bで別途確認する。

検証はCoreもYAML設定判定も実装しない。afterは期待値だけであり、Core実行後の実測値ではない。
Core実装後のGate Bで、実stdout/終了コード、実before/after、索引構築へ進まないことを確認する。
この9件に加えて[EARS-AI構文・候補抽出・拡張の12件](ears-review.md)と
[文書構造・UTF-8の9件](document-review.md)、[関係・path・coverageの6件](trace-review.md)、[ID重複・循環の4件](graph-review.md)を準備した。
計40/311件、matrix残271件、golden Context Digest、全体の副作用期待値、
fresh checkoutでのGate A全検証は残る。
