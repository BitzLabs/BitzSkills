# 上限・未知entry fixtureレビュー

2026-09-14。SINGLE-078、079-01/02、080-01/02/03、083の7件を追加する。
根拠は[安全な入出力・互換性](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md)§4のresource上限、
[workspace・設定仕様](../../../docs/03.詳細設計/02_SPECモデル/01_workspace・設定仕様.md)§3の探索対象、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の各matrix IDである。

| ID | 唯一の条件 | status／終了コード | 検査文書／句 |
|---|---|---|---|
| SINGLE-078 | `bitz.yaml`が64 KiB超 | failed／1 | 0／0 |
| SINGLE-079-01 | SPEC Markdownが1 MiB超 | failed／1 | 0／0 |
| SINGLE-079-02 | Frontmatterが32 KiB超 | failed／1 | 0／0 |
| SINGLE-080-01 | 規範文と関係配列が上限ちょうど | passed／0 | 1／1000 |
| SINGLE-080-02 | 1文書の規範文が1,001件 | failed／1 | 0／0 |
| SINGLE-080-03 | 1文書の配列項目が1,001件 | failed／1 | 1／1 |
| SINGLE-083 | `.spec/`直下の未知file | passed_with_warnings／0 | 1／1 |

入力は固定定数から生成し、生成後のbyte列を上限へ再度あてて、交差する次元が1つだけであることを監査で確かめる。
上限内の次元は上限内のままであることも同時に確かめるため、prose上の主張ではなく実byte数が条件を決める。

SINGLE-078はcomment行だけで64 KiBを超える。commentはkeyを増やさないため、設定Schemaの原因を重ねない。
有効なREQ 1件を同梱し、`stop-operation`で検査件数が0のままであることを固定する。
SINGLE-079-01はVerification節の後へ固定散文を足して1 MiBを超え、Frontmatterは上限内に保つ。
SINGLE-079-02は`x-`拡張field 1件で32 KiBを超える。`x-`は未知field warningを生まず、file全体は1 MiB未満に収める。

SINGLE-080-01は規範文1,000件と`tests[0].covers` 1,000件をちょうど上限に置く。test pathは実在させ、
path不在やcoverage不整合の診断を重ねない。coversは同一文書の全規範文を1件ずつ指し、対応重複を作らない。
SINGLE-080-02はSINGLE-080-01との差分を規範文1行だけにし、coversは1,000件のままとする。
SINGLE-080-03は差分をcovers 1件だけにする。1,001件目も解決する必要があるため、規範文1件だけのREQ-002を置く。
これで参照先不在を重ねず、原因を配列項目数に限定できる。`skip-document`によりREQ-002だけが検査され1／1となる。
SINGLE-083は`.spec/notes.txt`をSPEC pathではないentryとして1件だけ置き、warning後も文書検査を継続して1／1とする。

診断sourceは、file寸法の上限は対象file path、配列項目数は`tests[0].covers` keyを付ける。
規範文数とFrontmatter寸法は単一keyへ原因を帰せないためkeyを付けない。line/column、evidence、suggestedActionは
この期待値では付加しない。診断summaryは期待JSONの文字列を固定する。

入力byte列・manifest・完全結果・副作用Schemaを検証し、隔離Git repositoryを2回setupして固定snapshotへ照合する。
baselineへ入力をcommitし、report・cache等への書込みは許可しない。
回帰試験は件数・コード・severity・source・keyの改変と副作用の許容を拒否し、さらに各fixtureの入力を上限の反対側へ
差し替える改変も拒否する。上限検査もYAML parserもCoreも実装しない。
実際の継続単位（`stop-operation`と`skip-document`）と検査件数の観測はGate Bで受け入れる。
