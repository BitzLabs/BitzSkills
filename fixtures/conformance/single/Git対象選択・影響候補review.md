# Git対象選択・影響候補fixture review

2026-09-14。SINGLE-033、039、040、041の4件について、入力・Git状態・完全期待JSON・読取り専用副作用期待値を固定する。
これはCore実行結果ではなく、Step 0Bの受入準備である。

## 入力と単一原因

| ID | Git状態と入力 | 呼出し | 期待値 |
|---|---|---|---|
| SINGLE-033 | approved TECH-001のtitleと対応H1だけを未stage変更。TECH-002がrequires、003がrelatedで001を参照し、004が002をrequires | check --full --base HEAD --format json | full、passed_with_warnings / 0、TECH-002への影響候補warningだけ |
| SINGLE-039 | Git init済み、commit・ref・index entryなし。最小設定とapproved TECH-001が未追跡 | check --format json | full、passed / 0、revision=null |
| SINGLE-040 | 最小設定とapproved TECH-001をcommit済み。変更なし | check --base HEAD --format json | changed、passed / 0、selectionの3件数がすべて0 |
| SINGLE-041 | 最小設定とapproved TECH-001と未所有codeをcommit済み。code更新をstageし、未所有testを未追跡で追加 | check --base HEAD --format json | changed、passed / 0、変更2・対象文書0・未所有除外2 |

全TECHは規範文を持たず、implements/tests/verifyを宣言しない。commandを定義・実行しない。
設定不正、Git不在、状態遷移不正、REQ意味変更保護を原因へ混ぜない。

033の唯一の変更文書はTECH-001で、TECH-002〜004はHEAD/index/worktreeで同一である。
直接strong逆参照のTECH-002だけをSPEC-IMPACT-OUTDATED-001 / warning / passed_with_warningsとする。
弱いrelated参照の003と、変更されていない002に依存する004へ影響を伝播しない。
TECHのtitle変更はapproved REQ保護の対象外であり、title/H1は同時に更新してH1不一致を避ける。
sourceはTECH-002のrelations.requires、summaryはexpected/check.jsonの文字列を今回の受入期待値として選択した。
line、column、証跡、suggestedActionは付加しない。full検査文書数は4、規範文数は0。
全TECHのstatusはapprovedのままで、Coreによるoutdatedへの自動変更を読取り専用期待値で許さない。

039はGit自体が使用可能なunborn状態である。Git不在warningを追加せず、明示--baseも指定しない。
empty treeや架空commitをrevisionへ置かず、全体検査文書数1・規範文数0を返す。
040では文書が存在していてもchanged-onlyの対象は0件であり、fullやPre-checkの代用としない。
041ではimplements/tests逆索引の所有者が存在せず、path名だけからTECHを選ばない。
code更新はbase→index、test追加は未追跡集合から数える。testには誤起動時の失敗を置くが、
checkが実行しないことの実証はGate Bで行う。040・041ともDiagnosticを返さない。

commitありの3件では既定normalizerの40桁0をrevision.base/commitの代表値に使い、
dirtyは033・041でtrue、040でfalseとする。全件durationMs=0で、既存normalizer以外の比較除外を追加しない。

根拠は[check仕様 §3・§5・§6・§8・§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[安全な入出力 §8](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md)、
[文書・Frontmatter・状態仕様 §8](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合matrix §6.4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証

selection_fixtures.pyはreview済みbyte列と固定Frontmatter値、manifest、完全期待JSON、副作用期待値のSchemaを照合する。
各2回の隔離setupでHEAD/indexのpathとblob、worktreeのfile集合とbyte列、Git status/index、HOME/cache/TMPDIRを検査する。
039はGit repositoryの存在、HEADのsymbolic ref、HEAD解決失敗、refとindexの空集合を個別に確認する。
HEAD解決失敗だけでGit不在とunbornを混同しない。041のindexは更新済みcodeを含み、未追跡testを含まない。

回帰試験はwarning消去・失敗化・弱い参照への付替え・間接依存への追加、unbornの偽revisionとGit不在warning、
明示base混入、対象・変更・除外件数の誤り、dirtyの誤り、stage手順の欠落、副作用期待値の変更を拒否する。
入力のstrong/weak変更、変更原因の消去、未所有codeへの所有宣言追加も拒否する。
実repositoryへ誤ってstageした変更、unbornへの初回commit、clean repositoryへの追加fileもGit状態照合で拒否する。
本番の対象選択・影響判定・YAML parserは実装しない。実結果と副作用の受入はGate Bで行う。

準備済み57/311件、残254件。golden Digest等とfresh checkoutからの全Gate A検証は未完了で、Gate AはBlockedを維持する。

後続のGit環境fixture作成時に、040・041の明示--base HEADを補正した。入力と期待結果は不変である。
詳細は[Git環境fixture review](Git基準版error・Git不在review.md)を参照する。
