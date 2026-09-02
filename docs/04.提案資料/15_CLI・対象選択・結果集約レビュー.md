# CLI・対象選択・結果集約レビュー

- 状態: Review Complete
- 実施日: 2026-09-02
- 基準: branch `bitz_next`、HEAD `0097f2839e15a697cea5a8e4cb413a77562201ab`＋未コミット設計
- 規範文書digest: `b292eed96f8d607c49e380bdb500c10a0c896c2e2c41bea415c4fd14aa38aaba`
- 観点: CLI文法、workspace選択、排他、Git基準版、結果・Diagnostic・report

## 1. 結論

単独操作と`--all-workspaces`を別構文にし、明示対象との混在を禁止した点は明快である。共通statusの最悪値集約、
workspace別Diagnostic、federation root reportという基本形も成立している。

一方、「federation rootでだけ許可」の呼出し条件、未知`--workspace`の結果外形、操作別member結果Schemaが
未確定であり、CLI adapterとCoreで結果が分岐する可能性がある。

## 2. 指摘一覧

| ID | 優先度 | 指摘 | 影響 |
|---|---|---|---|
| FED-CLI-001 | P1 | `--all-workspaces`を許可する「federation root」の意味が曖昧 | member配下からの同じ呼出しが実装依存になる |
| FED-CLI-002 | P1 | 未知`--workspace`時の結果workspaceとreport位置が未定義 | 共通結果必須fieldを構成できない |
| FED-CLI-003 | P1 | `workspaces[]`の操作固有fieldが閉じていない | JSON consumerの適合性を判定できない |
| FED-CLI-004 | P2 | 非成功後に継続できる「依存しないworkspace」の判定規則がない | 継続範囲と実行時間が実装依存になる |
| FED-CLI-005 | P2 | 全体checkの`revision`配置が例示されていない | top-levelとmember別の重複が起き得る |

## 3. FED-CLI-001 全体操作の起動位置

[連合仕様 §8](../03.詳細設計/02_SPECモデル/05_モノレポSPEC連合仕様.md#8-全体操作の共通規則)と各操作仕様は、
`--all-workspaces`をfederation rootでだけ許可する。これは次の2通りに読める。

1. current directoryがrepository rootでなければ引数不正
2. member配下から呼んでもcatalogを発見できればfederation rootを対象に実行

運用手順はfederation rootでのCIを推奨するが、CLI契約はcurrent directory条件を明示していない。推奨は2とし、
発見したfederation rootを対象へ昇格することである。1を選ぶ場合は、current directoryの正規化条件と
終了コード4を明記する必要がある。

## 4. FED-CLI-002 未知workspace ID

連合仕様は字句上妥当だがcatalogにない`--workspace`を`failed`にする。共通結果はworkspace単独操作へ
`workspace`を必須にし、reportも対象workspaceへ保存する。しかし対象workspaceが存在しないため、どのID/pathを
結果へ置き、どこへreportを保存するか決まらない。

推奨はcatalog lookupをinvocation validationとし、未知IDを終了コード4、結果・reportなしに統一することである。
不在IDを成果物Diagnosticとして扱うなら、`workspace`を呼出し時active workspaceにするなどの規則が必要になる。

## 5. FED-CLI-003 操作別member結果

[共通結果](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#2-共通結果)は`workspaces[]`の共通fieldを
定めるが、操作固有fieldは各操作仕様へ委ねている。現状では次が完全には確定していない。

- check: full scopeでmemberごとに返す対象件数
- verify: target、Context、binding参照、command実体
- doctor: top-level checkとmember checkのJSON field

操作ごとに全体結果の完全なJSON例とfield表を1つずつ追加し、unknown same-major field以外の必須性を固定すべきである。

## 6. FED-CLI-004 継続判定

「依存しない後続workspaceは可能な範囲で継続する」とあるが、catalog不正、Schema不正、横断参照不正、test失敗の
どれが全体停止条件かは列挙されていない。少なくともcatalog、workspace ID/path、未知Schema majorは連合索引の
信頼性に影響するため、対象選択前に全体を停止する方が安全である。文書単位不適合とcommand失敗は、解決済みの
独立memberを継続できる。

## 7. FED-CLI-005 revision

全体checkはrepository全体で1つの基準commitを使用するため、`revision`はtop-levelに1回置くのが自然である。
member結果へ複製すると不一致の余地が生じる。全体結果例で配置を固定し、member結果に置かないことを推奨する。

## 8. 成立を確認した契約

- `--all-workspaces`と明示対象、`--full`、`--workspace`の排他は明確である。
- `check --all-workspaces`はfull checkを含意する。
- `verify --all-workspaces`はworkspaceごとの引数なしverifyを起点にする。
- 全体処理順はroot、member ID辞書順である。
- top-level Diagnosticとmember Diagnosticを複製しない。
- 全体reportはfederation root、単独reportは対象workspaceへ保存する。
- Git基準版はrepository全体で1つに固定される。

## 9. 判定

CLIの基本構文は成立している。FED-CLI-001〜003をAPI freeze前に確定する必要がある。
