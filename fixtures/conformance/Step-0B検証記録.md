# Step 0B検証記録

- 日付: 2026-09-17（下表は2026-09-14時点の構成。以後の追加は末尾の日付節を参照）
- command: `uv run fixtures/validate_step0b.py`
- 検証環境: CPython 3.14.6、Linux／POSIX、uv 0.11.32。validatorの依存versionはscriptのmetadataで固定した。
- Gate A: `Blocked`。commandの終了コードは1（未完了の証拠が残るため）。

| 検査 | 証拠 |
|---|---|
| 公開JSON | 操作結果、Diagnostic、fixture manifestの例10件が通過 |
| その他のJSON例 | Semantic IR／Digest材料の例5件を構文解析。結果Schemaによる保証はしない |
| EBNFの参照 | 定義33件と、散文で定義した字句集合3件。未解決の参照なし |
| Diagnostic review（2026-09-08更新） | 119条件を根拠文書17件へ対応付け。未解決の論点3件を解消し、台帳と回帰試験が通過 |
| matrixの一覧 | 310 ID（2026-09-17時点）、重複とfamily／接尾辞衝突なし。準備済み250件、未作成60件（複合workspaceのみ） |
| EARS fixture | SINGLE-007、008、009-01/02/03、010-01/02、011、012-01/02/03、013: 固定したREQのbyte列、Frontmatter Schema、完全な期待結果、Unicodeのtoken・行末の位置、隔離した2回のsetupを確認。位置・severity・code・件数・入力の改変を拒否 |
| 文書fixture（2026-09-11） | SINGLE-014、016、017-01/02/03、018-01/02/03、019: 不正なUTF-8を含む固定入力、完全な期待JSON、FrontmatterとSchemaの副作用期待値、隔離した2回のsetupがそれぞれ通過。skip／継続の件数、Diagnostic、report、副作用、入力の改変を拒否 |
| trace fixture（2026-09-11） | SINGLE-020、021、023、024、025、026: YAMLとdecode後のFrontmatterの組、完全な期待JSON、読取り専用snapshot、隔離した2回のsetupがそれぞれ通過。Diagnosticの重複、誤ったprimary・件数・severity・source、入力の修復、原因の追加を拒否 |
| graph fixture（2026-09-11） | SINGLE-015、022-01/02/03: TECH IDの重複と、requires／refines／relatedの自己参照。固定した完全な結果と読取り専用snapshot。隔離した2回のsetupと改変試験が通過 |
| Git fixture（2026-09-11） | SINGLE-027〜031: HEAD／index／作業treeの内容を固定し、遷移・新規・削除・rename・承認済みの意味変更を扱う。完全なJSONと読取り専用snapshot。隔離した2回のsetupと改変試験が通過 |
| 承認済みREQの保護対象外（2026-09-11） | SINGLE-032-01〜05: implements／tests／related／`x-` field／散文だけの変更、変わらない補助file、完全な成功JSON。HEAD／index／作業treeの比較を隔離した2回で行い、改変試験が通過 |
| TASK境界（2026-09-14） | SINGLE-034、035-01/02: 同じ2 pathの未stage変更で、明示TASKのsegment境界の失敗と、変更範囲・全体の成功を比べる。完全なJSON、HEAD／index／作業tree、読取り専用snapshotを隔離した2回で確認。scope、source、選択件数、権限、stageの改変を拒否 |
| Git対象選択・影響候補（2026-09-14） | SINGLE-033、039〜041: 直接の強い依存による警告と、弱い・推移的な依存の対照、unbornでの全体への縮退、変更のない空の選択、stage済みの所有者のないcode、未追跡のtest。完全なJSON、HEAD／index／作業tree、読取り専用snapshotを隔離した2回で確認。Diagnostic、revision、件数、所有、Git状態の改変を拒否 |
| Git環境（2026-09-14） | SINGLE-036〜038: `--report`付きの不正な明示基準版は既存reportを保ち結果を出さない。Git不在の全体・選択の結果はrevisionとGit snapshotをnullにする。隔離した2回のsetup、CLIのstreamの確認、改変試験が通過 |
| Context非成功（2026-09-14） | SINGLE-050、051、052-01/02、053: 起点不在、未完了の先行TASK、置換済みの起点・依存先、後継の重複。完全な非成功JSON、nullのDigestとunbornのrevision、空のBundle／coverage。隔離した2回のsetupと改変試験が通過 |
| 初期fixture | SINGLE-001、002、003、004-01/02、005-01/02、006-01/02: manifest・結果・副作用のSchemaと、review済みの入力の検査が通過。隔離した2回のsetupがそれぞれ固定した実行前snapshotと一致 |
| commandの前提 | 明示した実行fileの不在と、cwdの不在を分離。commandを実行せずに`/bin/true`の実行可能性を確認。原因の追加・欠落を回帰試験で拒否 |
| target vector（2026-09-08） | 基本の組合せ18件＋補足7件。順序付き集合4つ、入力順への非依存、拒否の回帰試験が通過 |
| 相対link | 現行の契約と承認済みADRの参照230件（2026-09-17時点）。参照先・anchorの欠落なし |
| Git基盤 | unborn、clean、作業tree、stage、rename、削除、作成。vectorごとに同じsetupを2回 |
| snapshotの比較 | 内容、実行bit、symlinkの参照先の変更を検出。安全でないpathの移動を拒否 |
| process helper | 終了コード0／7、SIGTERM、timeout、子孫によるpipeの保持。時間上限のある試験で、隔離したprocess groupを片付ける |
| 監査の回帰試験 | 不正な公開結果と未知の文法参照を拒否。Semantic IRを正しく分類。未作成のfixtureを検出。初期fixtureの結果・status・key・argv・復旧手順・snapshotの改変を拒否 |
| Step 0-P | 統合commandから再度通過 |

Gitとprocessのvectorは基盤の試験であり、適合fixtureやCoreの受入結果ではない。
読取り専用の実行前後の期待値は、導入・設定9件、EARS 12件、文書9件、trace 6件、graph 4件、Git・保護対象外10件、
TASK境界3件、Git対象選択・影響候補4件、Git環境3件、Context非成功5件について固定した。残りのcaseにはまだ期待値が必要である。
初期fixtureはCoreを実行していない。実行後のsnapshotは期待値であり、観測したCoreの副作用ではない。
この回で選んだdoctorのcheck名とDiagnosticの文字列は、[初期fixtureのreview](single/README.md)に記録した。
registryとmatrixの構造検査では、意味の網羅や単一原因への分離を証明できない。Diagnosticの意味上の判断は
[review済みの台帳](Diagnostic意味網羅review.md)に記録し、validatorは対応の欠落と根拠文書の変更を検出する。
独立に計算したgolden Context Digest、完全な受入の入力と結果、fresh checkoutからのGate Aの全体実行は未完了である。
Gate Aの承認とCoreの実装は含まない。

2026-09-11の実行は、最初の`uv run`による基準の後、固定したStep 0Bのuv環境のPythonを直接使った
（`python -B fixtures/validate_step0b.py`）。統合監査と回帰試験はerrorを報告しなかった。
監査reportの全体2件はbyte単位で一致し、未完了の証拠のため両方とも終了コード1を返した。
これは作業treeでの再現性であり、未完了のfresh checkoutでのGate A認定ではない。
文書の期待値の選択は[文書fixtureのreview](single/文書構造・UTF-8-review.md)に記録した。

続くtraceの6件は、統合監査と回帰試験を通過し、reportの2件はbyte一致した。
文書fixtureのSINGLE-017-02とSINGLE-018-01から余分な末尾の空行を除き、固定入力とsnapshotを更新した。
traceの期待値の選択は[trace fixtureのreview](single/関係・path・coverage-review.md)に記録した。

