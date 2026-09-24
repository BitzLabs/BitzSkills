# Step 0Bの適合fixture準備

repository rootで次を実行する。

```text
uv run fixtures/validate_step0b.py
```

このcommandは、公開の結果・Diagnostic・manifestのJSON例、Schemaの構造、EBNFの参照、registryの構造、
matrixの一覧、現行の設計契約と承認済みADRの相対linkを監査する。Step 0-Pの検証とfixture基盤の自己試験も実行する。
固定した依存はscriptに宣言してあり、初回はpackageのdownloadが必要である。

終了コード0はGate Aの許可、1はerrorまたは未完了の証拠が残っていることを表す。現在は1が想定どおりである
（2026-09-24時点で、matrix 310件はすべて入力と期待値を検証済みであり、fresh checkoutからの
Gate A全体実行だけが未完了）。未作成のfixtureは個別に列挙される。

上限境界の24件は入力を生成するため、実寸の照合は次のcommandで行う。

```text
uv run fixtures/validate_scale.py
```
静的な検査では、fixtureが独立した原因を1つだけ持つことを証明できない。Diagnosticの対応はreview済みの台帳で管理する
（[Diagnostic意味網羅review](Diagnostic意味網羅review.md)）。監査は台帳の整合と根拠文書の鮮度を検査し、自然言語の意味は検査しない。

[複合workspaceのfixture](multi/複合workspace-golden-Digest-review.md)は、root workspaceと2つのmemberからなる
固定corpusを持つ。golden Context Digestは、単一workspaceと同じく独立した2系統の参照計算で照合する。
[修飾IDの解決](multi/修飾IDの解決review.md)は、同じlocal IDの非衝突、非修飾参照、存在workspaceの不在target、
不在起点の4つを1件ずつ切り分ける。
[catalogと環境の事前検査](multi/catalogと環境の事前検査review.md)は、未知`--workspace`、未登録設定、memberの入れ子、
Git不在の4つの停止を切り分ける。
[所有境界とmemberの変更](multi/所有境界とmemberの変更review.md)は、symlinkの所有判定、TASK changesのsegment境界、
memberの非成功の独立性、member pathの移動とID変更・削除を扱う。
[複合workspace全体のverify](multi/複合workspace全体のverify-review.md)は、派生遮断、共有binding、失敗後の継続、
member単位と全体の対象0件を扱う。
[reportと結果外形の移行](multi/reportと結果外形の移行review.md)は、既定と明示`--report`の対、dual-read consumerの
排他的外形、複合workspace化と完全・部分rollbackを扱う。
[resource上限の境界](multi/resource上限の境界review.md)は、8 dimensionの`limit - 1`、`limit`、`limit + 1`を
dataset manifestから生成し、期待結果と副作用をdigestで固定する。

[target vector](targets/README.md)は、種別とpurposeの18組合せと、graphの7ケースを固定する。監査は4つの順序付き集合を
限定した参照計算と比べ、入力順に依存しないことを検査する。Coreの実行やbindingを保証するものではない。

[単一workspaceの初期fixture](single/README.md)は、実入力9件、manifest、完全な期待JSON、read-onlyの実行前後の
期待値を持つ。隔離した2回のsetupを、それぞれ固定した実行前snapshotと照合する。
これは準備証拠の検証であり、Coreの実行や操作後に観測した副作用の検証ではない。
cwd不在のcaseは、Linuxの検証hostに実行可能な`/bin/true`を要求する。前提が欠ければ監査は失敗する。

[EARS fixture](single/EARS-AI構文・候補抽出review.md)は、構文・ID・候補・拡張の12ケースを持つ。
固定したREQ入力、Frontmatter Schema、完全な期待JSON、tokenの位置、隔離した2回のsetupを監査する。
CoreのScannerやParserを実装・保証するものではない。

[文書fixture](single/文書構造・UTF-8-review.md)は、file名、必須の規範文・見出し、配置、無視するstyle、不正なUTF-8の
9ケースを、固定した準備証拠とともに加える。固定した入力byte列、完全な期待JSON、FrontmatterとSchemaの副作用期待値、
隔離した2回のsetupを監査する。skip／継続の件数と、修復したUTF-8や追加の原因の拒否は回帰試験で扱う。
Coreの受入はGate Bで行う。

[trace fixture](single/関係・path・coverage-review.md)は、強い参照、relationの型、旧`refs`、path、coverageの6ケースを、
固定した準備証拠とともに加える。完全な期待JSON、固定した入力byte列、review済みのFrontmatter値、read-onlyのsnapshot、
隔離した2回のsetupを検証し、原因の欠落や追加を改変試験で拒否する。

[graph fixture](single/文書ID重複・循環review.md)は、文書IDの重複と、requires／refines／relatedの自己循環の4ケースを、
固定した準備証拠とともに加える。完全な期待値、review済みのFrontmatter値、隔離した2回のsetupを検査し、
改変試験で原因の変更、Diagnosticの重複、改番の提案、副作用を拒否する。

