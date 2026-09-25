# resource上限の境界 fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-020-01..16`と`MULTI-021-01..08`を扱う。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 入力はcommitせず、dataset manifestから生成する

8つのdimensionの`limit - 1`、`limit`、`limit + 1`を実treeとしてcommitすると、repositoryは1 GiBを超える。
[ADR-048](../../../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)に従い、
各fixtureは`repo/`の代わりにdataset manifestを持ち、`setup.generate.treeDigest`で生成treeを固定する。
期待結果と副作用期待値も生成物なので、`expect.resultDigest`と副作用の`stateDigest`で固定する。
reviewの対象は生成器（`multi_generator.py`）とdataset manifestである。

生成器は、狙ったdimensionだけを指定値にし、ほかを通常規模へ保つ。dataset manifestは8つのdimensionの
実測値をすべて持ち、監査は「狙った以外のdimensionが上限を超えていないこと」をその実測値から確かめる。
計数（`count`）は生成計画を読まず、生成したbyte列だけから数え直す。

## 入力側の上限とぶつけない

生成物は、[安全な入出力・互換性 §4](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md)の
入力上限（設定64 KiB、SPEC 1 MiB、1文書の配列項目と規範文1,000件）を越えない形に分けている。

- commandはworkspaceあたり800件までに分け、10,000件の定義には13 workspaceを使う。
- 100万件のrelation edgeは1,000件ずつ別文書へ置き、targetは重複しない実在文書（target専用の
  補充文書を最大1,000件用意し、各edge文書はそこから重複なく参照する）にする
  （2026-09-25訂正。下の節を参照）。
- verify binding境界は、1 workspace分のtest対応をBINDINGS_PER_DOCUMENT（300）件ごとの複数文書へ分け、
  1文書のFrontmatterを32 KiB以下に保つ（2026-09-25訂正。下の節を参照）。
- 100万件のtrace項目はTASKの`changes`へ1,000件ずつ置く。`changes`は字句の許可集合なので、pathの実在を要求しない。
- 256 MiBの入力は、1 MiB未満の補充文書を並べ、最後の1件でちょうどの値に合わせる。

規範文はTECHの`Contract` sectionへ置く。[文書種別・本文template §3](../../../docs/03.詳細設計/02_SPECモデル/03_文書種別・本文template.md)が
他sectionの規範行を`SPEC-STYLE-PLACEMENT-001`とするためである。

## 越える側は早期に停止する

`MULTI-021-*`は`SPEC-MULTI-LIMIT-001`／`blocked`／終了コード2を返し、`workspaces: []`でmember処理もcommand実行も
始めない。`evidence`は`dimension`、`limit`、`observedAtLeast`を持つ。`observedAtLeast`は越えたことがわかる
最小の値（`limit + 1`）とし、正確な総数を求めない。

`MULTI-021-08`だけは、`verifyBindingCount`がcommand定義の部分集合であるため`commandDefinitionCount`も
同時に超える。複合workspace仕様 §10へ「複数のdimensionが同時に超過する場合は、verify実行計画のdimensionを
優先して報告する」を加え、dataset manifestの`companionDimensions`へ同時に超えるdimensionを明示した。
監査は、宣言していないdimensionの超過を拒否する。

## 検証は2段階に分ける

既定の統合検証（`uv run fixtures/validate_conformance.py`）は、同じdataset manifestを一定比率で縮小したprofileで
生成器の決定論とdimensionの計数を照合する。上限も同じ比率で縮めるので、越える／越えないの関係は保たれる。
実寸の生成、tree digest、期待結果のdigest、副作用のstate digestの照合は`uv run fixtures/validate_scale.py`が行い、
Gate Aの認定にはその記録を必要とする。

## 訂正（2026-09-25）：relation edge配列内のtarget重複

