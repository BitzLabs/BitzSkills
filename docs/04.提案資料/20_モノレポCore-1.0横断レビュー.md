# モノレポCore 1.0横断レビュー

- 状態: Review Complete / P0 Closed / P1 Adjudication Pending
- 実施日: 2026-09-02
- 基準: branch `bitz_next`、HEAD `0097f2839e15a697cea5a8e4cb413a77562201ab`＋未コミット設計
- 規範文書digest: `b292eed96f8d607c49e380bdb500c10a0c896c2e2c41bea415c4fd14aa38aaba`
- 入力: 独立レビュー13〜19

## 1. 総合判定

モノレポSPEC連合をCore 1.0へ含める設計方針は**条件付き採用を維持**できる。明示catalog、修飾ID、設定非継承、
到達workspace限定Context、`(workspaceId, commandName)` binding、Git境界のfail-closedは相互に整合し、
Core 1.0として実装可能な大きさに収まっている。

レビュー時点では、複数targetのverifyに対し結果が単一`contextDigest`しか持たず、verified述語が成立しない
P0を1件検出した。P0は2026-09-02にADR-041で裁定・反映済みである。互換条件、所有pathのcanonical判定、
公開Schema、CLI境界、移行、性能受入条件のP1は引き続き残る。

独立レビュー29件は原因単位で7つの横断課題へ統合できる。FED-CROSS-001はClosed、残るP1を正本へ反映し、
P2をfixtureまたは非目標として裁定した時点で、設計レビューゲートを再開できる。

## 2. 独立レビュー結果

| 文書 | 観点 | P0 | P1 | P2 | 判定 |
|---|---|---:|---:|---:|---|
| [13](13_モノレポ連合モデル・不変条件レビュー.md) | 連合モデル・不変条件 | 0 | 1 | 1 | 保証範囲とidentityを補完 |
| [14](14_ID・横断関係・Contextレビュー.md) | ID・横断関係・Context | 0 | 2 | 1 | Context公開契約を補完 |
| [15](15_CLI・対象選択・結果集約レビュー.md) | CLI・対象選択・集約 | 0 | 3 | 2 | invocationと結果境界を補完 |
| [16](16_verify実行モデルレビュー.md) | verify実行モデル | 1 | 3 | 1 | 結果Schema修正まで着手不可 |
| [17](17_セキュリティ・信頼境界レビュー.md) | セキュリティ・信頼境界 | 0 | 3 | 1 | canonical所有検査を補完 |
| [18](18_互換性・移行・運用レビュー.md) | 互換性・移行・運用 | 0 | 3 | 2 | release前提と移行を補完 |
| [19](19_実装可能性・性能・文書構造レビュー.md) | 実装可能性・性能・文書構造 | 0 | 3 | 2 | Schemaと受入fixtureを補完 |
| **合計** |  | **1** | **18** | **10** | **29件** |

優先度は次の意味で使用した。

- P0: 現在の契約では安全性または中心述語が成立せず、実装着手前に必須
- P1: 実装者が複数の互換でない動作を選べるため、公開契約を固定してから実装
- P2: 実装と運用の品質を左右するため、1.0受入試験までに裁定

## 3. 横断課題

| ID | 優先度 | 統合した独立指摘 | 裁定案 | 主な反映先 |
|---|---|---|---|---|
| FED-CROSS-001 | P0 | VER-001〜005 | `targetResults[]`をverified証跡の正本にする | verify仕様、共通結果 |
| FED-CROSS-002 | P1 | MIG-001〜002 | 初回公開前提を確認し、違う場合は旧Coreが拒否するversion gateを採る | ADR-040、設定Schema、互換性 |
| FED-CROSS-003 | P1 | INV-001、SEC-001〜004 | Git管理SPECのcatalog差分とcanonical所有領域を検査する | 連合仕様、安全なI/O、doctor/check |
| FED-CROSS-004 | P1 | CTX-001〜003、CLI-003、IMP-003 | Context・連合結果・bindingの完全Schemaを所有文書へ置く | Context、共通結果、verify |
| FED-CROSS-005 | P1 | CLI-001〜002、CLI-004〜005 | `--all-workspaces`の起点、未知workspace、継続、revisionを固定する | CLI共通、各操作仕様 |
| FED-CROSS-006 | P1 | INV-002、MIG-003〜005 | workspace IDを永続identityとし、原子的移行手順を定める | 連合仕様、運用手順、実装計画 |
| FED-CROSS-007 | P1 | IMP-001〜002、IMP-004〜005 | resource数値、測定条件、期待JSON fixtureを固定する | 実装計画、resource契約 |

