# TASK境界・対象選択のfixtureのレビュー記録

2026-09-14。SINGLE-034、SINGLE-035-01〜02の3件について、同じ入力を、異なる範囲（`scope`）の`check`で検査する、
完全な期待値を固定する。Coreの実行結果ではない。

## 入力と期待値

全件の`HEAD`に、最小設定、`open`のTASK-001、`src/inside.py`、`src2/outside.py`を置く。
TASKの`changes`は`[src/]`だけで、関係や規範文を持たない。`HEAD`から、TASKの`Objective`への説明の追記と、
`src2/outside.py`のコメントの変更だけを、未ステージで行う。`src/inside.py`は存在するが変更しない。
3件の入力とGitの状態は同一とし、呼出し方による差を固定する。

| ID | 呼出し（共通で`--base HEAD --format json`） | 期待値 |
|---|---|---|
| SINGLE-034 | `check TASK-001` | `scope: selected`、`failed`／1、`SPEC-TASK-BOUNDARY-001`が1件 |
| SINGLE-035-01 | `check` | `scope: changed`、`passed`／0、診断なし |
| SINGLE-035-02 | `check --full` | `scope: full`、`passed`／0、診断なし |

034は、`src/`と`src2/`を、セグメントの境界で区別し、`src2/outside.py`だけを境界の外とする。
TASK自身の変更は、境界の比較の対象から除外されるため、2件目の診断を追加しない。
発生元は、違反したファイルの`workspaceId=root`、`path=src2/outside.py`とし、`summary`は`expected/check.json`の値に固定する。
行、キー、証跡、`suggestedAction`は付加しない。この発生元の位置と文言は、今回の受入の期待値として選択した値である。

035-01では、TASKの説明の変更により、引数なしでもTASKが確実に選ばれる。変更したパスの数は2、対象の文書数は1、
未所有のコードとテストの除外したパスの数は1とする。TASKの`changes`は、コードの所有の逆索引を作らない。
境界を検査しないことや、未所有のコードの存在を、警告にしない。035-02も、全体の文書の検査だけを行う。
`scope: selected`と`scope: full`では、完全検査した文書数1、規範文数0とし、`scope: changed`だけに`selection`を出力する。
全件の`revision`は`HEAD`の代表値と`dirty=true`、`durationMs=0`で、既存の正規化器以外の比較の除外は追加しない。

根拠は[`check`仕様 §3・§5〜§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[フロントマター仕様 §3](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[診断レジストリ](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合matrix §6.4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証の範囲

`task_fixtures.py`は、レビュー済みの固定したバイト列、マニフェスト、完全な期待JSON、フロントマターのスキーマ、読取り専用の副作用の期待値を照合する。
各fixtureを隔離環境で2回準備し、`HEAD`とインデックスのパスとブロブ、作業ツリーの全ファイルのバイト列、`git status`とGitのインデックス、`HOME`・キャッシュ・`TMPDIR`を確認する。
本番の対象の選択やパスの境界の判定、汎用のYAML解析は実装しない。

回帰試験では、境界違反の成功化、発生元の`src/`への変更、TASKを明示した指定の除去、対象と除外の件数の誤り、
`scope: full`への警告の混入、規範文数の誤り、副作用の期待値の変更、許可範囲の拡大、TASKが選ばれる原因の消去を拒否する。
実際のリポジトリの変更をステージまたはコミットした場合にも、`HEAD`とインデックスの照合が失敗することを確認する。
Coreの実際の標準出力、終了コード、境界の判定、実際の副作用は、Gate Bで受け入れる。

準備済みは53/311件、残りは258件。goldenのハッシュ値などと、新しいチェックアウトからのGate Aの全検証は未完了であり、
Gate Aは`Blocked`を維持する。
