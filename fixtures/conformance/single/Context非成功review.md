# コンテキストの非成功のfixtureのレビュー記録

2026-09-14。SINGLE-050、051、052-01〜02、053の5件について、Coreの実装前の固定した入力、完全な期待JSON、
読取り専用の副作用の期待値を作成する。これらはCoreが返した観測結果ではない。

## 入力と単一原因

| ID | 起点／目的 | 入力 | 期待する状態／終了コード／診断 |
|---|---|---|---|
| SINGLE-050 | TECH-999／`interpret` | TECH-001だけが存在し、TECH-999は存在しない | `failed`／1／`CTX-ROOT-MISSING-001` |
| SINGLE-051 | TASK-001／`implement` | `open`のTASK-001が、`open`のTASK-002を`requires`する | `blocked`／2／`CTX-TASK-DEPENDENCY-001` |
| SINGLE-052-01 | TECH-001／`implement` | `approved`のTECH-002が、`approved`のTECH-001を`supersedes`する | `blocked`／2／`CTX-STATE-SUPERSEDED-001` |
| SINGLE-052-02 | TECH-003／`implement` | 上記に加えて、`approved`のTECH-003が旧TECH-001を`requires`する | `blocked`／2／`CTX-STATE-SUPERSEDED-001` |
| SINGLE-053 | TECH-001／`implement` | `approved`のTECH-002とTECH-003が、ともにTECH-001を`supersedes`する | `failed`／1／`CTX-STATE-SUPERSEDED-002` |

全件とも、最小設定の単一ワークスペースで、`git init`だけを行った、コミットのないリポジトリを使う。
`context`は`--base`を受け付けず、コミットを必要としないため`baseCommit`を作らない。目的を明示し、`--format json`を使用する。
TECHは規範文、`implements`、`tests`、`command`を持たず、TASKは`addresses`と`changes`を持たない。
これにより、カバレッジの不足、パスの不在、コマンドの不在、REQの保護を、原因へ混ぜない。

050では、IDの字句そのものは妥当であり、引数不正（終了コード4）にせず、操作の結果を返す。存在するTECH-001へ起点を置き換えない。
051の`requires`は、存在するTASKへの、型が正しい関係で、循環もない。先行するTASKが`done`でないことだけが、`blocked`の原因である。
052系は、旧TECHの文書の状態を`approved`のまま保持する。後継の存在は逆索引で検出し、文書の状態が`draft`または`outdated`の場合とは区別する。
目的`interpret`で後継を提示する経路と混ぜないよう、目的`implement`を明示する。052-02では、起点のTECH-003自体は置換されていない。
053は、1つの旧文書に有効な後継が2件あるという単一の原因であり、後継が1件の場合の診断（`blocked`）を重ねず、
後継の重複の診断（`failed`）を1件に固定する。最小のIDの後継を選択しない。

## 完全期待値の選択

- `roots`は、呼出しで指定した1件をそのまま保持する。後継や既知の起点への差替えを禁止する。
- `workspace`は`id=root`、`path=.`とする。Git自体は利用可能だが、コミットのないリポジトリなので`revision=null`とし、Git不在の警告を加えない。
- IDの検査、状態の検査、強い関係の検査で完全解決に到達しないため、`contextDigest=null`、`resolution.complete=false`、
  `documents=[]`、`constraintLedger.statements=[]`とし、`coverage`の`must`・`should`・`may`の各5配列と`adjacent`を空にする。
- `documentCount=0`は、完成した解決の集合をまだ出力しないことを表す。`unresolvedStrongRelations=0`とする。
  050は、明示した起点の不在であって、強い関係のエッジの不在ではなく、他の4件は、参照先がすべて存在する状態の検査または後継の検査の失敗である。
- `projection`は`detail=standard`、`expanded=[]`とする。`durationMs=0`で、既存の正規化器以外の比較の除外を追加しない。
- 重大度は全件`error`とする。050は、発生元の種類`invocation`で`argument=TECH-999`、051は、TASK-001の`relations.requires`を発生元とする。
  052と053は、置換される対象のTECH-001を発生元（種類`file`）にする。逆索引で判定するため、旧文書に存在しない`supersedes`のキーは付けない。
  行、列、証跡、`suggestedAction`は加えず、`summary`は、各`expected/context.json`の今回選択した文字列に固定する。

この空の非成功のコンテキスト一式と、診断の位置・文言・件数は、既存の規範に沿って今回固定した受入の期待値であり、
すべての非成功のコンテキストに共通する本番の処理を、この検証プログラムへ実装したものではない。

根拠は[`context`仕様 §2〜§4・§10](../../../docs/03.詳細設計/03_操作仕様/01_context.md)、
[関係・トレースモデル §3〜§6](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)、
[状態・適用可能性](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[結果・診断・終了コード](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)、
[診断レジストリ](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合matrix §6.5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証

`context_failure_fixtures.py`は、固定した入力のバイト列、レビュー済みのフロントマターの値のスキーマ、マニフェスト、完全な期待JSON、
読取り専用の副作用の期待値を照合する。起点と閉包の展開、状態の適用可否、ハッシュ値の計算などの、製品の処理は実装しない。
各fixtureを隔離環境で2回準備し、Gitリポジトリとシンボリックな`HEAD`の存在、`HEAD`が未解決であること、
Gitの参照とインデックスが空集合であること、作業ツリーの内容を確認する。
リポジトリ、`git status`とGitのインデックス、`HOME`・キャッシュ・`TMPDIR`のスナップショットを固定値へ照合し、`before=after`を要求する。
Core実行後の観測値ではなく、副作用0の期待値である。

回帰試験では、起点の差替え、非成功の成功化、誤った診断、ハッシュ値の捏造、`resolution`の成功化、
文書件数とカバレッジの部分的な出力、後継の重複の診断の降格と二重化、目的の変更、Gitのスナップショットの消去を拒否する。
入力については、先行するTASKの`done`化、`supersedes`または`requires`の弱い関係化、後継の`draft`化、起点のIDの追加を検出する。
実際のリポジトリへのステージや初回のコミットも、コミットのないリポジトリの照合で拒否する。
実際のCoreの結果と副作用は、Gate Bで受け入れる。

準備済みは65/311件、残りは246件。成功のコンテキストと独立したgoldenのハッシュ値など、新しいチェックアウトからのGate Aの全検証は未完了であり、
Gate Aは`Blocked`を維持する。