根拠の規範文：[文書・Frontmatter・状態仕様 §11](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#11-yaml制約)
「scalar配列の重複は、YAML解釈後の値と型の完全一致で判定し…重複配列はfieldの値域不正として
`SPEC-FM-SCHEMA-001`を返す」。

食い違い：`multi_generator.render_edge_document`は、1つのedge文書の`relations.requires`配列へ、
**同じtarget ID**（`TECH-000001`）を`edges`件並べていた。これは規範文の配列重複規則に反し、
Coreが実際に本文書を検査すれば（配列項目の値域不正として）`SPEC-FM-SCHEMA-001`を返し、
`MULTI-020-09`・`MULTI-020-10`（境界内`passed`を期待）が成立しない。`MULTI-021-05`
（`relationEdgeCount`超過。境界超過は入力を検査する前に`SPEC-MULTI-LIMIT-001`で早期停止するため
実害はないが、同じ生成器を使うため入力treeの形は同じ問題を持っていた）も同様。

訂正内容：`multi_generator.py`を、edge文書1件につき重複しないtargetを並べるよう直した。
1つのrelationEdgeCount profileにつき、target専用の補充文書（`render_filler_document`と同形、
`relations`を持たない）を`min(ITEMS_PER_DOCUMENT, 最大のchunk size)`件だけ生成し、各edge文書は
そこから重複なく`targets[:edges]`を参照する。target文書自身は`requires`を持たないため、
edge文書同士やtarget文書を経由した循環（`requires`＋`refines`の禁止循環。
[関係・トレースモデル §4](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#4-型制約)）
は生じない。影響を受けた`MULTI-020-09`・`MULTI-020-10`・`MULTI-021-05`のdataset manifest、
tree digest、期待結果digest、副作用state digestを生成器の実行から作り直した
（specFileCountがtarget文書の分だけ増える。他dimensionの値・境界超過判定は変えていない）。

## 訂正（2026-09-25）：verify binding境界のFrontmatter 32 KiB超過

根拠の規範文：[安全な入出力・互換性 §4](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#4-resource上限)
のFrontmatter 32 KiB上限（[文書・Frontmatter・状態仕様 §11](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#11-yaml制約)）。

食い違い：`verifyBindingCount`境界（`MULTI-020-15`・`MULTI-020-16`・`MULTI-021-08`、値9,999〜10,001）は、
1 workspace分のtest対応（最大約770件）を1つのTECH文書のFrontmatterへ置いており、実測で最大64,758 byte
（32 KiB=32,768 byteの約2倍）に達していた。Coreが実際に本文書を検査すれば、Frontmatter超過として
`SPEC-INPUT-LIMIT-001`／`skip-document`（Diagnostic registryの`INPUT-LIMIT-FRONTMATTER`）を返し、
「境界内は全bindingを実行してpassed」という期待が成立しない。

訂正内容：`multi_generator.py`に`BINDINGS_PER_DOCUMENT = 300`（実測で389件が32 KiB以内に収まる上限。
安全側に300とした）を導入し、1 workspace分のtest対応をこの件数ごとの複数のTECH文書へ分けて生成するよう
直した（`emit`のworkspaceループ）。verifyBindingCount以外のdimensionは1 workspaceのbinding件数が小さいため
（既定1件）、分割は起こらず生成物は変わらない。参照計算側（`multi_limit_fixtures.binding_documents`・
`passed_binding_result`、`validate_scale.py`の`binding_digests`、`fake_core.py`の`_binding_digests`）も、
1 workspaceが複数のbinding文書を持てるよう直した。影響を受けた3件のdataset manifest、tree digest、
期待結果digest、副作用state digestを生成器の実行から作り直した（binding数と他dimensionの値は保った）。

## 訂正（2026-09-25）：member数境界のmaxMembers省略

根拠の規範文：[複合workspace仕様 §2](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#2-配置とcatalog)
「`multiWorkspace.maxMembers`の既定は20…`members`が実効上限を超えれば`blocked`とする」。

食い違い：`MULTI-020-01`（member 99）・`MULTI-020-02`（member 100）は、root設定へ`maxMembers`を
明示せず、既定値20が効く状態で「境界内は`passed`」を期待していた。既定20のままCoreが実際に検査すれば、
99・100 memberはどちらも既定上限20を超えて`blocked`になり、期待と矛盾する。この2件とその対の
`MULTI-021-01`（member 101、超過）は、Core hard limit 100そのものの境界を検査する意図である。

訂正内容：`multi_generator.render_config`を、`dimension == "memberCount"`のprofileでは
root設定へ`multiWorkspace.maxMembers: 100`（`LIMITS["memberCount"]`）を明示するよう直した。
`MULTI-021-01`の期待（`evidence.limit: 100`で`blocked`）は、複合workspace仕様 §10のlimit
Diagnostic `evidence.limit`が「適用した上限」を表すこと、かつ明示した`maxMembers`がCore hard limit
100と同値であることから、そのままでよいと確認した（値の変更なし。入力配置だけ訂正）。影響を受けた
3件のdataset manifest、tree digest、期待結果digest、副作用state digestを生成器の実行から作り直した。

## 限界

- Coreは実行していない。実際に上限で遮断するか、境界内を通すかはGate Bで判定する。
- 期待結果は生成物であり、digestで固定する。人が読むのは生成器とdataset manifestである。
- 1つのfixtureは1つのdimensionだけを越える。全dimensionを同時に最大化した入力は扱わない。
- 基準環境でのpeak RSS 1 GiB以下という受入条件は、Coreの実行を伴うためGate Bで測定する。
