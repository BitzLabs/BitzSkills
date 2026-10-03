# 対象展開の期待集合

設計・検証日: 2026-09-08。
正本は[関係・トレースモデル §6.4](../../../docs/03.詳細設計/02_仕様文書モデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)。

## 入力と期待値

`cases.json`は、索引で解決済みの小さなグラフ、起点、目的、固定した期待値を持つ。単一ワークスペースは非修飾ID、複合ワークスペースは修飾IDを使う。
`cases.schema.json`は、未知のフィールドと期待配列の重複を拒否する。根拠契約のハッシュ値を固定し、変更したときは期待値の再レビューを要求する。
グラフは、`approved`のREQとTECH、`accepted`のADR、`open`または`done`のTASKに限定する。適用できない状態の診断は、既存の適合matrixの別のケースで扱う。

起点の種別（REQ、規範文のあるTECH、規範文のないTECH、規範文、TASK、ADR）の6種類×3つの目的を、18の基本ケースで固定した。
ADRの目的`implement`と`verify`は`context`のCLIの拒否の期待であり、`TargetExpansion`がエラーのオブジェクトを返すというAPIの追加ではない。
成功ケースの4つの配列は`rootDocuments`、`contextDocuments`、`targetStatements`、`adjacentStatements`で、要素と順序を完全に比較する。
目的`interpret`の`targetStatements`は空である。規範文を起点にした場合は、指定した規範文以外の兄弟句を隣接規範文とする。

## 追加の7ケース

| ケース | 確認内容 |
|---|---|
| `REFINEMENT-TRANSITIVE` | 推移的な具体化は対象に含め、`requires`の参照先はコンテキストにだけ含め、`related`は追加しない |
| `STATEMENT-ADJACENT` | 指定した規範文と具体化だけを対象とし、兄弟句は隣接規範文とする |
| `MULTI-ROOT-DEDUP` | 文書、規範文、重複した起点の和集合とし、対象へ選ばれた規範文は隣接規範文から除く |
| `TASK-REQUIRES-NOT-TARGET` | `verify`の起点TASKは、`addresses`の参照先だけを対象規範文とし、先行する`done`のTASKとその`addresses`の参照先をコンテキストへ含めない |
| `OPEN-TASK-IMPLEMENT` | 目的`implement`で、対象規範文を`addresses`する`open`のTASKをコンテキストへ追加する |
| `MULTI-WORKSPACE-SAME-LOCAL-ID` | 同名のローカルIDをワークスペースごとに区別し、ワークスペースをまたぐ具体化を対象へ追加する |
| `SOURCE-LINE-ORDER` | IDの辞書順よりも行番号の順を優先する |

`matrixFamilies`は関連する論点の索引であり、そのファミリーの全適合試験を完了したという意味ではない。
このグラフのfixtureは、`repo/`、マニフェスト、`expected/`の公開結果を持つ311件の適合fixtureを置き換えない。
規範文のないTECHの4つの集合は確認するが、文書単位のテスト割当ての保持、共有するコマンドの実行回数、検証対象ごとの証跡は、`verify`の適合試験で確認する。

## 検証

`uv run fixtures/validate_conformance.py`から`target_vectors.py`を実行する。
固定した期待値を、検証用の参照グラフの計算と照合し、入力のグラフ、起点、関係、規範文の配列を反転しても一致することを検査する。
スキーマ、18の組合せの網羅、IDと型、参照の存在、`requires`と`refines`による依存の非循環、matrixのファミリーの参照、根拠契約のハッシュ値も検査する。
回帰試験では、組合せの欠落、`requires`の参照先の対象への混入、順序の誤り、未知の参照を検出する。
期待値を実行中に再生成も更新もしない。参照計算はこの固定したグラフの準備の検証用であり、製品の構文解析器でも、完全なコンテキスト解決器でもない。
CoreのJSON出力、状態の判定、テスト割当て、コンテキストのハッシュ値との一致はGate Bで別に検証する。

2026-09-17: 関係・トレースモデル §6.3に合わせ、`TASK-REQUIRES-NOT-TARGET`の`contextDocuments`から先行する`TASK-002`を外した。
参照計算も、`verify`の起点TASKで`requires`をたどらないよう修正し、ほかの24ケースの期待集合は変わらないことを確認した。

2026-09-17: ADR-047に従い、`FEDERATED-SAME-LOCAL-ID`を`MULTI-WORKSPACE-SAME-LOCAL-ID`、matrixのファミリーの`MONO-*`を`MULTI-*`へ改名した。
関係・トレースモデルの変更は診断コードの改名だけで、25ケースの期待集合は変わらない。

2026-09-26: 2026-09-25に管理者が承認した仕様変更（`docs/03.詳細設計/02_仕様文書モデル/04_関係・トレースモデル.md`のコミット）で
`contractSha256`が失効した。差分を確認したところ、追加された記述は§4「関係の型制約」への1段落（`requires`の参照先のADRが
`accepted`以外の状態なら診断`CTX-RELATION-TYPE-001`とすること、状態の適用可能性は`CTX-STATE-*`の側の責務であることの明確化）
だけであり、本節が正とする§6.4 `TargetExpansion(root, purpose)`の記述と、`rootDocuments`、`contextDocuments`、`targetStatements`、
`adjacentStatements`の算出規則には変更がない。したがって25ケースの期待集合、グラフ、`matrixFamilies`の参照は変えず、
`contractSha256`を新しい文書のハッシュ値（`4bfe2f87773764c40e216b366d6429c6004ce96895a24cf6eb1cc720f4bc0e70`）へ更新するだけで足りる。

2026-09-29: 関係・トレースモデルの説明文を日本語表記へ書き直した（日本語表記の立て直し計画のPR 3）ため、`contractSha256`が失効した。
表記の変更だけで、§6の展開規則は変えていない。§6.1の4.の「target」は読みを確定せず一般の「対象」と書き、
参照計算（閉包内の起点を含む文書を`refines`する文書を加える）と矛盾しないことを独立のレビュー担当が確かめた。
`contractSha256`を新しい文書のハッシュ値に置き換えた状態で、25ケースの期待集合が参照計算と一致することも確かめた。
25ケースの期待集合、グラフ、`matrixFamilies`の参照は変えず、`contractSha256`を新しい文書のハッシュ値
（`dc1880ca671dfa453ac2eca66a8bc64006f52ea10a41d6371cc3fa70cd72812d`）へ更新した。