FED-CROSS-001は[ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)で
裁定・反映済みである。結果保存も同時に明示`--report`だけへ変更し、CIとworktreeの暗黙file生成を禁止した。

## 4. FED-CROSS-001 verify証跡モデル

### 4.1 問題

verifyはtargetごとにContextを解決し、異なるtargetは異なる依存閉包とDigestを持てる。一方、結果はtop-levelに
`contextDigest`を1つだけ持つ。複数target、引数なしverify、`--all-workspaces`では基数が一致しない。

### 4.2 推奨裁定

`targetResults[]`をverified証跡の正本とする。各要素は少なくとも次を持つ。

| field | 必須 | 内容 |
|---|---|---|
| `target` | yes | 連合正規target ID |
| `status` | yes | target単位status |
| `contextDigest` | yes | 解決成功時のDigest、Contextを作れない場合は`null` |
| `statements[]` | yes | 検証対象となった連合正規statement ID |
| `bindingRefs[]` | yes | 実行計画のbinding ID、重複なし辞書順 |
| `diagnostics[]` | yes | target固有原因 |

`commands[]`は実行実体をbindingごとに1件だけ保持し、`bindingId`、owner workspace、command名、status、exitCode、
timeout、stdout／stderr、`covers[]`を持つ。top-levelの単一`contextDigest`は削除する。blocked targetからだけ
得たbindingは実行せず、別の通過targetも同じbindingを要求するときだけ1回実行する。

### 4.3 受入条件

- 異なる2つのContextを持つtargetのDigestを両方保持できる
- 1つの共有bindingを1回だけ実行し、両targetから参照できる
- Context blocked targetのstatusをcommand結果で上書きしない
- command実体数、failed target数、非成功workspace数を別々に集計する

## 5. FED-CROSS-002 互換性gate

### 5.1 問題

旧Coreが同じ`schemaVersion: "1.0"`の未知`workspace`／`monorepo`をwarningで無視できる場合、連合rootを単一workspaceと
誤認する。新Coreの`monorepo.v1` Capabilityは、この旧Coreの実行を防止しない。

### 5.2 推奨裁定

まず「モノレポ非対応のCore 1.0を外部配布済みか」をrelease事実として確認する。

- 未配布なら、ADR-040を初回1.0公開前の互換性境界変更として記録し、1.0 Schemaへ含める
- 配布済みなら、旧Coreが必ず拒否するSchema majorまたは必須feature markerを採用し、最低Core版をCIで固定する

単一workspaceの旧固定ID `root`から明示root IDへの写像も同時に決める。暗黙renameを許さず、連合化時にContext Digestと
report identityが変わることを移行手順へ明記する。

## 6. FED-CROSS-003 所有境界の完全性

### 6.1 問題

「catalog外`.spec/`を暗黙追加しない」は妥当だが、「連合内のworkspaceを完全検査した」という保証とは別である。
また、root所有pathがmember内へ解決されるsymlinkを字句判定だけで拒否できない。

### 6.2 推奨裁定

- `doctor --all-workspaces`と全体checkは、Git indexおよび選択base/current treeの`**/.spec/bitz.yaml`を軽量列挙し、
  catalogとの差分を`SPEC-MONOREPO-UNREGISTERED-001`にする
- 未追跡filesystem全体は再帰探索せず、明示選択された未登録`.spec/`だけを現行どおりblockedにする
- 全所有pathを同一canonicalizerへ通し、repository、active workspace、別workspace、`.spec/`境界を順に検査する
- member path、所有path、TASK prefix、command cwdで同じ実path包含規則を使う
- 原子的snapshotとTOCTOU完全防止は非目標のまま維持する

## 7. FED-CROSS-004 公開Schemaの閉鎖

Context追加field、Digest材料、`workspaces[]`、verify bindingにfield表とcanonical JSONが不足する。
規範所有者を増やさず、次へ分配する。