[Git fixture](single/Git基準版・状態遷移review.md)は、禁止された遷移、新規文書、削除、rename、承認済みの意味変更の
5ケースを、固定した準備証拠とともに加える。HEADとindexのblob、作業treeのbyte列を直接検査し、完全な期待結果、
read-onlyのsnapshot、隔離した2回のsetupも確認する。改変試験で意図しないstageやcommitを拒否する。

[承認済みREQの保護対象外fixture](single/approved-REQの保護対象外変更review.md)は、implements／tests／related／拡張／散文だけの
変更5ケースを加え、準備済みを50/311にした。補助fileはHEADのまま変わらず、作業treeではREQだけが変わる。
Git fixtureの監査を使い、完全な成功期待値と、追加の原因を拒否する改変試験を持つ。

[TASK境界fixture](single/TASK境界・対象選択review.md)は、明示・変更範囲・全体の境界の3ケースを加える。
[Git対象選択・影響候補fixture](single/Git対象選択・影響候補review.md)は、直接依存、unborn、空または所有者のない選択の4ケースを加える。
[Git環境fixture](single/Git基準版error・Git不在review.md)は、不正な基準版とGit不在のケースを加え、準備済みを60/311にした。
後者は、人向けの理由文を照合せずにCLIのerror出力の形を固定し、明示的にGitがない場合だけGitのsnapshotをnullにする。

[Context非成功fixture](single/Context非成功review.md)は、起点不在、未完了のTASK、置換済みの起点・依存先、後継の重複の
5ケースを加え、準備済みを65/311にした。完全な非成功JSON、空のBundleの期待値、unbornのGit snapshot、改変試験を、
Coreを実行せずに検査する。

`harness-input` directoryは基盤の試験入力であり、`SINGLE-*`や`MULTI-*`の受入fixtureではない。
`harness.py`は隔離したGit repositoryを作り、file、実行bit、symlinkの参照先、directoryを比較する。
snapshotは`.git`を除き、自己試験はGitのstatusとindexを別に比較する。setupは親directoryへの移動とsymlinkの祖先を
拒否する。Coreの操作は実行しない。呼出し側は、受入manifest全体をSchemaで検証しなければならない。

`process_helper.py`は、正常・非0の終了、signalによる終了、timeout、pipeを保持する子孫を再現する。
`test_harness.py`はこれらの試験に時間の上限を設け、自分が作った隔離process groupだけを強制終了する。これらの試験は
helperとharnessの振る舞いを示すもので、将来のCoreのprocess runnerの受入ではない。

検証環境: Python 3.11以上とGitがあるLinux／POSIX。監査は一時的なfixture repositoryだけを書き込み、
受入結果や文書を自動更新しない。

[CLI引数境界fixture](single/CLI引数境界review.md)は、optionの重複、空の引数、timeoutの範囲・表記、reportの構文の
9ケースを加え、準備済みを116/311にした。この時点の引数不正fixture 14件は、出力契約と隔離した2回のsetupの検査を共有する。

[expand反復fixture](single/expand反復review.md)は、異なる値の整列と重複排除を、2系統のDigest参照計算と隔離した
2回のsetupとともに加え、準備済みを118/311にした。

[起点・workspace不存在fixture](single/起点・workspace不存在review.md)は、contextの起点不在（結果を伴うfailed／1）と、
workspace不在（結果のない終了コード4）を区別する。準備済みは120/311になった。

[出力形式fixture](single/出力形式review.md)は、checkの成功・失敗のtext出力と、明示report付きのJSONを加え、
準備済みを123/311にした。

[BOM・Frontmatter fixture](single/BOM・Frontmatter-review.md)は、警告と文書skipの11ケースを加え、準備済みを134/311にした。

[Diagnostic-text制御文字](single/Diagnostic-text制御文字review.md)は、承認済みの可視化escapeの規則を固定し、
準備済みを135/311にした。

[Diagnostic順序](single/Diagnostic順序review.md)は、独立した同一条件のerror 3件を固定し、準備済みを136/311にした。

[上限・未知entry fixture](single/上限・未知entry-review.md)は、64 KiBの設定、1 MiBのSPEC Markdown、32 KiBのFrontmatter、
規範文数と配列要素数のケースと、`.spec/`内の未知entryを加える。入力はreview済みの定数から生成して測り直すため、
他の次元の上限を越えるfixtureを監査が拒否する。準備済みは143/311になった。

[registry閉包fixture](single/registry閉包review.md)は、理由のないSHOULDの警告、`related`の参照先不在、禁止された設定YAML、
doctorの設定・Git不在のケース、workspace不在、未対応のEARS-AI majorを加え、matrix §6.9を完了する。
doctorの契約で`lostGuarantees`の4つの名前を固定した。準備済みは150/311になった。

[Scanner・位置fixture](single/Scanner・位置review.md)は、§6.10のcheck 16ケースを加える。run長によるcode span、
未知のescape、閉じていないquoted extensionの値、候補を抑止する4つの構文、形式不正のID 4件、位置違いの理由field、
multi-byte文字とTABの後のコードポイント列、原因を共有する2件のprimaryである。同節の`context`の4ケースは未作成だった。
準備済みは166/311になった。

