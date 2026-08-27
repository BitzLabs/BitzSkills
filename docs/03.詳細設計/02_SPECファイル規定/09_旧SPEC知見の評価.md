# 旧SPEC知見の評価

## 1. 調査対象

旧実装の`design/flw-tsk-106-safety-boundary`、commit `2cd4ff1`を、作業ツリーへ切り替えず確定refから調査した。
特にM2 Local Safety Profileの要求、設計、TASK、spec-issue、テスト仕様、検証証跡、実装後振り返りと、
bitz-sddの共通Frontmatter・ライフサイクル・検証契約を対象にした。

調査対象の`plugins/bitz-flow/.spec/`には374件のMarkdownがあった。設計18件はH2構成が18種類、
レポート63件は59種類だった。要求34件とTASK 114件は各1種類に揃っていたが、H2ではなく
`- **説明**:`、`- **完了条件**:`などの太字ラベルを疑似セクションとして使っていた。

## 2. 採用する知見

| 旧版の知見 | Core 1.0での採用方法 | 理由 |
|---|---|---|
| TASKの変更境界 | 任意の`changes`と明示TASK検査 | AIの意図しない横断変更を低コストで検出できる |
| 検証証跡のrevision・dirty状態 | `--report`結果へ記録 | 古い結果を現在の成功と誤認しにくい |
| 要求変更の影響候補 | 強い型付き関係の逆参照を警告表示 | 自動状態遷移なしで見直し漏れを減らせる |
| 実入口からの垂直検証 | `Verification`標準節で明記 | helper単体の成功を機能完成と誤認しない |
| raw log・秘密情報を証跡へ保存しない | レポート契約として維持 | 漏えいと巨大diffを避ける |
| 未対応・判定不能を成功へ畳み込まない | 共通結果の`blocked`・`error`を維持 | fail-openを防ぐ |

## 3. 簡素化して採用する知見

| 旧版の機能 | 簡素化 |
|---|---|
| `boundary`の巨大なカンマ区切り一覧 | YAML配列`changes`とディレクトリ接頭辞にする |
| `.spec/verification/`の恒常的証跡 | 成功時は明示`--report`時だけ保存する |
| `derived_from`、`implements`、`depends_on`等の無規律なグラフ | 5つの型付き関係と句単位テスト対応へ限定する |
| featureごとの`test-spec.md` | REQ/TECHの`Verification`節へ統合する |
| stale伝播と状態更新 | 逆参照から影響候補を警告し、人間が`outdated`を選ぶ |

## 4. 採用しない機能

| 機能 | 不採用理由 |
|---|---|
| `verified -> promoted`とGatePassage | 個人・小規模チームには承認状態機械が重い |
| `.spec/STATE.md`、ROADMAP、永続run台帳 | Git、Issue、CLI結果と責務が重複する |
| レビューごとの複数JSON・統合レポート | ファイル数と待ち時間が急増する |
| 専用`spec-issues/`ライフサイクル | 通常のIssueまたはTASK/ADRで足りる |
| 成果物ごとのversion、updated | Git履歴と重複し、同期ずれを生むため不採用 |
| 最終H2の`Revision History` | 主要な改訂意図だけを3列で要約。正確な差分・変更者・時刻はGitを正とする |
| 全変更の自動DAG伝播 | 候補抽出以上の意味判定は人間なしでは不正確 |
| platform・署名・lease等の安全機構をSPEC共通機能化 | 個別runtimeの責務でありSPEC形式を肥大化させる |

## 5. 実装後振り返りからの境界

旧ブランチの実装後振り返りで最も重要な教訓は、部品の存在を利用者が通る垂直フローの完成と
同一視しないことである。SPEC Coreは構文、参照、パス、コマンド終了結果を検査できるが、テストが本当に
production入口を通ったか、全異常境界を覆ったかを自動証明しない。

そのため、REQ/TECHの`Verification`節には必要に応じて次を記録する。

- 利用者または外部システムが入るproduction入口
- 正常系だけでなく重要な拒否・失敗境界
- タイムアウトなど有限時間で終了すべき条件
- platform固有実装を実走したか、未証明か
- 廃止契約が到達不能であることの確認方法
- 成功、失敗、判定不能を区別する観測結果

これらはすべての小機能へ強制しない。該当しない項目を埋める帳票にはせず、リスクが存在する場合だけ
H3、表、または短い箇条書きで具体化する。

## 6. 充足性の判定

変更境界、型付き依存の完全閉包、Context Digest、句単位カバレッジ、revision付き検証結果、
垂直検証の記述欄、統一本文構成を加えた現在の規定は、
個人から数人のチームを対象とするCore 1.0のSPEC機能として十分である。旧版のGate、恒常的な証跡、
多段状態、専用issue管理を戻す必要はない。

ただし、これは文書設計の充足判定であり、実装完了を意味しない。実装時には少なくとも次を作成する。

- `bitz.yaml`、Frontmatter、結果JSONの機械可読Schema
- REQ、TECH、ADR、TASKの正規テンプレート
- 各Diagnosticに対する最小の正例・反例fixture
- H1/H2構成、EARS-AI配置、太字疑似セクションを検査する適合性テスト
- TASK変更境界、Git revision、dirty状態、影響候補の統合テスト
- 型付き依存の閉包、循環、状態、上限、Context Digestの適合性テスト
- 各`MUST`句のTASK・テスト対応を1件ずつ欠落させるmutation fixture
- production入口を通る小さなEARS-AI垂直スライス

安全性が高い永続処理、複数process競合、platform固有機能については、SPEC Coreを拡張するのではなく、
個別TECHの`Contract`、`Constraints`、`Verification`で必要な状態表、crash-point、時間上限を定義する。