| 契約 | 正本 |
|---|---|
| `resolution.workspaces[]`、`crossWorkspaceEdges[]`、Digest材料 | Context仕様 |
| `federation`、`workspaces[]`、status・件数・Diagnostic配置 | 共通結果契約 |
| `targetResults[]`、`bindingRefs[]`、`commands[]` | verify仕様 |
| 修飾IDと所有境界 | モノレポ連合仕様 |

Digestへ含める実効設定はallowlistで固定し、表示だけに影響する設定を除外する。解決不能、型不正、参照先不在の
Diagnostic優先順位も通常の構文・型検査から横断解決の順へ固定する。

## 8. FED-CROSS-005 CLIと集約

次の解釈へ固定するのが最小である。

- 「federation rootで`--all-workspaces`」はcwd一致ではなく、cwd／入力pathから同じGit rootと連合rootを発見できること
- `--all-workspaces`はpath／ID対象および`--workspace`と排他的
- 構文上妥当だが未知の`--workspace`は処理開始前のinvocation error、終了コード4、report非生成
- workspace途中失敗後は、依存edgeまたは共有bindingを必要としない後続workspaceだけを継続
- all-checkの`revision`はtop-levelに1件置き、全workspaceが同じbase/current Git treeを共有する
- `workspaces[]`の共通fieldを固定し、操作固有詳細は名前付きsubobjectへ置く

これは未知workspaceを現在の`failed`とする規則を変更するため、共通の「引数不正は終了コード4」という既存原則との
優先関係を裁定して正本へ反映する必要がある。

## 9. FED-CROSS-006 identityと移行

workspace IDを連合内の永続identityとし、Core 1.0ではrenameを非対応とする。member path移動は同じIDとしてbase/current
catalogを対応付ける。member削除は、そのworkspaceの管理済みSPECが消える操作として既存の削除規則を適用する。

移行は不完全catalogを許容せず、root catalog、全member設定、横断参照を同じ変更集合へ追加する。CIの最低Core版、
`doctor --all-workspaces`、`check --all-workspaces`、report consumerを同じreleaseで切り替える。rollbackも設定だけでなく
横断参照とconsumerを同時に戻す。

## 10. FED-CROSS-007 resource・性能・適合試験

SPEC 10,000件以外に入力byte、document、statement、edge、bindingの総数を固定し、limit診断に超過dimensionを持たせる。
標準fixtureは環境、cold／warm、試行回数、統計値、file size、edge密度、到達workspace数を記録する。

適合fixtureには最低限、同一ローカルID、横断参照、未登録SPEC、symlink所有迂回、member移動・削除、multi-context verify、
共有binding、blocked／成功混在、0件、Git不在、resource境界を含める。status、exit code、Diagnostic順、期待JSON、
report生成有無を機械比較する。

## 11. 裁定・反映順序

| 順序 | 課題 | Gate |
|---:|---|---|
| 1 | FED-CROSS-001 verify証跡 | **Closed**。ADR-041と正本へ反映済み |
| 2 | FED-CROSS-002 互換性 | 公開済み版の事実確認後にversion方針を決定 |
| 3 | FED-CROSS-003 所有境界 | path resolver／doctor実装前に固定 |
| 4 | FED-CROSS-004 公開Schema | adapterとfixture作成前に固定 |
| 5 | FED-CROSS-005 CLI集約 | CLI parserとreport実装前に固定 |
| 6 | FED-CROSS-006 identity・移行 | 実repository移行前に固定 |
| 7 | FED-CROSS-007 性能・fixture | 1.0受入試験開始前に固定 |

1、3、4、5は既存方針を変えず詳細契約を閉じるため、原則として詳細設計の改訂で足りる。2は公開履歴によって
Schema互換性の決定が変わり、6はworkspace identityを新たに固定するため、ADR-040の追補または新規ADRで裁定する。

## 12. 最終判定

- 方針: **採用維持**
- 設計レビューゲート: **未完了**
- 実装着手: **残るP1裁定まで保留**
- 再レビュー: 正本反映後、上記受入fixtureに対する契約追跡だけを行う

モノレポをCore 1.0から再び除外する必要はない。verify結果とI/OのP0接続は完了した。現時点の課題はscope過大ではなく、
残る互換、所有、公開Schema、CLI、移行、resource契約を最後まで接続できていないことである。