続くgraphの4件は、統合検査と回帰試験を通過し、監査reportの全体2件はbyte一致した。
graphの期待値の選択と限界は[graph fixtureのreview](single/文書ID重複・循環review.md)に記録した。
作業treeでの再現性は、未完了のfresh checkoutでのGate A条件を保証しない。

続くGitの5件は、統合検査と回帰試験を通過し、監査reportの全体2件はbyte一致した。
snapshotに加えて、HEADとindexのblobを固定した基準版・現在版の内容と直接照合した。
Gitの期待値の選択は[Git fixtureのreview](single/Git基準版・状態遷移review.md)に記録した。

続く保護対象外の5件は、統合検査と回帰試験を通過し、監査reportの全体2件はbyte一致した。
Gitの監査は10件を準備するようになり、変わらない補助入力をHEAD／index／作業treeで確認する。
期待値の選択は[保護対象外変更のreview](single/approved-REQの保護対象外変更review.md)に記録した。

2026-09-14のTASKの回は、統合検査と回帰試験を通過し、監査reportの全体2件はbyte一致した。
2回とも固定したStep 0Bのuv環境のPythonを直接使い（`python -B fixtures/validate_step0b.py`）、未完了のGate Aの
証拠だけを理由に終了コード1を返した。準備済み53/311、未作成258件。
これは作業treeでの準備の再現性の保証であり、Coreの挙動やfresh checkoutでのGate A条件の保証ではない。
期待値の選択は[TASK fixtureのreview](single/TASK境界・対象選択review.md)に記録した。

