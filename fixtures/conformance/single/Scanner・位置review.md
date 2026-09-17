# Scanner・位置 fixtureレビュー

2026-09-14。matrix §6.10のcheck 16件（SINGLE-096-02、097-02、098-02、099-01〜04、100-01〜04、
101-02/03、102、103-01/02）を追加する。IRとDigestの完全比較を要する`context` 4件
（096-01、097-01、098-01、101-01）は同節の残件として分離する。
根拠は[EARS-AI言語・Semantic-IR仕様](../../../docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)§3〜§5、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の各matrix IDである。

| ID | 唯一の条件 | code | status／終了コード | 位置(行, 列) |
|---|---|---|---|---|
| SINGLE-096-02 | 開始run 2に対し終了run 1 | `EAI-CORE-SYNTAX-005` | failed／1 | 16, 73 |
| SINGLE-097-02 | 未知escape `\出` | `EAI-CORE-SYNTAX-004` | failed／1 | 16, 74 |
| SINGLE-098-02 | quoted extension値が未閉鎖 | `EAI-CORE-SYNTAX-004` | failed／1 | 16, 34 |
| SINGLE-099-01 | backtick fence内 | — | passed／0 | — |
| SINGLE-099-02 | tilde fence内 | — | passed／0 | — |
| SINGLE-099-03 | 引用内 | — | passed／0 | — |
| SINGLE-099-04 | 4 SP indent | — | passed／0 | — |
| SINGLE-100-01 | 桁不足の既知prefix | `EAI-CORE-ID-001` | failed／1 | 16, 3 |
| SINGLE-100-02 | 未知uppercase prefix | `EAI-CORE-ID-001` | failed／1 | 16, 3 |
| SINGLE-100-03 | 3階層ID | `EAI-CORE-ID-001` | failed／1 | 16, 3 |
| SINGLE-100-04 | `[ACTOR:...]`始まりのID欠落 | `EAI-CORE-ID-001` | failed／1 | 16, 3 |
| SINGLE-101-02 | `[MUST] [REASON]` | `EAI-CORE-SYNTAX-001` | failed／1 | 16, 56 |
| SINGLE-101-03 | `[MAY] [REASON]` | `EAI-CORE-SYNTAX-001` | failed／1 | 16, 55 |
| SINGLE-102 | 全角文字とTABの後の未escape `[` | `EAI-CORE-SYNTAX-004` | failed／1 | 16, 80 |
| SINGLE-103-01 | 未閉鎖code spanと未閉鎖tagの同一原因 | `EAI-CORE-SYNTAX-005` | failed／1 | 16, 73 |
| SINGLE-103-02 | 未閉鎖tagとID形式不正の同一原因 | `EAI-CORE-SYNTAX-004` | failed／1 | 16, 3 |

全件が既存のEARS文書builderを使い、15行目の有効な規範文を保ったまま16行目だけを差し替える。
承認済みREQに妥当な規範文が残るため、規範文不在の別条件を混ぜない。
文書statusはすべてapprovedとし、draftのwarning分岐（SINGLE-008〜009-03）と重複させない。
100-01〜03は§6.2のdraft版と同じ入力形で、approvedでも候補抽出が働き同じ形式不正を返すことを固定する。
101-02は`[WHEN]`起点のSINGLE-007と異なり`[ALWAYS]`で揃え、101-03との差を規範強度だけにする。

列は固定byte列から`[SHOULD]`等のanchor tokenの最初の出現位置を1始まりcode pointで再計算して照合する。
TAB、全角文字、結合文字を各1列と数える規則をSINGLE-102が固定する。
103-01は同じ行のrawから未閉鎖code spanと未閉鎖tagの両候補が生じる形にし、registryのpriority順どおり
`EAI-CORE-SYNTAX-005`だけをprimaryとする。103-02はID bracketを閉じないことで未閉鎖tagとID形式不正を
同時に生じさせ、`EAI-CORE-SYNTAX-004`だけをprimaryとする。回帰試験は低優先条件への差し替えを拒否する。

099-01〜04は同一の規範文様textを、fence、引用、indentという構造だけ変えて包む。
包みを外した入力は監査が拒否する。候補0件のため文書1件・規範文1件（15行目のみ）を検査したまま成功する。
098-02の未知namespace extensionは`skip-document`のため`EAI-CORE-SYNTAX-004`だけを返し、
`EAI-EXT-UNKNOWN-001`を重ねない。

入力byte列・manifest・完全結果・副作用Schemaを検証し、隔離Git repositoryを2回setupして固定snapshotへ照合する。
失敗時の検査件数は0／0、成功時は1／1で固定する。回帰試験は列のずれ、件数、code、二重診断、
位置fieldの欠落、副作用の許容、規範文の差し替えと包みの除去を拒否する。
Scanner、Lexer、Parser、Coreは実装も実行もしない。実際の候補抽出と位置出力はGate Bで受け入れる。