[既定表示・revision fixture](single/既定表示・revision-review.md)は、check、verify、doctorの`--format`省略、
commit済みのcontextのrevision、Git不在のverifyのrevision、出力のないcommand、2件のverify targetでの同一条件を加える。
要約行は対応するJSONから導き直し、revisionの形は隔離したrepositoryで観測する。準備済みは173/311になった。

SINGLE-104-01は、提案26で決めcontext仕様 §9へ固定したMarkdown提示に従う。
`markdown_reference.py`がreview済みの結果からその契約どおりに描画し、監査はcommitしたBundleをそれと比べ、
sectionの順序、本文を変えないこと、duration tokenがないことを検査する。
この時点の準備済みは174/311、残りは137件だった。

[Frontmatter境界fixture](single/Frontmatter境界review.md)として、種別definition、title長、必須／null、
空・重複配列、未知key、`x-`拡張、REQの`changes`の20件を加えた。各fieldはJSON構文のflow valueとして書き、
独立にdecodeして`frontmatter.schema.json`と照合する。
この時点でSINGLE-118-02／03と120-01／02は未作成であり、準備済みは201/311、残りは110件だった。

Frontmatter境界の追補として、SINGLE-118-02／03（test要素のkey tuple重複判定）と120-01／02（`changes`空・省略TASKの
明示TASK check）を加え、matrixの114〜120を完了した。準備済みは205/311、残りは106件である。

[Core副作用fixture](single/Core副作用review.md)として、SINGLE-125-01〜05を加えた。監査済みsource fixtureと
同じ起動・入力・期待結果を使い、context、doctor、reportなしcheck、書込みなしverifyでは`.spec/reports/`を置かずに
書込み0件を、明示report付きcheckでは最終report 1件だけと一時file残存0件を固定する。
SINGLE-125-06は発生条件の裁定待ちである。準備済みは210/311、残りは101件である。

SINGLE-125-06は、`.spec/reports`をrepository内directoryへのsymlinkにした保存失敗として追加した。
symlinkを解決せず保存失敗とする規定を結果・Diagnostic・終了コード §8へ追加している。準備済みは211/311、残りは100件である。

[verify argv・実行環境・出力変換fixture](single/verify-argv・実行環境・出力変換review.md)として、SINGLE-126-01〜05、07、09〜16を加えた。
argv template違反5件、空引数・PATH解決不能・標準入力・環境継承、子孫がpipeを保持するtimeout、timeout後の独立binding、
制御文字変換、chunk境界をまたぐredaction、redaction後の64 KiB超過を固定する。実行caseはfixture自身のscriptを
直接観測する。126-06は設定64 KiB上限との矛盾、126-08はfixture規模のため保留した。準備済みは225/311、残りは86件である。

SINGLE-126-06は、設定64 KiB上限により到達できないため裁定でmatrixから削除した（matrixは310件）。
SINGLE-126-08は、約3,770 byteのtest path 280件を規範文なしTECH 35文書へ置き、引数なしverifyの展開後argvだけが
byte総和1 MiBを超える入力として追加した。準備済みは226/310、残りは84件である。

[明示起点の不在・ADR起点fixture](single/明示起点の不在・ADR起点review.md)として、SINGLE-111-01〜04と112-01〜04を加えた。
構文上妥当な不在起点を終了コード4や既知文書の検査へ置き換えず`CTX-ROOT-MISSING-001`で返すこと、ADR起点は
interpretのcontextと明示checkだけで受理することを固定する。

[共通target展開・advisory提示fixture](single/target展開・advisory提示review.md)として、SINGLE-106-03、107-01／02、108-01／02、
109、110、113を加えた。作成前にrole割当、draft refinement、statement起点の提示、verifyの起点TASKの`requires`を
裁定して正本へ反映した。contextの4集合を完全比較し、同じ起点のverifyが同じtarget集合とDigestを使うことを確認する。

[Digest材料の完全順序・reverse solidus fixture](single/Digest材料の完全順序review.md)として、SINGLE-122〜124を加えた。
同一pathのtest対応と同一namespace／termのextensionの正規順、path型以外のreverse solidus保持を固定する。
準備済みは245/310、残りは65件（SINGLE-127-15〜19と複合workspace60件）である。

[実行環境・配布物fixture](single/実行環境・配布物review.md)として、SINGLE-127-15〜19を加えた。作成前に
適合harnessの外部仕様をADR-046で裁定し、manifestへ`invocation.python`と`invocation.gitVersion`、runnerへ
`package`を追加した。Git版と下限CPythonは実行環境契約の本文から読み取る。単一workspaceのmatrixは全250件を
準備済みとなり、残りは複合workspace60件である。

複合workspaceの60件は、冒頭に挙げた`multi/`の7つのreviewで作成した。2026-09-18時点で、matrix 310件は
すべて準備済みである。