続く2026-09-14のGit対象選択・影響候補の回は、統合検査と回帰試験を通過した。
固定した環境での`python -B fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み57/311、未作成254件。
HEAD／index／作業treeの比較は、unbornの空のindexと、stage済みのcode・未追跡のtestの分かれ方を含む。
期待値の選択は[Git対象選択・影響候補のreview](single/Git対象選択・影響候補review.md)に記録した。
これは引き続き作業treeでの準備の証拠であり、Coreの挙動とfresh checkoutでのGate A認定は未完了である。

続く2026-09-14のGit環境の回は、統合検査と回帰試験を通過した。
固定した環境での`python -B fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み60/311、未作成251件。
新しいcaseは、不正な基準版のstreamの形とreportの保持を固定し、Git不在と空のGit statusを区別する。
SINGLE-040/041は、fixture契約どおり`--base HEAD`を明示するようにした。期待結果とsnapshotは変わらない。
matrixの回帰試験は、必須の基準版の省略と、Git不在のcaseへの基準版の指定を拒否する。
期待値の選択は[Git環境のreview](single/Git基準版error・Git不在review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のContext非成功の回は、統合検査と回帰試験を通過した。
固定した環境での`python -B fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み65/311、未作成246件。
5件は、要求した起点、正確な失敗のDiagnostic、nullのDigest、空の非成功Bundleを固定する。
unbornのrepositoryの検査と改変試験は、作ったcommit、stageした入力、暗黙の後継への置換え、部分的な成功を拒否する。
期待値の選択は[Context非成功のreview](single/Context非成功review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のContext Digestの回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み71/311、未作成240件。
SINGLE-042は単一workspaceのgolden Canonical JSONとDigestを所有する。SINGLE-043-01/02とSINGLE-045はそれと
byte一致し、SINGLE-044-01/02はそれとも互いとも異なる。
独立に書いた2系統の参照計算が一致する。Aはreview済みのliteralでDigest材料を記述し、Bはfixture自身のtreeから、
別の読取り処理と別のRFC 8785 serializerで組み立て直す。
Bを独立に書いたことで、B自身の欠陥を1件見つけて直した。EBNFでは`[SHOULD]`にだけ許される`[MUST] [REASON]`を
受理していた。期待値の選択と限界は[Digest fixtureのreview](single/Context-Digest-review.md)に記録した。
複合workspaceのgolden（MULTI-002-01）は未作成であり、Gate AのDigest条件のうち複合workspace側は未完了である。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14の非成功Contextの回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み77/311、未作成234件。
これでmatrixのcontextとDigestの節（SINGLE-042〜SINGLE-054）が完了する。
群全体に2つの規則を適用し、監査が強制する。非成功のContextはBundleの材料を返さないこと、
contextDigestは完全解決が成立した場合に限りnullでないことである。
SINGLE-046とSINGLE-047は、別の定数ではなくSINGLE-042がcommitしたDigestを返す。
SINGLE-049は、標準の提示と閉包を設定の最大値に収めたまま、本文1,071,063 byteで固定の1 MiBの提示hard limitを越える。
SINGLE-054は、implementのpurposeによる固有のDigest材料を持ち、bindingを記録せず、`addresses`するTASKを加える。
これらの入力に対して参照計算Bを書いたことで、2点を直した。既定値を仮定せず設定から
context.maxDocuments／maxBytesを読むこと、推移的なrefinementの連鎖をたどることである。期待値の選択と限界は
[非成功Contextのreview](single/Context-stale・上限・coverage-review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のverifyの回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み83/311、未作成228件。
SINGLE-055/056はcommandを実行し、SINGLE-060/061/062/067はspawnの前に停止する。
verifyはindexで未追跡の設定があると起動を遮断するため、Context fixtureと異なり入力をstageする。verifyには
`--base`がないので基準commitは使えず、repositoryはindexに内容を持つunbornのままで、revisionはnullである。
監査は全caseでindexを読み戻す。
SINGLE-055はSINGLE-042がcommitしたDigestを返す。監査は、Contextが解決した場合に限りtargetのDigestがあること、
bindingRefsとcommands[]が同じ実行を表すことを強制する。Diagnosticの置き場所はregistryの継続単位に従い、
skip-targetの条件はtargetに、stop-operationの対象0件の条件は最上位に置く。
期待値の選択と限界は[verifyのreview](single/verify実行・事前ブロックreview.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のverify bindingの回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み86/311、未作成225件。
SINGLE-063とSINGLE-064は、2つのtargetが1つのcommand名を要求するよう、起点を2つ持つworkspaceを使う。
各targetは固有のDigestを返し、1つのcommand実体が重複排除した共有test pathを1回だけ実行する。
SINGLE-064はblockedのtargetをbindingRefs []に保ち、その規範文を実行したcommandのcoversから除く。SINGLE-065は、
{tests}のないcommand templateを1回だけ実行し、pathを渡さないことを固定する。workspaceは独立した起点を
複数持ち得るので、参照計算Bの強いedgeの検査は、計算中の閉包に触れるedgeにだけ働くようにした。
SINGLE-066とSINGLE-068は専用の段階へ保留した。どちらも、この参照計算がまだ導出しない閉包の挙動を必要とする。
期待値の選択と限界は[verify bindingのreview](single/verify-binding-review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のverify processの回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み89/311、未作成222件。
SINGLE-057、058、059はいずれも事前検査の通過後に失敗するので、bindingRefsを保ったまま、nullの終了コードと
error statusを持つcommands[]の要素を記録する。Diagnosticはregistryのskip-bindingの分類どおり、environmentの
sourceで最上位に置く。
監査は各fixture自身のcommand fileを、Coreを介さず直接実行し、入力がreview済みの原因を今も再現することを確認する。
これによりfixture自身の欠陥を2件見つけた。最初のhang scriptは前景のsleepが終了されるとprocess groupへの
SIGTERMで終了してしまい、監査はshellがtrapを設定する前にsignalを送っていた。現在のscriptは前景のsleepが
終了されても続行し、pipeを保持する子processはTERMを無視し、trapの設定後に準備完了の行を出力する。監査はその行を待つ。
この準備完了の行はSINGLE-059の期待するstdoutExcerptでもあり、来ないEOFを待たずにstreamを読み切って
read handleを閉じた場合にだけ現れる。
期待値の選択と限界は[verify processのreview](single/verify-process終了review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のverify出力・文書単位bindingの回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み92/311、未作成219件。
SINGLE-069-01/02は、64 byteの行から成る70,400 byteのstreamを固定し、最初と最後の行に異なる目印を置く。
これにより、commitした64 KiBの抜粋が末尾の目印を含み先頭の目印を含まないことを証明できる。監査はcommand fileを
実行し、生成された末尾をbyte単位で比べる。scriptの本文はDigest材料ではないので、終了コードが異なっても
両者は1つのContext Digestを共有する。
SINGLE-066は、規範文を持たず文書単位のtestを持つTECHをtargetにし、statements []、bindingRefsの要素、
covers [TECH-001]を返す。Frontmatterの契約は、このようなTECHに限ってこれを許す。
SINGLE-068は意図してまだ作らない。起点TASKが`addresses`する参照先を所有する文書がverifyのContextに含まれるかを、
規範文書が決めておらず、契約より先にfixtureを実行対象へ入れてはならないためである。期待値の選択、理由、
報告した欠落は[verify出力のreview](single/verify出力・文書単位binding-review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のdone TASK起点の回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み93/311、未作成218件。
これでmatrix §6.6のverify、全16行が完了する。
SINGLE-068には先に契約の確定が必要だった。関係・トレースモデル §6.3は現在、起点TASKが`addresses`する参照先と
その所有文書をcontextDocumentsへ含め、その文書からinterpretの閉包規則を適用し、implementと異なり起点TASKの
requires閉包を含めないと定める。
決定は変えていない。target展開の参照計算は既にこの読みを実装しており、25ケースの期待集合は変わらない
（2026-09-17訂正: 実際には参照計算がverifyでも起点TASKのrequiresをたどっており、後に1ケースを修正した）。
解決できない`addresses`の参照先は既存のSPEC-RELATION-MISSING-001になるので、Diagnosticの条件も追加しない。
監査は、diagnostic-coverage.jsonとtargets/cases.jsonが固定する根拠文書hashによってこの編集を自分で検出し、
hashはDiagnostic意味網羅review.mdに再reviewを記録した後にだけ更新した。
このfixtureはSINGLE-067と対になる。doneの起点は固有のDigestとbindingで再検証でき、cancelledの起点はどちらも持たず
blockedになる。AC-02は意図して`addresses`せず、その規範文もtestもbindingへ入れない。期待値の選択と限界は
[done TASK起点のreview](single/done-TASK起点review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のreport非作成・引数不正の回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み102/311、未作成209件。
SINGLE-070-01/02/03/04は、`--report`なしで両操作の両結果を扱う。各入力は既に.spec/reports/existing.jsonを持つ。
これがない入力では、新しいfileを作らないことしか示せず、既存のreportが残ることを示せないためである。監査は
snapshotにこのfileがないfixtureを拒否する。
追加したreport fileはSPECの材料ではなくContextも変わらないので、verifyの2件はSINGLE-055とSINGLE-056の
review済みの結果を直接使う。
SINGLE-073-01/02とSINGLE-074-01/02/03はstatusも結果fileも持たない。manifestの契約は、共通結果がない場合にだけ
これを許す。SINGLE-074-03は、IDの不在ではなく字句のIDの誤りであり、CLI契約はこれをCTX-ROOT-MISSING-001と区別する。
標準エラー出力の契約はcheckに固定されていたが、操作を区別するように改め、5件と以前のGit環境の1件が1つの契約を
共有する。監査は操作ごとにこれを動かし、誤った接頭辞、空の理由、2行目、4以外の終了コードを拒否する。
期待値の選択と限界は[report非作成のreview](single/report非作成・引数不正review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14の明示reportの回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み107/311、未作成204件。
side-effects.schema.jsonは、report objectを伴うpolicy explicit-reportを受け付けるようになり、Schemaは
explicit-reportにreportを必須とし、read-onlyにはこれを禁止する。report file名は共通normalizerが除外する
生成時刻と連番を含むので、beforeとafterは既存のpathだけを記述し（すべて不変でなければならない）、
report objectが差分を持つ。
監査は、commitした名前のpatternが正しい形式の名前を受理し、時刻の欠落、0の連番、他の操作、残った.tmp接尾辞を
拒否することを要求する。
空のdirectoryへの作成では排他的な作成と置換を区別できないので、各SINGLE-071-*の入力は既存のreportを持つ。
reportを保存しても計算済みの結果は変わらないので、4件はSINGLE-070-*の組のreview済みの結果を使う。
SINGLE-072は、「元の結果が残る」ことが空疎にならないよう、成功ではなく失敗するcheckに基づく。結果の本体は変わらず、
SPEC-RELATION-MISSING-001が残り、SPEC-REPORT-WRITE-001が追加され、statusがfailedからerrorへ上がる。
Gitはdirectoryの権限を記録せずfresh checkoutで復元されないため、保存先はdirectoryの権限ではなく
.spec/reportsに置いた通常fileで塞ぐ。
期待値の選択と限界は[明示reportのreview](single/明示report-review.md)に記録した。
これらは準備の検査であり、観測したCoreの挙動や、fresh checkoutでのGate Aの完全な認定ではない。

続く2026-09-14のCLI引数境界の回は、統合検査と回帰試験を通過した。
固定した環境での`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み116/311、未作成195件。
SINGLE-127-01/02/05/06/07/08/09/10/11は、optionの重複、空の引数、contextの起点の欠落、timeoutの境界・表記、
任意のreport pathの構文を扱う。9件とも結果の本体とreportなしで終了コード4を返す。固定した実行前後のsnapshotは、
repositoryと隔離したHOME／cache／TMPDIRへの書込みを禁じ、Gitのstatus／indexを保つ。各setupを2回再現した。
改変試験は、不正な引数の削除、妥当なtimeout値への置換え、新しいout.jsonのpathを拒否する。操作を区別する既存の
標準エラー出力の検査は、CLIの14件すべてで共有する。
期待値の選択と限界は[CLI引数境界のreview](single/CLI引数境界review.md)に記録した。
host: Linux 6.18.33.2-microsoft-standard-WSL2、x86_64、CPython 3.14.4、Git 2.53.0。
validatorの依存は入口のscriptで固定したままである。
これらは準備の検査であり、観測したCoreの挙動、CPython 3.11での受入、fresh checkoutでのGate Aの完全な認定ではない。
複合workspaceのgolden Digestと、残りのfixtureの証拠は未完了である。

続く2026-09-14のexpand反復の回は、統合検査と回帰試験を通過した。
1回目は`uv run fixtures/validate_step0b.py`、2回目はcacheした同じ固定環境のPythonを`-B`付きで直接起動した。
監査reportの2件はbyte一致し、check errorはなく、未完了のGate Aの証拠によってだけ終了コード1だった。
準備済み118/311、未作成193件。
SINGLE-127-03はTECH-001、REQ-001の順に与えて整列したexpand IDを期待し、SINGLE-127-04はTECH-001を反復して
IDを1件だけ期待する。完全な結果の本体は、goldenのresolution、coverage、Digestを保つ。
独立した2系統の参照計算がcommitしたCanonical JSONと一致し、fixtureごとの隔離した2回のsetupが固定した
読取り専用snapshotと一致する。改変試験は、整列していない・重複したexpand IDと、反復したoptionの欠落を拒否する。
[expand反復のreview](single/expand反復review.md)を参照。
validatorの実行環境: CPython 3.14.6。jsonschema 4.23.0、attrs 26.1.0、jsonschema-specifications 2025.9.1、
referencing 0.37.0、rpds-py 2026.6.3、typing-extensions 4.13.2。Linux／WSL2、Git 2.53.0。
Coreは実行していない。fresh checkoutでのGate Aの全体検査、残りのfixtureの証拠、複合workspaceのgolden Digestは未完了である。

続く2026-09-14の起点・workspace不存在の回は、統合検査と回帰試験を通過した。
cacheした固定のvalidatorのPythonによる`-B`付きのfixtures/validate_step0b.pyの2回はbyte一致したreportを出し、
check errorはなく、未完了のGate Aの証拠により終了コード1だった。
準備済み120/311、未作成191件。新しいfixtureはそれぞれ隔離した2回のsetupの比較を通過した。
SINGLE-127-13は要求した不在の起点を保ち、不完全で空のContextとCTX-ROOT-MISSING-001を伴うfailed／1を返す。
SINGLE-127-14は、構文上妥当だが存在しないworkspaceを選び、共通結果なしで終了コード4を返す。改変試験は、
workspaceのrootへの変更、終了コードとstatusの契約の混同、失敗したContextの完全化、Diagnosticのsourceの変更を拒否する。
入力と期待値の選択は[起点・workspace不存在のreview](single/起点・workspace不存在review.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
Coreは実行していない。残りのfixture、複合workspaceのgolden Digest、fresh checkoutでのGate Aの全体の再現性は
未完了であり、これらの実行は準備だけを保証する。

続く2026-09-14の出力形式の回は、統合検査と回帰試験を通過した。
cacheした固定のvalidatorのPythonによる`-B`付きのfixtures/validate_step0b.pyの2回はbyte一致したreportを出し、
check errorはなく、未完了のGate Aの証拠により終了コード1だった。
準備済み123/311、未作成188件。新しいfixtureはそれぞれ隔離した2回のsetupの比較を通過した。
SINGLE-075-01/02は、text出力を選びつつ対応する完全なJSONを保つ。固定したUTF-8のtextはstatus、scope、文書数、
Diagnostic数を保ち、sourceの行・列がないfieldは空のままにする。所要時間だけのbyte正規化は、status・件数・空白・
改行の変更、ASCII以外の数字、小数の所要時間表記を拒否する。改変試験は、変えたJSON、textの件数、副作用の期待値を
拒否する。SINGLE-127-12は`--format json`と`--report`を明示的に組み合わせ、既存のfileを保ち、一時fileを残さずに
ちょうど1件のreportを許す。
期待値の選択と限界は[出力形式のreview](single/出力形式review.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
Coreは実行していない。実際のtextの描画、reportの内容、副作用はGate Bの作業である。
残りのfixture、複合workspaceのgolden Digest、fresh checkoutでのGate Aの全体の再現性は未完了である。

続く2026-09-14のBOM・Frontmatterの回は、統合検査と回帰試験を通過した。
cacheした固定のvalidatorのPythonによる`-B`付きの2回はbyte一致した監査reportを出し、check errorはなく、
未完了のGate Aの証拠により終了コード1だった。準備済み134/311、未作成177件。
SINGLE-081/082/084/085は、1件の警告の後、検査した文書と規範文を1件ずつ数えて続行する。
SINGLE-086/087-01〜05/088は、Schema Diagnosticを1件出して形式不正の文書をskipし、件数を0にする。
各fixtureは隔離した2回のsetupの比較を通過した。改変試験は、修復した入力byte列、誤った件数・status・code、
削除または重複したDiagnostic、新しいcacheへの副作用を拒否する。
入力と期待値の選択は[BOM・Frontmatterのreview](single/BOM・Frontmatter-review.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
YAML loaderもCoreも実装・実行していない。実際の続行、拒否、副作用はGate Bの作業である。
残りのfixture、複合workspaceのgolden Digest、fresh checkoutでのGate Aは未完了である。

Diagnostic制御文字の回は、固定したCPython 3.14.6環境で、byte一致した統合監査を2回通過した。
check errorはすべて空で、終了コード1は未完了のGate Aの証拠を表す。準備済み135/311、未作成176件。
SINGLE-076は、renameで作った制御文字を含むpathで、隔離した2回のsetupを通過した。
承認済みのfieldのescape規則を結果契約へ追加した。JSONは元のfield値を保ち、textだけが小文字4桁のescapeを使う。
回帰試験はC0／DEL／C1の全範囲、LF／TAB、隣接する可視文字、literalのbackslashを扱う。Diagnosticの意味上の
条件は変わらず、review済みの根拠文書hashを更新した。範囲と証拠は端末制御文字のreviewを参照。
Coreは実行していない。残りのfixtureの証拠、複合workspaceのgolden、fresh checkoutでのGate Aは未完了である。

SINGLE-077は、固定したCPython 3.14.6環境で、byte一致した統合監査を2回通過した。
check errorはすべて空で、終了コード1は未完了のGate Aの証拠を表す。準備済み136/311、未作成175件。
3件のTECH文書が、それぞれ独立に不在のTECH-999を参照する。JSONとtextは3件のDiagnosticをpath順にすべて保ち、
5文書と2規範文をすべて数える。隔離した2回のsetupは固定したsnapshotと一致する。
回帰試験は、逆順や欠落したDiagnosticと、減らした文書数を拒否する。範囲はDiagnostic順序のreviewを参照。
Coreの実行、残りのfixture、複合workspaceのgolden、Gate Aの全体は未完了である。

入力上限の回は、固定したCPython 3.14.6環境で、byte一致した統合監査を2回通過した。
check errorはすべて空で、終了コード1は未完了のGate Aの証拠を表す。準備済み143/311、未作成168件。
SINGLE-078/079-01/079-02は、他の次元を上限内に保ったまま、64 KiBの設定、1 MiBのSPEC Markdown、
32 KiBのFrontmatterの上限をそれぞれ越える。SINGLE-080-01は規範文1,000件とcovers 1,000件をちょうど満たして
成功のまま残り、080-02は規範文を1件、080-03はcoversを1件加える。追加の参照が解決するよう、規範文1件の
2つ目のREQで支える。SINGLE-083は、SPECでないfileを1件`.spec/`直下に置く。監査は生成したbyte数を測り直し、
他の次元を越えるfixtureを拒否する。
fixtureごとに隔離した2回のsetupが固定したsnapshotと一致する。回帰試験は、変えた件数、code、severity、source、
key、副作用と、上限の反対側へ移した入力を拒否する。
範囲と証拠は[入力上限のreview](single/上限・未知entry-review.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
上限の検査もCoreも実装・実行していない。実際の継続単位と件数はGate Bの作業である。
残りのfixture、複合workspaceのgolden Digest、fresh checkoutでのGate Aの全体の再現性は未完了である。

registry閉包の回はmatrix §6.9を完了し、固定したCPython 3.14.6環境で、byte一致した統合監査を2回通過した。
check errorはすべて空で、終了コード1は未完了のGate Aの証拠を表す。準備済み150/311、未作成161件。
SINGLE-089は、理由のないSHOULDの1始まりのコードポイント位置を固定し、文書を数えたまま残す。SINGLE-090は、
不在の参照先へのadvisoryな関係だけを持つ。SINGLE-091は、最小の設定とanchor 1つだけが異なる。SINGLE-092は、
review済みの型誤りの設定をdoctorで再利用し、実行したcheck 4件とともに共通の設定codeを返す。
SINGLE-093は、SINGLE-001とGit不在だけが異なり、nullのGit snapshotを持つ。doctorの契約には`lostGuarantees`の
4つの名前を固定し、review済みの根拠文書hashを更新した。
SINGLE-094はdoctor専用のcodeではなくcheckのworkspace不在の条件を返し、SINGLE-095は最小の設定とEARS-AIの
majorだけが異なる。fixtureごとに隔離した2回のsetupが固定したsnapshotと一致する。回帰試験は、変えた位置、
severity、workspaceの同一性、doctorのcheck status、失われる保証、code、副作用と、修復した入力、追加した
workspaceを拒否する。
範囲と証拠は[registry閉包のreview](single/registry閉包review.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
YAML loader、Gitの調査、doctorの手順、Coreのいずれも実装・実行していない。実際のcheckの続行とdoctorの出力は
Gate Bの作業である。残りのfixture、複合workspaceのgolden Digest、fresh checkoutでのGate Aの全体の再現性は未完了である。

Scanner・位置の回は、固定したCPython 3.14.6環境で、byte一致した統合監査を2回通過した。
check errorはすべて空で、終了コード1は未完了のGate Aの証拠を表す。準備済み166/311、未作成145件。
§6.10のcheck fixture 16件は、review済みのEARS文書を保ち、16行目だけを置き換える。
各Diagnosticの列は、multi-byte文字とTABのcaseを含め、固定したbyte列から1始まりのコードポイントの位置として
導き直す。原因を共有する2件はregistryの優先順位によるprimaryを固定し、抑止の4件は、同じ規範文風のtextを
backtickのfence、tildeのfence、引用、4 spaceのindentで囲む。失敗するcaseは文書も規範文も0件と数え、抑止のcaseは
15行目の妥当な規範文1件を数える。fixtureごとに隔離した2回のsetupが固定したsnapshotと一致する。回帰試験は、
ずらした列、変えた件数とcode、重複したDiagnostic、欠落した位置field、副作用、置き換えた規範文、囲みを外した構文を
拒否する。§6.10の`context`の4件は、完全なSemantic IRとDigestの比較を必要とするため未作成のままとした。
範囲と証拠は[Scannerのreview](single/Scanner・位置review.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
Scanner、Lexer、Parser、Coreのいずれも実装・実行していない。実際の候補抽出と出力する位置はGate Bの作業である。
残りのfixture、複合workspaceのgolden Digest、fresh checkoutでのGate Aの全体の再現性は未完了である。

既定表示の回は、固定したCPython 3.14.6環境で、byte一致した統合監査を2回通過した。
check errorはすべて空で、終了コード1は未完了のGate Aの証拠を表す。準備済み173/311、未作成138件。
SINGLE-104-02/03/04は`--format`を省略し、check、verify、doctorのtextの要約行を固定する。監査は、公開した
導出手順で対応するJSONから操作、status、targets、diagnosticsを導き直し、scope=を含むdoctorの行を拒否する。
SINGLE-105-01はgoldenのcontextの入力に基準commitを加え、現在のrevisionを固定する。実際の40桁の小文字commit、
cleanな作業tree、操作ごとのrevisionの形を、各隔離setupで観測する。SINGLE-105-02はGitを完全に除き、revisionと
Git snapshotをnullに保つ。SINGLE-106-04は、切り詰めの入力を、0で終了し何も書かないことを観測した無出力の
scriptで再利用し、空の抜粋と、両方falseの切り詰めflagを固定する。SINGLE-106-05は、2つのtargetで同じ起点不在の
条件を返し、textの要約で両方を数える。textの契約には、file以外のDiagnostic行はpath、行、列を空にすることを明記し、
review済みの根拠文書hashを更新した。contextとverifyには基準版のoptionがないので、commit済みfixtureの`--base`の
規則はcheckだけに適用するようにした。
範囲と証拠は[既定表示のreview](single/既定表示・revision-review.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
描画処理、Gitの読取り、Coreのいずれも実装・実行していない。Markdownのbyte一致（SINGLE-104-01）とprojectionの
fixture 3件は、残りのContextとDigestの作業とともに未作成である。

SINGLE-104-01は、固定したCPython 3.14.6環境で、byte一致した統合監査を2回通過した。
check errorはすべて空で、終了コード1は未完了のGate Aの証拠を表す。準備済み174/311、未作成137件。
Markdownの提示はsectionの順序以外が未定義だったため、提案26で描画全体を決め、現在はcontext仕様 §9が持つ。
review済みの根拠文書hashを更新した。`markdown_reference.py`はその契約をfixture側で計算する参照計算であり、
commitしたBundleはその出力とbyte単位で一致しなければならない。監査はさらに、変えたsectionの順序、変更した・
fenceで囲まない本文、内部の最長runより長くないfence、2つ目のH1、所要時間のtokenを拒否する。goldenの
contextの入力は変わらないので、DigestとJSONはSINGLE-042と同一のままである。
決めた論点は[Markdown提示の提案](../../docs/04.提案資料/26_context-Markdown提示仕様案.md)を参照。
実行環境は上に記録したのと同じ固定のCPython 3.14.6のvalidator環境、Linux／WSL2、Git 2.53.0。
Coreの描画処理は実装・実行していない。§6.11のprojectionのfixture 3件と、§6.10の`context`の4件は、残りの
Digestの入力の作業とともに未作成である。

## 2026-09-17: reason、full projection、Digestのversion

SINGLE-101-01、SINGLE-106-01、SINGLE-121を追加した。準備済み177/311、未作成134件。
`uv run fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはすべて空だった。
両方とも、未完了のGate Aの証拠だけを理由に終了コード1を返した。
Report SHA-256: `49554c146d9e524c0310e4700806c912ef10388cb595018284936033dd7c784e`。
既存の固定したuv環境と依存を使い、実行環境は変えていない。
新しいfixtureはそれぞれ、完全な入力、manifest、期待結果、Canonical JSON、読取り専用snapshotを持つ。
隔離した2回のsetupと、独立した2系統のDigest参照計算が一致する。改変試験は、reasonの欠落、fullのprojectionの
禁止field・必須fieldの欠落、変えたdigestVersion／resolverVersionを拒否する。
[Digestのreview](single/Context-Digest-review.md)を参照。Coreは実行していない。
normative／referenceのprojection、残りのScannerのContextのcase、複合workspaceのgolden、fresh checkoutでのGate Aの
全体の証拠は未完了である。

## 2026-09-17: 内部Parserの証拠とnormative projection

準備済み179/311、未作成132件。SINGLE-097-01とSINGLE-106-02を追加し、SINGLE-101-01に内部Parserの完全なIRの
期待値を加えた。
固定した環境での`python -B fixtures/validate_step0b.py`の2回はbyte一致したreportを出し、check errorはなく、
両方とも未完了のGate Aの証拠により終了コード1だった。
Report SHA-256: `145b9efd0b02033a4f5d9b3148ec6a4f8a5c5e7da9606c5414a4f98669a99027`。
実行環境: 既存のCPython 3.14.6のStep 0Bのuv環境、Linux／POSIX。依存の固定は変えていない。
textの5種類のescapeと、source・raw・意味のfieldが、固定した完全なIRの期待値と一致する。
距離2のrefinementで、normative projectionのfield省略を検査する。
入力、完全なJSON、Canonical JSON、snapshotを固定し、隔離した2回のsetupと、独立した2系統のDigest計算が一致する。
改変試験は、意味のfield、sourceの位置、raw、projectionのfieldと、欠落・安全でない・重複したParserの参照を扱う。
受け入れた分担は適合fixture仕様 §4.1に定めた。Step 2では実際のParserの完全なIRを比べ、公開のcontextの受入は
引き続きJSONとDigestを比べる。
CoreのParserも操作も実装・実行していない。code spanとquoted extensionの期待値は意味の決定待ちであり、
reference projection、複合workspaceのgolden、他の未作成fixture、fresh checkoutでのGate A認定も未完了である。

## 2026-09-17: quoted extensionの受入

準備済み180/311、未作成131件。SINGLE-098-01は、quality extensionでescapeしたDQUOTEを固定し、明示的に承認された
passed_with_warningsとする。既存の固定したCPython 3.14.6環境での`python -B fixtures/validate_step0b.py`による
統合実行2回はbyte一致したreportを出し、check errorはすべて空だった。
Report SHA-256: `edecc666b3ad04a7da27816272fbd398de2a242027511d9d19d2888668df4d07`。
両方とも未完了のGate Aの証拠により終了コード1だった。完全なIR、source、opaque／未知のextensionの値、公開結果、
Canonical JSON、読取り専用snapshotを検査する。
Coreは実行していない。code span、reference projection、複合workspaceのgolden、残りのfixture、fresh checkoutでの
認定は未完了である。

## 2026-09-17: code spanの受入

準備済み181/311、未作成130件。SINGLE-096-01でmatrix §6.10の20件が完了する。
承認済みの意味は、外側の区切りだけを除くことである。長さの異なる内部のrunと、span内部のtag・escape風のtextは
literalのまま残す。完全なIR、raw／source、JSON、Canonical JSONを固定する。独立した2系統の参照計算と、隔離した
2回のsetupが一致する。同じ長さのrunでの終了と、形式不正のrunの回帰試験が通過した。
同じ固定したCPython 3.14.6環境での統合実行2回はbyte一致し、check errorはなく、両方とも未完了のGate Aの証拠により
終了コード1だった。
Report SHA-256: `e4c52beaeb441737c9a8f96f18e4d59b1f9a4bc766f738c60238685d78f272ca`。
Coreは実行していない。reference projection、残りのfixture、複合workspaceのgolden、fresh checkoutでのGate A認定は
未完了である。

## 2026-09-17: Frontmatter境界

準備済み201/311、残り110件。SINGLE-114、115-01〜04、116-01〜05、117-01〜03、118-01、119-01〜04、
120-03、120-04で、REQ／TECH／ADR／TASKの最小definition、titleの120／121 code point境界、空白・複数行・null・
欠落のtitle、空・重複配列、未知key、`x-`拡張、REQの`changes`の優先順位を固定した。
独立にdecodeしたflow valueはreview済みfieldおよびFrontmatter Schemaの判定と一致した。2回の隔離setupは
読取り専用snapshotと一致した。回帰試験はstatus・件数・codeの改変、二重または削除した診断、cache書込み、
境界内へ修復した121 code point titleを拒否する。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `db8b0defde675722225f72962027265855afbe953971a3379b4bbba0a3e39582`。
Coreは実行していない。SINGLE-118-02／03、120-01／02、残りの適合fixture、複合workspaceのgolden、fresh checkoutでの
Gate A認定は未完了である。

## 2026-09-17: Frontmatter境界の追補

準備済み205/311、残り106件。SINGLE-118-02、118-03、120-01、120-02を加え、matrixの114〜120を完了した。
118-02／03は`tests`要素を`(path, commandの有無と値, covers集合)`のkey tupleで独立に比較し、
JSON Schemaの`uniqueItems`では検出できないcovers順だけの重複を拒否、command／coversの異なる要素を受理する。
120-01／02は明示TASK checkで、`changes: []`かつ差分なしの通過と、`changes`省略かつ未stage差分の
`SPEC-TASK-BOUNDARY-001`を固定した。HEAD／indexのblobと作業treeのbyteを2回の隔離setupで照合した。
回帰試験は受理への改変、covers順の修復、件数・source・argvの改変、差分の消去とstageの追加を拒否する。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `0fff1aa3a4d4ca4b2bbc3e21ac59549a39bc0b5f516ee2cf8a3eaa72ca155bc0`。
Coreは実行していない。残りの適合fixture、複合workspaceのgolden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: Core副作用

準備済み210/311、残り101件。SINGLE-125-01〜05を追加した。source fixture（042、001、070-01、055、071-01）と
同じ起動・入力を使い、期待結果fileはsourceとbyte一致させた。125-01〜04は`.spec/reports/`を置かない読取り専用、
HOME／cache／tempは空で固定し、125-04は書込みなしcommand `/bin/true`に限定した。125-05は最終report 1件、
一時file残存0件、既存report不変を要求する。各fixtureを2回の隔離setupで照合した。
回帰試験は書込み許容、外部treeの事前汚染、report要求・件数・policyの改変、追加環境変数、
report directoryの追加、書込みcommandへの置換を拒否する。
SINGLE-125-06は、時刻固定も障害注入もできないfixture形式では、SINGLE-072と異なる排他的作成失敗を
決定論的に起こせないため保留した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `09eb848bfd50680e20ed3fa13eb6f0c4b860281810957f182eff436b8b23e457`。
Coreは実行していない。SINGLE-125-06、残りの適合fixture、複合workspaceのgolden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: report directoryのsymlink（SINGLE-125-06）

準備済み211/311、残り100件。`.spec`または`.spec/reports`がsymlinkなら解決せず保存失敗とする規定を
結果・Diagnostic・終了コード §8へ、`.spec/reports`をentry種別にかかわらず既知entryとする規定を
workspace・設定仕様 §3へ追加し、registryの`REPORT-WRITE`行へ注記した。新規条件はなく、
Diagnostic台帳は3文書のhashだけを再review後に更新した。
SINGLE-125-06はSINGLE-072と同じ起動・期待結果で、`.spec/reports`を`../report-store`へのsymlinkに替えた。
symlink、symlink先directory、既存reportの不変を読取り専用snapshotで固定し、2回の隔離setupで照合した。
監査の`copy_fixture`はsymlinkをsymlinkのままcopyするよう修正した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `6ba25afc010d4f839244d4a2f26f3488703d62d67c8f3e70a2209531e3311b81`。
Coreは実行していない。残りの適合fixture、複合workspaceのgolden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: verify argv・実行環境・出力変換

準備済み225/311、残り86件。SINGLE-126-01〜05、07、09〜16を追加した。
126-01〜05は設定のflow配列を独立にdecodeし、argv template規則の違反がちょうど1件であることを確認した。
126-07、10、11はfixture自身のscriptを直接起動し、期待入力でだけ成功することを観測した。126-11は
POSIX shが`PWD`を再計算するため、awkで環境を読む。126-12は別sessionの子孫が直接process終了後も
5秒以上pipeを保持することを、126-13はSINGLE-059と同じhang観測と後続`/bin/true`の成功を観測した。
126-14〜16はraw出力から独立の参照変換（制御文字、redaction、code point境界の末尾保持）で期待抜粋を再計算した。
各fixtureを2回の隔離setupで照合し、Context Digestは2系統のreferenceで一致した。
126-06は`bitz.yaml`の64 KiB上限により`SPEC-CONFIG-SCHEMA-001`へ到達できないため、126-08はfixture規模のため保留した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `242dd2b0bce32f6e233c849292e3d1d56e00296f5521f3b6285b84a5f5e7c8fd`。
Coreは実行していない。126-06、126-08、残りの適合fixture、複合workspaceのgolden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: argv上限の裁定とSINGLE-126-08

準備済み226/310、残り84件。SINGLE-126-06は`bitz.yaml`の64 KiB上限により`SPEC-CONFIG-SCHEMA-001`へ到達できないため、
裁定でmatrixから削除し、workspace・設定仕様 §6へ注記した。Diagnostic台帳は同文書のhashだけを再review後に更新した。
SINGLE-126-08は規範文なしTECH 35文書、test path 280件（各約3,770 byte）で、引数なしverifyの展開後argvが
1,055,609 byteとなりbyte上限だけを超える。設定・Frontmatter・文書・要素数・要素長・path長が上限内であること、
1文書分を除くと上限内へ戻ることを独立に確認した。35 targetのContext Digestは2系統のreferenceで一致した。
fixtureは入力と副作用snapshotで約9 MiBである。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `f40dbfc6f38683207e31d53e7fde47d33232b708791a994b51dd980f1ebd8206`。
Coreは実行していない。残りの適合fixture、複合workspaceのgolden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: 明示起点の不在・ADR起点、共通target展開、Digest材料の順序

準備済み245/310、残り65件。SINGLE-106-03、107-01／02、108-01／02、109、110、111-01〜04、112-01〜04、113、
122〜124の19件を追加した。作成前に、role割当、interpretのdraft refinement、statement起点の提示、
verifyの起点TASKの`requires`を裁定して正本へ反映し、Diagnostic台帳とtarget vectorの根拠hashを再review後に更新した。
target vectorは`TASK-REQUIRES-NOT-TARGET`の期待集合だけが変わり、他の24 caseは不変である。
reference B（`digest_crosscheck.py`）を`requires`の追跡、statementへの`refines`、draft advisory、
command省略時の文書`verify`解決、extensionの正規順へ拡張し、既存fixtureのCanonical JSONが不変であることを確認した。
新規のContext Digestはすべて2系統のreferenceで一致した。各fixtureを2回の隔離setupで照合した。
SINGLE-127-15〜19は、偽Gitの配置、`consumer` runnerのargv、CPython 3.11の選択が未確定のため保留した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `23f787eb283aa4fe0f877ac020ceb070fa6b116282a2046bbd1cd079eca47c8c`。
Coreは実行していない。SINGLE-127-15〜19、複合workspaceのfixture、複合workspaceのgolden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: 適合harness外部仕様の裁定と実行環境・配布物

準備済み250/310、残り60件（すべて複合workspace）。提案27とADR-046で、検査対象の受取り（source／wheelと`uv`隔離環境）、
`invocation.python`、`invocation.gitVersion`とGit shim、`bitz.compat`によるconsumer／migration runner、
harness側の`runner: package`を裁定し、適合fixture仕様、実行環境契約 §4（`git --version`による版取得）、
実装計画のGate C（全matrixを3.11と基準環境で通す）、manifest Schemaへ反映した。
Diagnostic台帳は実行環境契約のhashだけを再review後に更新した。
SINGLE-127-15〜19を追加し、Git版と下限CPythonを規範本文から読み取ってmanifestと照合した。
統合検証へ、bitz以外のrunnerの期待結果が`{"outcome": ...}`だけであることの検査を加えた。
各fixtureを2回の隔離setupで照合した。shim生成、`uv`環境構築、package検査の実行部は未作成である。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `08eda7ecd76069a296e42d1a429a81f22cccfcb16a1f529cdf5de790b3fdaba8`。
Coreは実行していない。複合workspaceのfixture、複合workspaceのgolden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: 複合workspaceの識別子の改名

準備済み250/310、残り60件（すべて複合workspace）。ADR-047に従い、設定key、Capability、結果field、Diagnostic code、
condition ID、継続単位、fixture ID（`MONO-*`→`MULTI-*`）、結果SchemaのSchema定義名、性能datasetを改名した。
doctorの期待結果11件はCapability一覧の`multiWorkspace.v1`だけが変わり、manifest Schemaとmatrix検査は
`MULTI-*`を受け付ける。Diagnostic台帳とtarget vectorの根拠文書hashは再review後に更新した。
target vectorの期待集合25 caseは変わらない。性能datasetの期待tree digestは設定keyの変更分だけ更新した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `fb0d2efe0a442145d47e47be364a80d45849c0d0af187f4c57769db1ca15e5f5`。
Coreは実行していない。複合workspaceのfixture、そのgolden Digest、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: file名の改名

用語集 §7に従い78件のfile名を改名し、参照322箇所、ADR 16件の`title`とH1、台帳の根拠文書keyを直した。
提案資料とfixtureの記録を含む全Markdownでlinkを検査し、link切れは改名前と同じ107件（置換済みの旧ADRが
旧構成の文書を指すもの）で、改名による増加はない。台帳とtarget vectorの根拠文書hashは再review後に更新した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `fb0d2efe0a442145d47e47be364a80d45849c0d0af187f4c57769db1ca15e5f5`（改名前と同じ）。

## 2026-09-17: 文言の統一

用語集 §2に従い、設計書・ADR、詳細設計、提案資料、fixtureの記録の本文を統一し、英文の記録を翻訳した。
Pythonは43 fileのコメント、docstring、検査の失敗文言を日本語にし、JSON Schemaの`title`と`description`も日本語にした。
fixtureの入力byte列（`tests/test_contract.py`などに書く`RuntimeError`の文言）、期待出力、Gitの状態、
validator reportの値（`pending`の文言を含む）は英語のまま残した。文言を照合する監査試験と、
`validate_step0p.py`の形状不一致の照合は、新しい文言に合わせて直した。台帳とtarget vectorの根拠文書hashは再review後に更新した。
監査試験145件と基盤の自己試験3件は成功した。link切れは統一前と同じ107件である。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `fb0d2efe0a442145d47e47be364a80d45849c0d0af187f4c57769db1ca15e5f5`（統一前と同じ）。
Coreは実行していない。複合workspaceのfixture、そのgolden Digest、fresh checkoutでのGate A認定は未完了である。

## 2026-09-18: federationの残りの言換え

結果契約の表の種別名と複合workspace仕様の注記に残っていた「federation」を、用語集 §4.7に従って
単一workspace、複合workspace内、workspace単独、複合workspace全体、root workspace IDへ改めた。
性能generatorの内部関数名`federation_model`も`multi_workspace_model`へ改めた。台帳の根拠文書hashは再review後に更新した。
監査試験の子processの時間上限は、試験145件の所要21秒に対し30秒では余裕がないため180秒へ広げた。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `fb0d2efe0a442145d47e47be364a80d45849c0d0af187f4c57769db1ca15e5f5`（変更前と同じ）。

## 2026-09-18: 複合workspaceのgolden Digestと修飾IDの解決

準備済み258/310、残り52件（すべて複合workspace）。root workspace `platform`とmember `web`／`api`からなる
固定corpusを作り、`MULTI-002-01`が複合workspaceのgolden Context Digestを所有する。
Digest材料は、review済みliteralによる参照計算A（`multi_reference`）と、入力treeから導出する参照計算B
（`multi_crosscheck`）で照合し、2回の隔離setupでもbyte一致した。
golden: `sha256:72661dba40f08eb57cc1a57fe36d9a60f67df24826b4ebfdbbd8afb77c6f1fd3`。
`MULTI-002-02`は同じ材料をverifyの側から固定し、targetのDigestがgoldenとbyte一致することを要求する。
`MULTI-001`／`003`／`004-01/02`／`025-01/02`は、同じcorpusの3変種で修飾IDの4つの結末を1件ずつ切り分けた。
各変種が原因を1つだけ持つことは、散文ではなく入力から確かめる。監査試験を7件追加し、
材料の並び、workspace IDの付け替え、codeの取り違え、終了コード4への置換、入力への2つ目の原因を拒否することを確認した。
統合検証のpendingから複合workspaceのgolden Digestが外れ、fixture未作成の残りは52件になった。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `a5ec6d0027188193a43a71bd5f231fc50cd3661bd07b8fd9e1d72414c600869b`。
Coreは実行していない。複合workspaceの残り52件、fresh checkoutでのGate A認定は未完了である。

## 2026-09-18: catalogと環境の事前検査

準備済み262/310、残り48件（すべて複合workspace）。全体事前検査の4つの停止を1件ずつ固定した。
`MULTI-005`は未知`--workspace`が操作結果もreportも作らない終了コード4、`MULTI-006`はGitが知る
catalog未登録の設定、`MULTI-007-01`はmemberの入れ子、`MULTI-019`はGit不在である。
いずれも`workspaces: []`で停止し、member処理を始めない。Git不在は`setup.git: false`と起動環境の`PATH`で表し、
副作用の期待値のGit状態は明示的なnullとした。監査試験を3件追加し、部分的なmember結果、warningへの縮退、
codeの取り違え、終了コード1への置換、入力をflatなmember pathへ直した写しを拒否することを確認した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `dd94c0faa244388a795af24271d6cf6bb896c480899020ab8a5b349481f28eec`。
`MULTI-007-02`（submodule）と`MULTI-007-03`（別worktree）は、fixtureがGitのmetadataを作る手段を必要とするため
この記録には含まない。

## 2026-09-18: 所有境界とmemberの変更

準備済み269/310、残り41件（すべて複合workspace）。所有境界とTASK境界、memberの独立性、catalogの変更を固定した。
`MULTI-008`は別memberへ出るsymlinkの`implements`宣言、`MULTI-009`は`src/`が`src2/`を許可しない字句境界、
`MULTI-010`は基準版と現在版の双方で行うsymlinkの所有判定である。`MULTI-010`の基準版は、Git treeのentry mode
`120000`とlink targetを監査が直接確かめる。`MULTI-011`は1つのmemberの非成功が後続memberの件数を落とさないこと、
`MULTI-017`／`018-01`／`018-02`はmember pathの移動、workspace IDの変更、memberの削除を扱う。
後者2件は管理済みSPECの削除検査として最上位のDiagnosticへ置き、member結果へ複製しない。
監査試験を6件追加し、codeの取り違え、後続memberの件数の切詰め、member要素の削除、
入力をweb内へ向けたsymlinkやID変更なしのcatalogへ直した写しを拒否することを確認した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `b1be564fc094dadff33736e16d86f2a3b3ed7a5245bab5b993735acddbadb734`。

## 2026-09-18: 複合workspace全体のverify

準備済み274/310、残り36件（すべて複合workspace）。`verify --all-workspaces`の4つの場面を固定した。
`MULTI-012`は規範文IDが重複するinvalid文書への強い依存を`SPEC-MULTI-DEPENDENCY-001`／`blocked`とし、
独立targetの`api::backend`は実行する。最上位statusは最悪値順で`failed`になる。
`MULTI-013`は2つのContext（Digest 2件）が同じbinding 1件を共有し、`MULTI-014`はwebのcommand失敗後も
apiの独立bindingを実行する。`MULTI-015`はmember単位の対象0件をwarning、`MULTI-016`は複合workspace全体の
対象0件をerror／`blocked`とし、空のCIを成功にしない。
通過targetのDigestは、review済みliteral（参照計算A）と入力treeからの導出（参照計算B）でbyte一致を確認した。
監査試験を4件追加し、遮断targetへのbinding付与、共有bindingの二重実行、Digestの同一化、失敗後のbinding省略、
status集約の取り違え、依存先を解決可能に直した入力を拒否することを確認した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `dae472e1ed294fc3ebd677545ceeecbc430096ad0101f69cf9d757397ad07c44`。

## 2026-09-18: reportと結果外形の移行

準備済み284/310、残り26件（`MULTI-007-02/03`、`MULTI-020-*`、`MULTI-021-*`）。
`MULTI-022-01..04`は、checkとverifyの既定実行と明示`--report`を対にし、既定は0件、明示時はroot workspaceの
`.spec/reports/`へ1件を排他的に作成することを固定した。対の2件は結果本体が完全に一致する。
`MULTI-023-01..03`はdual-read consumerの排他的外形を固定し、受理するJSONが公開結果Schemaへ適合すること、
混在JSONが適合しないことをSchemaそのもので確かめる。`MULTI-024-01..03`はmigration runnerのcase名を
`to-multi-workspace`と`rollback`に確定し、複合workspace化、完全rollback、修飾参照が残る部分rollbackを分けた。
監査試験を5件追加し、既定実行でのreport作成、名前patternの緩和、結果本体の変化、outcomeの取り違え、
部分rollbackを完全rollbackへ直した入力を拒否することを確認した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `a3f4a70d60adc69bd2a2de6311e19157aa238fb15b9bdc6c4942baeaac15a1be`。

## 2026-09-18: resource上限の境界とmember pathのGit構造

準備済み310/310。matrixの未作成fixtureは0件になった。
`MULTI-007-02/03`は、ADR-048で加えた`submodule`と`worktree`のsetup operationでmember pathのGit構造を作る。
生成したgitlink、`.gitmodules`、worktreeの`.git` fileは2回のsetupで同じになり、副作用の比較からは
入れ子のGitのmetadataを除外する。
`MULTI-020-01..16`と`MULTI-021-01..08`は、8 dimensionの`limit - 1`、`limit`、`limit + 1`をdataset manifestから
生成する。入力、期待結果、副作用期待値をversion管理せず、tree digest、`expect.resultDigest`、`stateDigest`で固定した。
`MULTI-021-08`は`verifyBindingCount`と`commandDefinitionCount`が同時に超過するため、複合workspace仕様 §10へ
verify実行計画のdimensionを優先して報告する規則を加え、`companionDimensions`へ明示した。
台帳の根拠文書hashは再review後に更新した。

既定の統合検証は縮小profileで生成器の決定論と計数を照合する。実寸の照合は`uv run fixtures/validate_scale.py`で
24件すべてを生成し、tree digest、期待結果のdigest、隔離setup 2回のstate digestを照合した（37秒、status Passed）。
最大入力は256 MiB（`MULTI-021-03`、308 file）、最多fileは10,027件（`MULTI-021-08`）である。
監査試験を5件、harnessの自己試験を3件追加した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `154cac445a806f94d0767c64bd5407a1336cbff7c3dd8f22cc3507f1c3c9aa73`。
残るpendingは、Coreと照合した入力・期待値（Gate B）と、fresh checkoutからのGate A全体実行である。

## 2026-09-18: fresh checkoutでの再現性と実行bitの修正

commit済みのrepositoryを`git clone`した写しで統合検証とscale検証を実行した。最初の実行で、
`bin/*.sh`など14件の実行bitがGitのindexへ入っていないことがわかり、監査試験5件が失敗した。
このrepositoryは`core.fileMode=false`のため、作業treeの実行bitがindexへ記録されていなかった。
副作用期待値を正として`git update-index --chmod=+x`で直し、統合検証へ、repo/配下の入力1,730件について
Gitのindexの実行bitと副作用期待値の一致を照合する検査を加えた。

修正後、fresh checkoutと作業treeの統合検証reportはbyte一致した。
Report SHA-256: `c81f0f402f624d69cc80ba5abd09e45806edfd8f3572db2f0bd135313896ba27`（両者同じ）。
scale検証もfresh checkoutで24件すべてPassedとなり、tree digestを含む結果は作業treeと同じであった（36秒）。
監査試験175件と基盤の自己試験6件は成功した。Gate Aは、Coreと照合した入力・期待値が残るためBlockedのままである。
