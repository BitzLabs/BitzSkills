# ID・横断関係・Contextレビュー

- 状態: Review Complete
- 実施日: 2026-09-02
- 基準: branch `bitz_next`、HEAD `0097f2839e15a697cea5a8e4cb413a77562201ab`＋未コミット設計
- 規範文書digest: `b292eed96f8d607c49e380bdb500c10a0c896c2e2c41bea415c4fd14aa38aaba`
- 観点: 修飾ID、関係型、逆参照、coverage、Context Bundle、Context Digest

## 1. 結論

`workspace-id::local-id`を文書自身のIDへ混入させず、連合解決envelopeとして扱う設計は妥当である。
非修飾参照をsource workspaceだけから解決し、横断参照へ修飾IDを必須にしたことで探索順依存も排除できている。

主な不足は、連合Contextの追加fieldとCanonical Digest入力が実装可能なSchemaまで閉じていないこと、および
横断参照失敗時のDiagnostic所有者が重複し得ることである。

## 2. 指摘一覧

| ID | 優先度 | 指摘 | 影響 |
|---|---|---|---|
| FED-CTX-001 | P1 | 連合Context追加fieldの完全なSchemaがない | adapterと実装で必須field・null・順序が分岐する |
| FED-CTX-002 | P1 | Context Digestへ入れるworkspace実効設定の選択規則が曖昧 | 無関係変更でstaleになる、または必要変更を見逃す |
| FED-CTX-003 | P2 | 横断target不在時のDiagnostic優先順位が未定義 | 同一原因へ2つのerrorを返し得る |

## 3. FED-CTX-001 連合Context Schema

[連合仕様 §6](../03.詳細設計/02_SPECモデル/05_モノレポSPEC連合仕様.md#6-横断索引とcontext)は、
`documents[].workspaceId`、`resolution.workspaces[]`、`resolution.crossWorkspaceEdges[]`を追加している。
しかし、各配列要素の型、必須性、空配列、未知field、単一workspaceでの省略可否を表として確定していない。
[context仕様 §4](../03.詳細設計/03_操作仕様/01_context.md#4-context-bundle)のJSON例も単一workspaceだけである。

少なくとも次を正本Schemaへ追加する必要がある。

- `documents[].workspaceId`: 連合では必須、単一では省略可または実効ID必須のどちらか
- `resolution.workspaces[]`: `{id, path}`、request workspaceを先頭、その後ID順
- `resolution.crossWorkspaceEdges[]`: `{relation, source, target}`、3field必須
- `relation`のenumと、source/targetが文書IDかstatement IDか
- 連合でedgeが0件のとき空配列を返すか省略するか

## 4. FED-CTX-002 Digest入力となる設定

[context仕様 §6](../03.詳細設計/03_操作仕様/01_context.md#6-context-digest)は、command名、argv、cwd、timeout、
Contextに影響する実効設定をDigestへ含める。連合仕様は到達した各workspaceの実効設定を追加するが、
workspaceの`bitz.yaml`全体を含めるのか、閉包が参照するcommandとContext上限だけを含めるのかが明確でない。

全設定を含めると、未使用command変更でも既存Contextがstaleになる。参照分だけにすると、設定選択規則が
必要になる。推奨は、意味解決に使った設定とBundleへ収録したbindingだけをCanonical構造へ明示し、
`monorepo.maxMembers`や未使用commandを除くことである。設定不適合はDigest計算前に操作を停止する。

## 5. FED-CTX-003 Diagnostic所有者

横断参照のworkspaceまたはtargetが不在の場合、連合仕様の`SPEC-MONOREPO-REF-001`と、関係モデルの
`SPEC-RELATION-MISSING-001`またはcontext操作の`CTX-RELATION-MISSING-001`が同じ原因に適用できる。
共通契約は同じ原因の同義Diagnosticを重複させないため、次の優先順位を定める必要がある。

1. workspace qualifier自体が不在・不正: `SPEC-MONOREPO-REF-001`
2. workspaceは存在するがtarget IDが不在: 通常のrelation missing
3. targetは存在するが型不正: `CTX-RELATION-TYPE-001`

## 6. 成立を確認した契約

- EARS-AIの文書ID・statement IDはローカル形式のままである。
- 同一workspace内では非修飾参照を許し、別workspaceへ暗黙探索しない。
- request workspaceは1回のContext requestで1つに限定される。
- reverse refinementにより共通REQからmember側具体化へ到達できる。
- 横断coverageは直接`refines`する文書またはstatementに限定される。
- 未到達workspaceの本文と設定をBundleおよびDigestへ入れない。
- Context上限超過時に部分Bundleを成功扱いしない。

## 7. 判定

IDとgraph規則にP0はない。FED-CTX-001と002を実装前にSchema化する必要がある。
