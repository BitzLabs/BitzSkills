# Coreの出力文言のレビュー記録

Coreの出力文言（診断の`summary`と`suggestedAction`、引数不正のときの標準エラー出力の`<reason>`）を
[表記規則](../../docs/表記規則.md) §3.5に合わせて変えたときの、適合fixtureの期待値の変更の記録である。
変える手順は表記規則 §8の8と[ADR-062](../../docs/02.設計書/10_決定記録/ADR-062_Coreの出力文言の規範と適合fixtureの期待値の扱いを確定する.md)、
[適合fixture仕様](../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md) §1.1に従う。

## 2026-10-12: 出力文の見直し PR-2（英語の一般語の書換え）

### 追加の理由

- 出力文の計画の PR-2。Coreの出力文言には、英語の一般語（strong relation、Frontmatter、file、command、testなど）と、
  表記規則 §3.5に反する書き方（識別子のバッククォート、型名、差し込む値の前に置く語の欠落）が残っていた。
- 表記規則 §3.5がCoreの出力文言の書き方を定め、ADR-062が、§3.5に反する文言を固定している適合fixtureの期待値を
  §3.5に合わせて訂正することをADR-051の期待値の訂正として扱うと決めた。
- 診断の`summary`は規範文が文字列を1つに定めないが、適合fixtureは完全一致で比べる（適合fixture仕様 §1.1）。

### 管理者の承認

- 2026-10-12、人間の管理者（ユーザー）が、下の対応表を**このまま承認した**（ADR-062 Decision 2）。
- 追加の決定: 行#147（`VERIFY-TARGETS-EMPTY`の単一ワークスペースの文言）は、複合ワークスペース全体の文言「検証対象がありません」にそろえる。
  「実行可能ファイル」を使う（診断レジストリ`VERIFY-EXECUTABLE-UNAVAILABLE`の書き方）。
- **変更後の文字列は、規範文から一意に導いた値ではなく、表記規則 §3.5に合わせて管理者が承認した値である。**
  期待値の根拠はこの承認済みの対応表であり、Coreの出力ではない（ADR-051、ADR-062）。

### 承認済みの対応表

「変更前」はコミット`a5d4229e`のCoreの出力文言、「変更後」は承認した値である。`{…}`は実行時に差し込む値を示す。
「固定しているfixture」は変更前の文言を期待値で固定していたfixtureの件数と代表のIDである。
行#の番号は承認時の対応表の番号である。

| # | 種類 | 診断コード（stderrは操作） | 場所（ファイル:行） | 変更前 | 変更後 | 根拠（§3.5 の項、§4 の行、用語集の語） | 固定しているfixture（件数と代表のID） |
|---:|---|---|---|---|---|---|---|
| 1 | summary | CTX-COVERAGE-TASK-001<br>（CTX-COVERAGE-TASK-MUST／-SHOULD） | messages.py:270（context.py:837） | `implement対象の{modality} {stmt_id}を実装するTASKがありません` | `目的implementの対象規範文{modality} {stmt_id}を実装するTASKがありません` | §3.5の2・3: implementは識別子（前に「目的」）、MUSTは括弧なし。対象規範文（用語集 §6.2） | 4件（SINGLE-054、SINGLE-135、SINGLE-140ほか）；生成器・監査2 |
| 2 | summary | CTX-CYCLE-001<br>（RELATION-CYCLE） | messages.py:179（relations.py:293、multirelate.py:296） | `{relation}に禁止循環があります` | `関係型{relation}に禁止された循環があります` | §3.5の1・2: 禁止された循環（用語集 §6.1）、関係型の前に「関係型」 | 2件（SINGLE-022-01、SINGLE-022-02）；生成器・監査1 |
| 3 | summary | CTX-LIMIT-001<br>（CTX-CLOSURE-LIMIT） | messages.py:265（context.py:748） | `完全Context閉包が文書数上限を超過しました` | `コンテキストの完全な閉包が文書数上限を超過しました` | 指示書の注記: 「完全Context閉包」は用語集で使わない語。用語集 §6.2の閉包、診断レジストリ「コンテキストの完全な閉包」 | 1件（SINGLE-048-01）；生成器・監査1 |
| 4 | summary | CTX-LIMIT-001<br>（CTX-CLOSURE-LIMIT） | messages.py:266（context.py:748） | `完全Context閉包がbyte上限を超過しました` | `コンテキストの完全な閉包がバイト数上限を超過しました` | 同上。byte=バイト（§4.1）、「バイト数の上限」は診断レジストリの書き方 | 1件（SINGLE-048-02）；生成器・監査1 |
| 5 | summary | CTX-PROJECTION-001<br>（CTX-PROJECTION-OUTSIDE） | messages.py:278（context.py:1050） | `expand対象{expand_id}は完全解決集合にありません` | `展開指定の対象{expand_id}は完全解決した集合にありません` | §3.5の1: expand=展開指定（用語集 §7）。「完全解決した集合」は用語集の展開指定・診断レジストリの書き方 | 1件（SINGLE-047）；生成器・監査1 |
| 6 | summary | CTX-PROJECTION-LIMIT-001<br>（CTX-PROJECTION-LIMIT） | messages.py:282（context.py:1076） | `detail {detail}の提示量が1 MiBのhard limitを超過します` | `詳細度{detail}の提示量が1 MiBの絶対上限を超過します` | §3.5の1: detail=詳細度（用語集 §7）、hard limit=絶対上限（§4.2） | 1件（SINGLE-049）；生成器・監査1 |
| 7 | summary | CTX-RELATION-TYPE-001<br>（RELATION-TYPE） | messages.py:175（relations.py:216、multirelate.py:267。targetexpand.py:729の呼出しにも及ぶ） | `{source_kind}から{target_kind}への{relation}は許可されません` | `{source_kind}から{target_kind}への関係型{relation}は許可されません` | §3.5の2・6: relationの値（requiresなど）は識別子。前に「関係型」（用語集 §6.1） | 6件（MULTI-027-01、MULTI-027-02、SINGLE-021ほか）；生成器・監査4；うちADRへのrequires（PR-3の対象）: MULTI-027-01、MULTI-027-02、SINGLE-147、SINGLE-148、SINGLE-149 |
| 8 | summary | CTX-STALE-001<br>（CTX-DIGEST-STALE） | messages.py:285（context.py:1095） | `期待Digestが現在のContext Digestと一致しません` | `期待したハッシュ値が現在のコンテキストのハッシュ値と一致しません` | §3.5の1: Context Digest=コンテキストのハッシュ値（略: ハッシュ値。用語集 §7） | 1件（SINGLE-046）；生成器・監査1 |
| 9 | summary | EAI-CORE-SEM-001<br>（EAI-SEM-OPERAND-MISSING（-DRAFT）） | messages.py:153 | `operandが不足しています` | `オペランドが不足しています` | §4.1: operand=オペランド | 0件 |
| 10 | summary | EAI-CORE-SYNTAX-001<br>（EAI-SYNTAX-TAG-ORDER（-DRAFT）） | messages.py:149 | `tagの順序が不正です` | `タグの順序が不正です` | §4.1: tag=タグ | 4件（SINGLE-007、SINGLE-008、SINGLE-101-02ほか）；生成器・監査2 |
| 11 | summary | EAI-CORE-SYNTAX-002<br>（EAI-SYNTAX-TAG-REQUIRED（-DRAFT）） | messages.py:150 | `必須tagが不足しています` | `必須のタグが不足しています` | §4.1: tag=タグ（「必須の節」と同じ形） | 0件 |
| 12 | summary | EAI-CORE-SYNTAX-004<br>（EAI-SYNTAX-TAG-UNCLOSED（-DRAFT）） | messages.py:142 | `tagが閉じられていません` | `タグが閉じられていません` | §4.1: tag=タグ | 3件（SINGLE-012-01、SINGLE-102、SINGLE-103-02）；生成器・監査2 |
| 13 | summary | EAI-CORE-SYNTAX-004<br>（EAI-SYNTAX-TAG-UNCLOSED（-DRAFT）） | messages.py:143 | `未知のescapeです` | `未知のエスケープです` | §4.1: escape=エスケープ | 1件（SINGLE-097-02）；生成器・監査1 |
| 14 | summary | EAI-CORE-SYNTAX-004<br>（EAI-SYNTAX-TAG-UNCLOSED（-DRAFT）） | messages.py:144 | `extension値のquoteが閉じられていません` | `拡張タグの値の引用符が閉じられていません` | 指示書の注記: quote=引用符、extension=拡張タグ（EARS-AIの文脈。用語集 §5） | 1件（SINGLE-098-02）；生成器・監査1 |
| 15 | summary | EAI-CORE-SYNTAX-004<br>（EAI-SYNTAX-TAG-UNCLOSED（-DRAFT）） | messages.py:145 | `tagが不正です` | `タグが不正です` | §4.1: tag=タグ | 0件 |
| 16 | summary | EAI-CORE-SYNTAX-005<br>（EAI-SYNTAX-CODE-UNCLOSED（-DRAFT）） | messages.py:141 | `code spanが閉じられていません` | `コードスパンが閉じられていません` | §4.2: code span=コードスパン | 3件（SINGLE-012-02、SINGLE-096-02、SINGLE-103-01）；生成器・監査2 |
| 17 | summary | EAI-EXT-UNKNOWN-001<br>（EAI-EXTENSION-UNKNOWN） | messages.py:155 | `未知namespaceのextensionを保持します` | `未知の名前空間の拡張タグを保持します` | §4.2: namespace=名前空間。extension=拡張タグ（用語集 §5。EARS-AIの文脈） | 3件（SINGLE-013、SINGLE-098-01、SINGLE-123）；生成器・監査3 |
| 18 | summary | SPEC-CONFIG-SCHEMA-001 | config.py:448 | `設定YAMLはmapで記述してください` | `設定YAMLはマッピングで記述してください` | §3.5の4: map=マッピング | 0件 |
| 19 | summary | SPEC-CONFIG-SCHEMA-001 | multiws.py:223（到達しにくい防御の分岐） | `member設定が不正です` | `メンバーの設定が不正です` | §4.1: member=メンバー | 0件 |
| 20 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、174 | `{key}はmapまたはargv配列で指定してください` | `設定キー{key}はマッピングまたは引数列で指定してください` | §3.5の4: map=マッピング。argv配列=引数列（§4.2: argv=引数列）。§3.5の2・6: 設定キーの前に「設定キー」を置く | 0件 |
| 21 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、200、214、256、261 | `{key}はstringで指定してください` | `設定キー{key}は文字列で指定してください` | §3.5の4: string=文字列。§3.5の2・6: 設定キーの前に「設定キー」を置く | 3件（SINGLE-004-01、SINGLE-092、SINGLE-150）；生成器・監査4、単体試験1 |
| 22 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、266、281、290、303、311 | `{key}はmapで指定してください` | `設定キー{key}はマッピングで指定してください` | §3.5の4: map=マッピング。§3.5の2・6: 設定キーの前に「設定キー」を置く | 0件 |
| 23 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、271 | `{key}は1〜100のintegerで指定してください` | `設定キー{key}は1〜100の整数で指定してください` | §3.5の4: integer=整数。§3.5の2・6: 設定キーの前に「設定キー」を置く | 0件 |
| 24 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、275 | `{key}は4096〜1048576のintegerで指定してください` | `設定キー{key}は4096〜1048576の整数で指定してください` | §3.5の4: integer=整数。§3.5の2・6: 設定キーの前に「設定キー」を置く | 1件（SINGLE-151）；生成器・監査1 |
| 25 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、286 | `{key}は1〜3600のintegerで指定してください` | `設定キー{key}は1〜3600の整数で指定してください` | §3.5の4: integer=整数。§3.5の2・6: 設定キーの前に「設定キー」を置く | 0件 |
| 26 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、306 | `{key}はbooleanで指定してください` | `設定キー{key}は真偽値で指定してください` | §3.5の4: boolean=真偽値（§4.2）。§3.5の2・6: 設定キーの前に「設定キー」を置く | 0件 |
| 27 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | config.py:122、294、315 | `{key}は[a-z][a-z0-9-]{0,31}で指定してください` | `設定キー{key}は[a-z][a-z0-9-]{0,31}で指定してください` | §3.5の6: {key}の前に「設定キー」を置く（形式の正規表現は変えない） | 0件 |
| 28 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | messages.py:290（config.py:179） | `argv templateは256要素以下で指定してください` | `引数列テンプレートは256要素以下で指定してください` | 指示書の注記: argv templateは定義語「引数列テンプレート」（用語集 §8） | 1件（SINGLE-126-04）；生成器・監査1 |
| 29 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | messages.py:291（config.py:185） | `argvの要素はstringで指定してください` | `argvの要素は文字列で指定してください` | §3.5の4: string=文字列。単独のargvは識別子（ユーザーの決定） | 1件（SINGLE-126-01）；生成器・監査1 |
| 30 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-FIELD-TYPE） | messages.py:292（config.py:189） | `argv[0]は空stringにできません` | `argv[0]は空文字列にできません` | §3.5の4: string=文字列（§4.2） | 1件（SINGLE-126-02）；生成器・監査1 |
| 31 | summary | SPEC-CONFIG-SCHEMA-001<br>（CONFIG-SCHEMA-MAJOR） | config.py:473 | `未対応のSchema majorです` | `未対応のスキーマのメジャーバージョンです` | §4.1: Schema=スキーマ、major version=メジャーバージョン | 1件（SINGLE-003）；単体試験1 |
| 32 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:78、111、124、134。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}のanchorは禁止です` | `{label}のアンカーは禁止です` | §4.1: anchor=アンカー | 2件（SINGLE-087-02、SINGLE-091）；生成器・監査2 |
| 33 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:80、113、126。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}のcustom tagは禁止です` | `{label}のカスタムタグは禁止です` | §4.1: custom tag=カスタムタグ | 1件（SINGLE-087-01）；生成器・監査1 |
| 34 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:106。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}のaliasは禁止です` | `{label}のエイリアスは禁止です` | §4.1: alias=エイリアス | 1件（SINGLE-087-03）；生成器・監査1 |
| 35 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:132。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}の複雑keyは禁止です` | `{label}の複雑なキーは禁止です` | §4.1: key=キー。「複雑なキー」は診断レジストリの書き方 | 0件 |
| 36 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:138。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}のmapping keyは文字列だけを許可します` | `{label}のマッピングのキーは文字列だけを許可します` | §4.1: mapping=マッピング、key=キー | 0件 |
| 37 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:141。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}のmerge keyは禁止です` | `{label}のマージキーは禁止です` | §4.1: merge key=マージキー | 1件（SINGLE-087-04）；生成器・監査1 |
| 38 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:146。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}の重複mapping keyは禁止です` | `{label}の重複したマッピングのキーは禁止です` | §4.1: mapping=マッピング、key=キー。「重複したマッピングのキー」は診断レジストリの書き方 | 1件（SINGLE-087-05）；生成器・監査1 |
| 39 | summary | SPEC-CONFIG-SCHEMA-001／SPEC-FM-SCHEMA-001<br>（CONFIG-YAML-FORBIDDEN／FM-YAML-FORBIDDEN） | yamlsafe.py:173。{label}は設定YAML（yamlsafe.py:189。変更なし）またはFrontmatter→フロントマター（messages.py:40の定数を変える） | `{label}の複数documentは禁止です` | `{label}の複数のYAML文書は禁止です` | 「複数のYAML文書」は診断レジストリの書き方（document=YAML文書） | 0件 |
| 40 | summary | SPEC-CONFIG-UNKNOWN-001<br>（CONFIG-KEY-PROFILES） | config.py:240 | `profilesはCore 1.0では使用しません` | `設定キーprofilesはCore 1.0では使用しません` | §3.5の2・6: 設定キーは識別子。前に「設定キー」を置く | 1件（SINGLE-005-02） |
| 41 | summary | SPEC-CONFIG-UNKNOWN-001<br>（CONFIG-KEY-UNKNOWN） | config.py:250 | `未知の設定keyです` | `未知の設定キーです` | §4.1: key=キー | 2件（SINGLE-005-01、SINGLE-153）；生成器・監査1 |
| 42 | summary | SPEC-DOCTOR-COMMAND-001<br>（DOCTOR-COMMAND-CWD） | doctor.py:371 | `command cwdを解決できません` | `コマンドの作業ディレクトリを解決できません` | §4.1・§4.2: command=コマンド、cwd=作業ディレクトリ | 1件（SINGLE-006-02） |
| 43 | summary | SPEC-DOCTOR-COMMAND-001<br>（DOCTOR-COMMAND-FILE） | doctor.py:388 | `command実行fileを解決できません` | `コマンドの実行可能ファイルを解決できません` | §4.1: command=コマンド、file=ファイル。指示書の注記（実行可能ファイル） | 2件（MULTI-026-02、SINGLE-006-01）；生成器・監査1 |
| 44 | summary | SPEC-DOCTOR-CORE-001<br>（DOCTOR-RUNTIME-VERSION） | doctor.py:182、293 | `実行環境のCPython versionが下限未満です` | `実行環境のCPythonのバージョンが下限未満です` | §4.1: version=バージョン。CPythonは§3.3 | 0件 |
| 45 | summary | SPEC-EARS-VERSION-001／SPEC-DOCTOR-EARS-001<br>（EARS-SCHEMA-MAJOR／DOCTOR-EARS-VERSION） | config.py:505 | `未対応のEARS-AI majorです` | `未対応のEARS-AIのメジャーバージョンです` | §4.1: major version=メジャーバージョン。EARS-AIは§3.3 | 1件（SINGLE-095）；生成器・監査1 |
| 46 | summary | SPEC-FILE-NAME-001<br>（DOC-FILE-NAME-ID） | messages.py:111（document.py:407） | `file名IDとFrontmatter IDが一致しません` | `ファイル名のIDとフロントマターのIDが一致しません` | §3.5の1: file=ファイル、Frontmatter=フロントマター。「ファイル名のIDとフロントマターのID」は診断レジストリの書き方 | 2件（MULTI-011、SINGLE-014）；生成器・監査2 |
| 47 | summary | SPEC-FM-REQUIRED-001<br>（FM-FIELD-REQUIRED） | messages.py:55（frontmatter.py:143） | `Frontmatterの必須field {key}がありません` | `フロントマターの必須フィールド{key}がありません` | §3.5の1・2: Frontmatter=フロントマター、field=フィールド（前に置く語） | 1件（SINGLE-117-01）；生成器・監査1 |
| 48 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:205、217、227、293、332（id、title、status、tests[i].path、verify） | `Frontmatter {key}はstringが必要です` | `フロントマターのフィールド{key}は文字列が必要です` | §3.5の1・2・4: Frontmatter=フロントマター、フィールドの前に「フィールド」、string=文字列 | 1件（SINGLE-088）；生成器・監査1、単体試験1 |
| 49 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:172（implements、changes） | `Frontmatter {key}はstringの配列が必要です` | `フロントマターのフィールド{key}は文字列の配列が必要です` | §3.5の1・2・4: string=文字列 | 1件（SINGLE-120-04）；生成器・監査1、単体試験1 |
| 50 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:239（relations） | `Frontmatter {key}はmapが必要です` | `フロントマターのフィールド{key}はマッピングが必要です` | §3.5の4: map=マッピング | 0件 |
| 51 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:247、299（relations.<関係型>、tests[i].covers） | `Frontmatter {key}はID文字列の配列が必要です` | `フロントマターのフィールド{key}はID文字列の配列が必要です` | §3.5の1・2: Frontmatter=フロントマター、フィールドの前に「フィールド」（型の部分は適合済み） | 0件 |
| 52 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:270（tests） | `Frontmatter {key}はobjectの配列が必要です` | `フロントマターのフィールド{key}はオブジェクトの配列が必要です` | §3.5の4: object=オブジェクト | 0件 |
| 53 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:279（tests[i]） | `Frontmatter {key}はobjectが必要です` | `フロントマターのフィールド{key}はオブジェクトが必要です` | §3.5の4: object=オブジェクト | 0件 |
| 54 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:288（tests[i]） | `Frontmatter {key}はpath・coversを持つobjectが必要です` | `フロントマターのフィールド{key}はフィールドpathとcoversを持つオブジェクトが必要です` | §3.5の2・4: pathとcoversは識別子（前に「フィールド」）、object=オブジェクト | 0件 |
| 55 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:318、336（tests[i].command、verify） | `Frontmatter {key}はcommand名が必要です` | `フロントマターのフィールド{key}はコマンド名が必要です` | §4.1: command=コマンド | 0件；単体試験1 |
| 56 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:352（refs） | `Frontmatter {key}はscalarの配列が必要です` | `フロントマターのフィールド{key}はスカラーの配列が必要です` | §4.1: scalar=スカラー | 0件 |
| 57 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | frontmatter.py:188 | `Frontmatterはmapで記述してください` | `フロントマターはマッピングで記述してください` | §3.5の1・4: Frontmatter=フロントマター、map=マッピング | 0件 |
| 58 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:59（frontmatter.py:203ほか） | `Frontmatter {key}にnullは指定できません` | `フロントマターのフィールド{key}にnullは指定できません` | §3.5の1・2: nullは識別子（英字）。{key}の前に「フィールド」 | 1件（SINGLE-117-02）；生成器・監査1 |
| 59 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:63（frontmatter.py:207ほか） | `Frontmatter {key}は空文字列にできません` | `フロントマターのフィールド{key}は空文字列にできません` | §3.5の1・2・6 | 0件 |
| 60 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:66（frontmatter.py:219） | `Frontmatter titleは改行を含まない1〜120文字で指定してください` | `フロントマターのフィールドtitleは改行を含まない1〜120文字で指定してください` | §3.5の1・2: titleは識別子（前に「フィールド」） | 4件（SINGLE-116-02、SINGLE-116-03、SINGLE-116-04ほか）；生成器・監査1 |
| 61 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:70（frontmatter.py:209） | `Frontmatter idの形式が不正です` | `フロントマターのフィールドidの形式が不正です` | §3.5の1・2 | 0件 |
| 62 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:74（frontmatter.py:231） | `Frontmatter statusの値が不正です` | `フロントマターのフィールドstatusの値が不正です` | §3.5の1・2 | 0件 |
| 63 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:86（frontmatter.py:364） | `Frontmatter {key}はscalar・scalar配列・文字列keyのmapだけを使用できます` | `フロントマターのフィールド{key}はスカラー・スカラーの配列・文字列のキーを持つマッピングだけを使用できます` | §3.5の1・2・4: scalar=スカラー、key=キー、map=マッピング | 0件 |
| 64 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:90（frontmatter.py:243） | `relationsに未知のkey {key}があります` | `フィールドrelationsに未知のキー{key}があります` | §3.5の2・6: relationsは識別子（前に「フィールド」）、key=キー | 1件（SINGLE-119-01）；生成器・監査1 |
| 65 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:94（frontmatter.py:254） | `relations.{key}に重複した値があります` | `フィールドrelations.{key}に重複した値があります` | §3.5の2 | 1件（SINGLE-118-01）；生成器・監査1 |
| 66 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:98（frontmatter.py:178、311、356） | `{key}に重複した値があります` | `フィールド{key}に重複した値があります` | §3.5の2・6: {key}の前に「フィールド」 | 0件；生成器・監査1 |
| 67 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:101（frontmatter.py:324） | `testsに重複した要素があります` | `フィールドtestsに重複した要素があります` | §3.5の2 | 1件（SINGLE-118-02）；生成器・監査1 |
| 68 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:102（frontmatter.py:307） | `tests[].coversは1件以上指定してください` | `フィールドtests[].coversは1件以上指定してください` | §3.5の2 | 1件（SINGLE-117-03）；生成器・監査1 |
| 69 | summary | SPEC-FM-SCHEMA-001<br>（FM-FIELD-TYPE） | messages.py:106（frontmatter.py:284） | `testsの要素に未知のkey {key}があります` | `フィールドtestsの要素に未知のキー{key}があります` | §3.5の2・6、§4.1: key=キー | 1件（SINGLE-119-02）；生成器・監査1 |
| 70 | summary | SPEC-FM-SCHEMA-001<br>（FM-YAML-SYNTAX） | messages.py:41、45（document.py:358、377） | `Frontmatter YAMLの構文が不正です` | `フロントマターのYAMLの構文が不正です` | §3.5の1: Frontmatter=フロントマター。YAMLは§3.3 | 1件（SINGLE-086）；生成器・監査1 |
| 71 | summary | SPEC-FM-UNAVAILABLE-001<br>（FM-FIELD-UNAVAILABLE） | messages.py:78（frontmatter.py:153） | `{kind_label}では{key}を使用できません` | `{kind_label}ではフィールド{key}を使用できません` | §3.5の2・6: {key}の前に「フィールド」。{kind_label}はREQ／TECH／ADR／TASK（§3.3） | 2件（SINGLE-084、SINGLE-120-03）；生成器・監査2、単体試験1 |
| 72 | summary | SPEC-FM-UNKNOWN-001<br>（FM-FIELD-UNKNOWN） | messages.py:82（frontmatter.py:163） | `未知のFrontmatter fieldを無視します` | `未知のフロントマターのフィールドを無視します` | §3.5の1: Frontmatter=フロントマター、field=フィールド | 2件（SINGLE-085、SINGLE-119-03）；生成器・監査2 |
| 73 | summary | SPEC-GIT-DEGRADED-001<br>（CHECK-GIT-DEGRADED） | messages.py:231（check.py:769） | `Git不在のため全体checkへ縮退します。承認済みREQ保護、状態遷移、管理済みSPEC削除の差分検査は実施できません` | `Git不在のため全体検査へ縮退します。承認済み要求の保護、状態遷移、管理済みの仕様文書の削除の差分検査は実施できません` | §3.5の1: 全体検査・承認済み要求の保護・状態遷移（用語集 §8、§4）、SPEC=仕様文書 | 1件（SINGLE-037）；生成器・監査1 |
| 74 | summary | SPEC-INPUT-BOM-001<br>（INPUT-BOM-CONFIG） | config.py:359 | `設定file先頭のBOMを除いて解析を続行します` | `設定ファイル先頭のBOMを除いて解析を続行します` | §4.1: file=ファイル | 1件（SINGLE-081）；生成器・監査1 |
| 75 | summary | SPEC-INPUT-BOM-001<br>（INPUT-BOM-SPEC） | messages.py:30（document.py:346） | `SPEC file先頭のBOMを除いて解析を続行します` | `仕様文書のファイル先頭のBOMを除いて解析を続行します` | §3.5の1: SPEC=仕様文書、file=ファイル。BOMは§3.3 | 1件（SINGLE-082）；生成器・監査1 |
| 76 | summary | SPEC-INPUT-LIMIT-001<br>（INPUT-LIMIT-ARRAY-COUNT） | messages.py:27（frontmatter.py:175、251、272、304、354） | `1文書の関係・path配列の項目数が1,000上限を超過しました` | `1文書の関係・パスの配列の項目数が1,000上限を超過しました` | §4.1: path=パス。「パスの配列」は診断レジストリの書き方 | 1件（SINGLE-080-03）；生成器・監査1 |
| 77 | summary | SPEC-INPUT-LIMIT-001<br>（INPUT-LIMIT-CONFIG） | config.py:339 | `設定fileが64 KiB上限を超過しました` | `設定ファイルが64 KiB上限を超過しました` | §4.1: file=ファイル | 1件（SINGLE-078）；生成器・監査1 |
| 78 | summary | SPEC-INPUT-LIMIT-001<br>（INPUT-LIMIT-FRONTMATTER） | messages.py:18（document.py:364） | `Frontmatterが32 KiB上限を超過しました` | `フロントマターが32 KiB上限を超過しました` | §3.5の1: Frontmatter=フロントマター（用語集 §4） | 1件（SINGLE-079-02）；生成器・監査1 |
| 79 | summary | SPEC-INPUT-LIMIT-001<br>（INPUT-LIMIT-SPEC） | messages.py:17（document.py:341） | `SPEC Markdownが1 MiB上限を超過しました` | `仕様文書のMarkdownが1 MiB上限を超過しました` | §3.5の1: SPEC=仕様文書。Markdown・MiBは§3.3 | 1件（SINGLE-079-01）；生成器・監査1 |
| 80 | summary | SPEC-INPUT-LIMIT-001<br>（INPUT-LIMIT-SPEC-COUNT） | messages.py:23（document.py:534） | `SPEC fileが{limit}件上限を超過しました` | `仕様文書のファイルが{limit}件上限を超過しました` | §3.5の1: SPEC=仕様文書、file=ファイル。{limit}は3桁区切りの数（10,000） | 0件；単体試験1 |
| 81 | summary | SPEC-INPUT-READ-001<br>（INPUT-IO-CONFIG） | config.py:532 | `設定fileを読み取れません` | `設定ファイルを読み取れません` | §4.1: file=ファイル | 0件 |
| 82 | summary | SPEC-INPUT-READ-001<br>（INPUT-IO-SPEC） | messages.py:16（document.py:326） | `SPEC fileを読み取れません` | `仕様文書のファイルを読み取れません` | §3.5の1: SPEC=仕様文書、file=ファイル | 0件 |
| 83 | summary | SPEC-INPUT-READ-001<br>（INPUT-UTF8-CONFIG） | config.py:400 | `設定fileをUTF-8として復号できません` | `設定ファイルをUTF-8として復号できません` | §4.1: file=ファイル | 0件 |
| 84 | summary | SPEC-INPUT-READ-001<br>（INPUT-UTF8-SPEC） | messages.py:15（document.py:351） | `SPEC fileをUTF-8として復号できません` | `仕様文書のファイルをUTF-8として復号できません` | §3.5の1: SPEC=仕様文書（用語集 §4）、file=ファイル（§4.1） | 1件（SINGLE-019）；生成器・監査1 |
| 85 | summary | SPEC-MULTI-CONFIG-001<br>（MULTI-CONFIG） | messages.py:338（multiws.py:154） | `multiWorkspaceはmapで指定してください` | `設定キーmultiWorkspaceはマッピングで指定してください` | §3.5の2・4: 設定キーの前に「設定キー」、map=マッピング | 0件 |
| 86 | summary | SPEC-MULTI-CONFIG-001<br>（MULTI-CONFIG） | messages.py:339（multiws.py:173） | `multiWorkspace.membersは1件以上指定してください` | `設定キーmultiWorkspace.membersは1件以上指定してください` | §3.5の2 | 0件 |
| 87 | summary | SPEC-MULTI-CONFIG-001<br>（MULTI-CONFIG） | messages.py:340（multiws.py:168） | `multiWorkspace.membersは配列で指定してください` | `設定キーmultiWorkspace.membersは配列で指定してください` | §3.5の2 | 0件 |
| 88 | summary | SPEC-MULTI-CONFIG-001<br>（MULTI-CONFIG） | messages.py:341（multiws.py:185） | `multiWorkspace.membersの要素はmapで指定してください` | `設定キーmultiWorkspace.membersの要素はマッピングで指定してください` | §3.5の2・4 | 0件 |
| 89 | summary | SPEC-MULTI-CONFIG-001<br>（MULTI-CONFIG） | messages.py:342（multiws.py:161） | `multiWorkspace.maxMembersは1〜100のintegerで指定してください` | `設定キーmultiWorkspace.maxMembersは1〜100の整数で指定してください` | §3.5の2・4: integer=整数 | 0件 |
| 90 | summary | SPEC-MULTI-DEPENDENCY-001<br>（MULTI-DEPENDENCY） | messages.py:369（verify.py:505） | `依存するworkspaceの非成功によりContextを構成できません` | `依存するワークスペースの非成功によりコンテキストを構成できません` | §4.1: workspace=ワークスペース。Context=コンテキスト（用語集 §7） | 1件（MULTI-012）；生成器・監査1 |
| 91 | summary | SPEC-MULTI-DEPENDENCY-001<br>（MULTI-DEPENDENCY-DOCTOR） | doctor.py:220 | `{name}検査に必要な設定の出力を取得できません` | `検査項目{name}に必要な設定の出力を取得できません` | §3.5の6: {name}（schema・ears・command・impact）の前に「検査項目」（用語集 §8） | 0件 |
| 92 | summary | SPEC-MULTI-GIT-001<br>（MULTI-GIT） | messages.py:359（multiws.py:755） | `Git repositoryの境界を確定できません` | `Gitのリポジトリの境界を確定できません` | §4.1: repository=リポジトリ | 1件（MULTI-019）；生成器・監査1 |
| 93 | summary | SPEC-MULTI-ID-001<br>（MULTI-ID） | messages.py:348（multiws.py:263） | `workspace idの形式が不正です` | `ワークスペースIDの形式が不正です` | §4.1: workspace=ワークスペース。IDは§3.3 | 0件 |
| 94 | summary | SPEC-MULTI-ID-001<br>（MULTI-ID） | messages.py:349（multiws.py:268、382） | `workspace idが複合workspace内で重複しています` | `ワークスペースIDが複合ワークスペース内で重複しています` | §4.1: workspace=ワークスペース（複合ワークスペースは用語集 §3） | 0件 |
| 95 | summary | SPEC-MULTI-LIMIT-001<br>（MULTI-LIMIT） | messages.py:372-384（multiws.py:552、verify.py:1179、1195）。dimension=memberCount | `member数が上限{limit}を超過しました` | `メンバー数が上限{limit}を超過しました` | §4.1: member=メンバー | 0件 |
| 96 | summary | SPEC-MULTI-LIMIT-001<br>（MULTI-LIMIT） | messages.py:372-384（multiws.py:552、verify.py:1179、1195）。dimension=specFileCount | `SPEC file数が上限{limit}を超過しました` | `仕様文書のファイル数が上限{limit}を超過しました` | §3.5の1: SPEC=仕様文書、file=ファイル | 0件 |
| 97 | summary | SPEC-MULTI-LIMIT-001<br>（MULTI-LIMIT） | messages.py:372-384（multiws.py:552、verify.py:1179、1195）。dimension=inputBytes | `入力byte数が上限{limit}を超過しました` | `入力バイト数が上限{limit}を超過しました` | §4.1: byte=バイト | 0件 |
| 98 | summary | SPEC-MULTI-LIMIT-001<br>（MULTI-LIMIT） | messages.py:372-384（multiws.py:552、verify.py:1179、1195）。dimension=relationEdgeCount | `relation edge数が上限{limit}を超過しました` | `関係のエッジ数が上限{limit}を超過しました` | §4.1: edge=エッジ。relation=関係（用語集 §6.1） | 0件 |
| 99 | summary | SPEC-MULTI-LIMIT-001<br>（MULTI-LIMIT） | messages.py:372-384（multiws.py:552、verify.py:1179、1195）。dimension=traceEntryCount | `trace項目数が上限{limit}を超過しました` | `トレースのエントリ数が上限{limit}を超過しました` | §4.1: entry=エントリ。trace=トレース（用語集 §6.3） | 0件 |
| 100 | summary | SPEC-MULTI-LIMIT-001<br>（MULTI-LIMIT） | messages.py:372-384（multiws.py:552、verify.py:1179、1195）。dimension=commandDefinitionCount | `command定義数が上限{limit}を超過しました` | `コマンド定義数が上限{limit}を超過しました` | §4.1: command=コマンド | 0件 |
| 101 | summary | SPEC-MULTI-LIMIT-001<br>（MULTI-LIMIT） | messages.py:372-384（multiws.py:552、verify.py:1179、1195）。dimension=verifyBindingCount | `verify binding数が上限{limit}を超過しました` | `テスト割当て数が上限{limit}を超過しました` | §3.5の1: binding=テスト割当て（用語集 §8） | 0件 |
| 102 | summary | SPEC-MULTI-MEMBER-001<br>（MULTI-MEMBER） | messages.py:344（multiws.py:206） | `memberの.spec/bitz.yamlがありません` | `メンバーの.spec/bitz.yamlがありません` | §4.1: member=メンバー | 0件 |
| 103 | summary | SPEC-MULTI-MEMBER-001<br>（MULTI-MEMBER） | messages.py:345（multiws.py:229） | `memberの設定workspace.idがcatalogのidと一致しません` | `メンバーの設定キーworkspace.idがカタログのIDと一致しません` | §4.1: member=メンバー、catalog=カタログ。§3.5の2: 設定キーの前に「設定キー」。「カタログのID」は診断レジストリの書き方 | 0件 |
| 104 | summary | SPEC-MULTI-MEMBER-001<br>（MULTI-MEMBER） | messages.py:346（multiws.py:234） | `memberはmultiWorkspaceを宣言できません` | `メンバーは設定キーmultiWorkspaceを宣言できません` | §4.1: member=メンバー。§3.5の2 | 0件 |
| 105 | summary | SPEC-MULTI-OWNERSHIP-001<br>（MULTI-OWNERSHIP） | messages.py:394（multirelate.py:399、423） | `{path}の解決先が{workspace_id}の所有範囲外です` | `パス{path}の解決先がワークスペース{workspace_id}の所有領域の外です` | §3.5の6: 値の前に「パス」「ワークスペース」。用語集 §12: メンバーが所有するパスの範囲=所有領域 | 1件（MULTI-008）；生成器・監査1 |
| 106 | summary | SPEC-MULTI-OWNERSHIP-001<br>（MULTI-OWNERSHIP） | messages.py:398（check.py:142） | `{path}の基準版のsymlinkが{workspace_id}の所有範囲外を指します` | `パス{path}の基準版のシンボリックリンクがワークスペース{workspace_id}の所有領域の外を指します` | §4.1: symlink=シンボリックリンク。§3.5の6、用語集 §12（所有領域） | 1件（MULTI-010）；生成器・監査1 |
| 107 | summary | SPEC-MULTI-OWNERSHIP-001<br>（MULTI-OWNERSHIP） | messages.py:402（check.py:148） | `{path}の現在版のsymlinkが{workspace_id}の所有範囲外を指します` | `パス{path}の現在版のシンボリックリンクがワークスペース{workspace_id}の所有領域の外を指します` | 同上 | 0件 |
| 108 | summary | SPEC-MULTI-PATH-001<br>（MULTI-PATH） | messages.py:351（multiws.py:276） | `member pathの形式が不正です` | `メンバーのパスの形式が不正です` | §4.1: member=メンバー、path=パス | 0件 |
| 109 | summary | SPEC-MULTI-PATH-001<br>（MULTI-PATH） | messages.py:352（multiws.py:390） | `member pathが重複しています` | `メンバーのパスが重複しています` | 同上 | 0件 |
| 110 | summary | SPEC-MULTI-PATH-001<br>（MULTI-PATH） | messages.py:353（multiws.py:398） | `member pathが別のmemberの配下にあります` | `メンバーのパスが別のメンバーの配下にあります` | 同上 | 1件（MULTI-007-01）；生成器・監査1 |
| 111 | summary | SPEC-MULTI-PATH-001<br>（MULTI-PATH） | messages.py:354（multiws.py:319） | `member pathの経路にsymlinkが含まれています` | `メンバーのパスの経路にシンボリックリンクが含まれています` | §4.1: symlink=シンボリックリンク | 0件 |
| 112 | summary | SPEC-MULTI-PATH-001<br>（MULTI-PATH） | messages.py:355（multiws.py:305） | `member pathがGit submoduleです` | `メンバーのパスがGitのサブモジュールです` | §4.1: submodule=サブモジュール | 1件（MULTI-007-02）；生成器・監査1 |
| 113 | summary | SPEC-MULTI-PATH-001<br>（MULTI-PATH） | messages.py:356（multiws.py:311） | `member pathが別のworktreeです` | `メンバーのパスが別のワークツリーです` | §4.1: worktree=ワークツリー | 1件（MULTI-007-03）；生成器・監査1 |
| 114 | summary | SPEC-MULTI-PATH-001<br>（MULTI-PATH） | messages.py:357（multiws.py:324） | `member pathが別のGit repositoryです` | `メンバーのパスが別のGitのリポジトリです` | §4.1: repository=リポジトリ | 0件 |
| 115 | summary | SPEC-MULTI-REF-001<br>（MULTI-REF-UNQUALIFIED） | messages.py:390（multirelate.py:233） | `非修飾の参照先が別workspaceにだけ存在します` | `非修飾の参照先が別のワークスペースにだけ存在します` | §4.1: workspace=ワークスペース | 1件（MULTI-003）；生成器・監査1 |
| 116 | summary | SPEC-MULTI-REF-001<br>（MULTI-REF-WORKSPACE） | messages.py:391（multirelate.py:240） | `修飾workspaceがcatalogに存在しません` | `修飾したワークスペースがカタログに存在しません` | §4.1: workspace=ワークスペース、catalog=カタログ。「修飾したワークスペース」は診断レジストリの書き方 | 0件 |
| 117 | summary | SPEC-MULTI-UNREGISTERED-001<br>（MULTI-UNREGISTERED） | messages.py:364（multiws.py:460） | `Gitが認識する設定fileがcatalogに登録されていません` | `Gitが認識する設定ファイルがカタログに登録されていません` | §4.1: file=ファイル、catalog=カタログ | 2件（MULTI-006、MULTI-030-02）；生成器・監査2 |
| 118 | summary | SPEC-MULTI-VERSION-001<br>（MULTI-VERSION） | messages.py:361（multiws.py:215） | `memberのschemaVersionが未対応majorです` | `メンバーの設定キーschemaVersionのメジャーバージョンが未対応です` | §4.1: member=メンバー、major version=メジャーバージョン。§3.5の2 | 0件 |
| 119 | summary | SPEC-MULTI-VERSION-001<br>（MULTI-VERSION） | messages.py:362（multiws.py:217） | `memberのearsAiが未対応majorです` | `メンバーの設定キーearsAiのメジャーバージョンが未対応です` | 同上 | 0件 |
| 120 | summary | SPEC-PATH-INVALID-001<br>（TRACE-PATH-APPROVED） | messages.py:185（relations.py:377、multirelate.py:407） | `実装pathが存在しません` | `実装パスが存在しません` | §4.1: path=パス | 1件（SINGLE-024）；生成器・監査1 |
| 121 | summary | SPEC-PATH-INVALID-001<br>（TRACE-PATH-APPROVED） | messages.py:187（relations.py:394、multirelate.py:430） | `testのpathが存在しません` | `テストのパスが存在しません` | §4.1: test=テスト、path=パス | 0件 |
| 122 | summary | SPEC-PATH-INVALID-001<br>（TRACE-PATH-DRAFT） | messages.py:186（relations.py:377、multirelate.py:407） | `draftの実装pathは未作成です` | `状態draftの実装パスは未作成です` | §3.5の2: draftは識別子（前に「状態」）、path=パス | 1件（SINGLE-025）；生成器・監査1 |
| 123 | summary | SPEC-PATH-INVALID-001<br>（TRACE-PATH-DRAFT） | messages.py:188（relations.py:394、multirelate.py:430） | `draftのtest pathは未作成です` | `状態draftのテストのパスは未作成です` | §3.5の2: draftは識別子（前に「状態」）、test=テスト、path=パス | 0件 |
| 124 | summary | SPEC-RELATION-ADVISORY-MISSING-001<br>（RELATION-TARGET-MISSING-RELATED） | messages.py:183（relations.py:189、multirelate.py:249） | `relatedの参照先が存在しません` | `関係型relatedの参照先が存在しません` | §3.5の2: relatedは識別子（前に「関係型」） | 1件（SINGLE-090）；生成器・監査1 |
| 125 | summary | SPEC-RELATION-LEGACY-001<br>（RELATION-LEGACY-REFS） | messages.py:182（relations.py:230、multirelate.py:274） | `旧refs fieldは使用できません` | `旧フィールドrefsは使用できません` | §3.5の1・2: field=フィールド、refsは識別子 | 1件（SINGLE-023）；生成器・監査1 |
| 126 | summary | SPEC-RELATION-MISSING-001<br>（RELATION-TARGET-MISSING-STRONG） | messages.py:165、168（relations.py:202、multirelate.py:257） | `strong relationの参照先が存在しません` | `強い関係の参照先が存在しません` | §3.5の1: strong relation=強い関係（用語集 §6.1） | 11件（MULTI-004-01、MULTI-004-02、MULTI-029-03ほか）；生成器・監査6 |
| 127 | summary | SPEC-RELATION-MISSING-001<br>（RELATION-TARGET-MISSING-STRONG） | messages.py:170（制御文字を含む参照元のパスのとき） | `参照元{source_path}のstrong relation参照先が存在しません` | `参照元{source_path}の強い関係の参照先が存在しません` | §3.5の1: strong relation=強い関係。助詞「の」を補い、通常の文と同じ文型にする（§3.5の7） | 1件（SINGLE-076）；生成器・監査1 |
| 128 | summary | SPEC-REPORT-WRITE-001<br>（REPORT-WRITE） | messages.py:239（reportio.py:58） | `report保存先へ排他的に作成できません` | `レポートの保存先へ排他的に作成できません` | §4.1: report=レポート | 2件（SINGLE-072、SINGLE-125-06）；生成器・監査1 |
| 129 | summary | SPEC-REQ-STATEMENT-001<br>（DOC-REQ-STATEMENT-EMPTY） | messages.py:120（document.py:488） | `approved REQに妥当な規範文がありません` | `状態approvedのREQに妥当な規範文がありません` | §3.5の2: approvedは識別子（前に「状態」） | 1件（SINGLE-016）；生成器・監査1 |
| 130 | summary | SPEC-SAFETY-APPROVED-001<br>（CHECK-APPROVED-MEANING） | messages.py:220（basecompare.py:219） | `approved REQの意味変更時にstatusが戻されていません` | `状態approvedのREQの意味変更時に文書の状態が戻されていません` | §3.5の2: approvedは識別子（前に「状態」）。status=文書の状態（用語集 §4） | 3件（MULTI-030-01、SINGLE-031、SINGLE-158）；生成器・監査2 |
| 131 | summary | SPEC-STATE-TRANSITION-001<br>（CHECK-DOCUMENT-DELETED） | messages.py:211（basecompare.py:127） | `管理済みSPECが削除されています` | `管理済みの仕様文書が削除されています` | §3.5の1: SPEC=仕様文書。「管理済みの仕様文書」は診断レジストリの書き方 | 5件（MULTI-018-01、MULTI-018-02、MULTI-030-01ほか）；生成器・監査3、単体試験1 |
| 132 | summary | SPEC-STATE-TRANSITION-001<br>（CHECK-STATE-TRANSITION） | messages.py:214（basecompare.py:144） | `{from_status} {kind}を{to_status}へ戻すことはできません` | `状態{from_status}の{kind}を状態{to_status}へ戻すことはできません` | §3.5の2・6: 状態の値（approvedなど）は識別子。前に「状態」 | 1件（SINGLE-027）；生成器・監査1、単体試験1 |
| 133 | summary | SPEC-STYLE-H1-001<br>（DOC-STYLE-H1） | messages.py:124（document.py:295） | `H1がFrontmatterと一致しません` | `H1がフロントマターと一致しません` | §3.5の1: Frontmatter=フロントマター | 1件（SINGLE-017-01）；生成器・監査1 |
| 134 | summary | SPEC-STYLE-PLACEMENT-001<br>（DOC-STYLE-PLACEMENT） | messages.py:136（document.py:479） | `{kind_label}に規範行を配置できません` | `{kind_label}に規範文を配置できません` | §3.5の1: 用語集の「規範文」（「規範行」は使わない語） | 1件（SINGLE-017-03）；生成器・監査1 |
| 135 | summary | SPEC-STYLE-SECTION-001<br>（DOC-STYLE-SECTION） | messages.py:128（document.py:306） | `REQ必須section {name}がありません` | `REQの必須の節{name}がありません` | §4.2: section=節（「必須の節」）。{name}の前に「節」 | 1件（SINGLE-017-02）；生成器・監査1 |
| 136 | summary | SPEC-STYLE-SECTION-001<br>（DOC-STYLE-SECTION） | messages.py:132（document.py:315） | `REQ必須section {name}が空です` | `REQの必須の節{name}が空です` | §4.2: section=節 | 0件 |
| 137 | summary | SPEC-TASK-BOUNDARY-001<br>（CHECK-TASK-BOUNDARY） | messages.py:195（check.py:212） | `{path}は{task_id}の許可変更path外です` | `パス{path}は{task_id}の変更許可パスの外です` | §3.5の1・6: changes=変更許可パス（用語集 §4）、path=パス。値の前に「パス」（§3.5の6の例文と同じ形） | 3件（MULTI-009、SINGLE-034、SINGLE-120-02）；生成器・監査3 |
| 138 | summary | SPEC-TASK-BOUNDARY-002<br>（CHECK-TASK-NO-GIT） | messages.py:199（check.py:181） | `Git不在のため{task_id}の変更境界を検査できません` | `Git不在のため{task_id}のTASK境界を検査できません` | §3.5の1: 「TASK境界」は用語集 §8の語（「変更境界」は用語集にない） | 1件（SINGLE-038）；生成器・監査1 |
| 139 | summary | SPEC-TEST-COVERAGE-001<br>（TRACE-COVERAGE-INVALID） | messages.py:190（relations.py:488、multirelate.py:503） | `coversが存在しない規範文を参照しています` | `フィールドcoversが存在しない規範文を参照しています` | §3.5の2: coversは識別子（前に「フィールド」） | 1件（SINGLE-026）；生成器・監査1 |
| 140 | summary | SPEC-VERIFY-BLOCKED-001<br>（VERIFY-ARGV-EXPANDED-LIMIT） | messages.py:303（verify.py:702、707） | `{tests}展開後のargvがbyte上限1 MiBを超えます` | `{tests}展開後のargvがバイト数上限1 MiBを超えます` | §4.1: byte=バイト。「バイト数の上限」は診断レジストリの書き方。単独のargvは識別子（ユーザーの決定） | 1件（SINGLE-126-08）；生成器・監査1 |
| 141 | summary | SPEC-VERIFY-BLOCKED-001<br>（VERIFY-BINDING-MISSING） | messages.py:313（verify.py:587） | `command名{name}が設定に定義されていません` | `コマンド名{name}が設定に定義されていません` | §4.1: command=コマンド | 1件（SINGLE-061）；生成器・監査1 |
| 142 | summary | SPEC-VERIFY-BLOCKED-001<br>（VERIFY-CONFIG-UNTRACKED） | messages.py:304（verify.py:673） | `設定fileがGit管理下で未追跡です` | `設定ファイルがGit管理下で未追跡です` | §4.1: file=ファイル | 0件 |
| 143 | summary | SPEC-VERIFY-BLOCKED-001<br>（VERIFY-CWD-UNAVAILABLE） | messages.py:329（verify.py:676） | `command cwdが利用できません` | `コマンドの作業ディレクトリが利用できません` | §4.1・§4.2: command=コマンド、cwd=作業ディレクトリ | 0件 |
| 144 | summary | SPEC-VERIFY-BLOCKED-001<br>（VERIFY-EXECUTABLE-UNAVAILABLE） | messages.py:302（verify.py:714） | `command実行fileをPATHから解決できません` | `コマンドの実行可能ファイルを環境変数PATHから解決できません` | §4.1: command=コマンド、file=ファイル。指示書の注記: 「実行file」は診断レジストリ（VERIFY-EXECUTABLE-UNAVAILABLE）の「実行可能ファイル」にそろえる。§3.5の2: PATHは識別子（前に「環境変数」。§4.1に「環境変数は`PATH`」） | 1件（SINGLE-126-09）；生成器・監査1 |
| 145 | summary | SPEC-VERIFY-BLOCKED-001<br>（VERIFY-EXECUTABLE-UNAVAILABLE） | messages.py:321（verify.py:716） | `command実行fileを解決できません` | `コマンドの実行可能ファイルを解決できません` | 同上 | 0件；生成器・監査1 |
| 146 | summary | SPEC-VERIFY-BLOCKED-001<br>（VERIFY-TEST-OUTSIDE-CWD） | messages.py:305（verify.py:688） | `test pathが実効cwd配下にありません` | `テストのパスが実効の作業ディレクトリの配下にありません` | §4.1・§4.2: test=テスト、path=パス、cwd=作業ディレクトリ。「実効の作業ディレクトリ」は診断レジストリの書き方 | 0件 |
| 147 | summary | SPEC-VERIFY-BLOCKED-002<br>（VERIFY-TARGETS-EMPTY） | messages.py:299（verify.py:974） | `verify対象が0件です` | `検証対象がありません` | §3.5の1: verify対象=検証対象（用語集 §8）。同じ条件ID VERIFY-TARGETS-EMPTYの複合ワークスペース全体の文言（messages.py:367）にそろえる（§3.5の7。注意点の1） | 1件（SINGLE-062）；生成器・監査1 |
| 148 | summary | SPEC-VERIFY-COMMAND-001<br>（VERIFY-SIGNAL） | messages.py:301（verify.py:747） | `commandがsignalで終了しました` | `コマンドがシグナルで終了しました` | §4.1: command=コマンド、signal=シグナル | 1件（SINGLE-058）；生成器・監査1 |
| 149 | summary | SPEC-VERIFY-COMMAND-001<br>（VERIFY-SPAWN-ERROR） | messages.py:300（verify.py:744） | `commandの実行形式をOSが拒否しprocessを生成できません` | `コマンドの実行形式をOSが拒否しプロセスを生成できません` | §4.1: command=コマンド、process=プロセス。OSは§3.3 | 1件（SINGLE-057）；生成器・監査1 |
| 150 | summary | SPEC-VERIFY-TIMEOUT-001<br>（VERIFY-TIMEOUT） | messages.py:309（verify.py:750） | `commandが実効timeout {seconds}秒で終了しませんでした` | `コマンドが実効タイムアウト{seconds}秒で終了しませんでした` | §4.1: command=コマンド、timeout=タイムアウト。実効タイムアウト（用語集 §8）。和文と数字の間に空白を入れない（§7の1） | 3件（SINGLE-059、SINGLE-126-12、SINGLE-126-13）；生成器・監査2 |
| 151 | summary | SPEC-WORKSPACE-UNKNOWN-001<br>（WORKSPACE-ENTRY-UNKNOWN） | messages.py:35（document.py:547、558） | `.spec/内の未知fileをSPECとして読みません` | `.spec/内の未知のファイルを仕様文書として読みません` | §3.5の1: file=ファイル、SPEC=仕様文書。「未知file」は助詞の補い | 1件（SINGLE-083）；生成器・監査1 |
| 152 | stderr | (no-operation) | cliargs.py:296 | `operationを指定してください` | `操作を指定してください` | §3.5の1: operation=操作（用語集 §2「公開操作」、§3.4「操作名」） | 0件（理由の文字列は固定されない） |
| 153 | stderr | (no-operation) | cliargs.py:299 | `未知のoperationです: {op}` | `未知の操作です: {op}` | 同上 | 0件（理由の文字列は固定されない） |
| 154 | stderr | check, context | check.py:723、context.py:428 | `複数の起点が異なるworkspaceに属しています` | `複数の起点が異なるワークスペースに属しています` | §4.1: workspace=ワークスペース | 0件（理由の文字列は固定されない） |
| 155 | stderr | check, context | check.py:726、context.py:431 | `起点のworkspaceと--workspaceが一致しません: {target_ws_id}` | `起点のワークスペースと--workspaceが一致しません: {target_ws_id}` | §4.1: workspace=ワークスペース | 0件（理由の文字列は固定されない） |
| 156 | stderr | check, context, doctor, verify | cliargs.py:56 | `未知のoption形式です: {name}` | `未知のオプション形式です: {name}` | §4.1: option=オプション | 0件（理由の文字列は固定されない） |
| 157 | stderr | check, context, doctor, verify | cliargs.py:85 | `未知のoptionです: {name}` | `未知のオプションです: {name}` | §4.1: option=オプション | 0件（理由の文字列は固定されない） |
| 158 | stderr | check, context, doctor, verify | check.py:755、context.py:460、doctor.py:275、verify.py:844 | `指定したworkspaceが見つかりません: {requested_workspace}` | `指定したワークスペースが見つかりません: {requested_workspace}` | §4.1: workspace=ワークスペース | 0件（理由の文字列は固定されない） |
| 159 | stderr | check, doctor, verify | check.py:631、doctor.py:191、verify.py:1057 | `複合workspaceのroot設定を発見できません` | `複合ワークスペースのルートワークスペースの設定を発見できません` | §4.1: workspace=ワークスペース。root=ルートワークスペース（用語集 §3、§12） | 0件（理由の文字列は固定されない） |
| 160 | stderr | check, verify | cliargs.py:216、242 | `targetの構文が不正です: {t}` | `明示対象の構文が不正です: {t}` | §3.5の1: target=明示対象（用語集 §8。check・verifyの位置引数） | 0件（理由の文字列は固定されない） |
| 161 | stderr | context | cliargs.py:277 | `ADR起点にpurpose={purpose}は指定できません: {t}` | `ADR起点に目的{purpose}は指定できません: {t}` | §3.5の1・2: purpose=目的（用語集 §7）、値implementの前に「目的」 | 0件（理由の文字列は固定されない） |
| 162 | stderr | verify | verify.py:818 | `複数の対象が異なるworkspaceに属しています` | `複数の対象が異なるワークスペースに属しています` | §4.1: workspace=ワークスペース | 0件（理由の文字列は固定されない） |
| 163 | stderr | verify | verify.py:821 | `対象のworkspaceと--workspaceが一致しません: {target_ws_id}` | `対象のワークスペースと--workspaceが一致しません: {target_ws_id}` | §4.1: workspace=ワークスペース | 0件（理由の文字列は固定されない） |

### PR-3 に回した文言

この表では変えない。変更前の文言と場所だけを挙げる。これらの文言にも英語の一般語が残っている（`purpose`、`cancelled`、`verify`、`test`）ので、PR-3 で意味の食い違いを直すときに、§3.5 に合わせて書く必要がある。

| # | 診断コード（条件ID） | 場所 | 変更前の文言 | 固定しているfixture |
|---:|---|---|---|---|
| P1 | CTX-TASK-DEPENDENCY-001（CTX-TASK-DEPENDENCY） | messages.py:245（targetexpand.py:498） | `先行{prereq_task_id}が完了していません` | 3件（SINGLE-051、SINGLE-137、SINGLE-144） |
| P2 | CTX-STATE-001（CTX-STATE-INAPPLICABLE） | messages.py:249（targetexpand.py:410、417、437） | `{doc_id}は現在のpurposeに適用できません` | 3件（SINGLE-146、SINGLE-148、SINGLE-159） |
| P3 | CTX-STATE-001（CTX-STATE-INAPPLICABLE） | messages.py:332（targetexpand.py:417） | `起点{doc_id}はcancelledでありverifyに適用できません` | 1件（SINGLE-067） |
| P4 | CTX-COVERAGE-TEST-001（CTX-COVERAGE-TEST-*） | messages.py:273（context.py:847、857、868、878） | `{modality} {stmt_id}がtestされていません` | 3件（SINGLE-134、SINGLE-142、SINGLE-145） |
| P5 | CTX-COVERAGE-TEST-001（CTX-COVERAGE-TEST-*） | messages.py:316（verify.py:537、543） | `対象{modality} {stmt_id}にtest対応がありません` | 2件（SINGLE-060、SINGLE-064） |
| P6 | CTX-RELATION-TYPE-001（RELATION-TYPE。承認されていない ADR への `requires`） | targetexpand.py:729（messages.py:175 の `relation_type_mismatch` を呼ぶ） | `{source_kind}から{target_kind}への{relation}は許可されません`（出力例: `TASKからADRへのrequiresは許可されません`） | 該当fixture: MULTI-027-01、MULTI-027-02、SINGLE-147、SINGLE-148、SINGLE-149 |
| P7 | CTX-TASK-DEPENDENCY-001 の `suggestedAction` | （現在のCoreにない） | なし。先行TASKが `cancelled` の場合の `suggestedAction` と文言は PR-3 で加える | — |
| P8 | `doctor` の診断の `suggestedAction` の追加（C29） | doctor.py（現在は `SPEC-DOCTOR-WORKSPACE-001` の1件だけが `suggestedAction` を持つ。適合済み） | 追加は PR-3 に回した。既存の1件の文言は §3.5 に合うので変えない。**PR-4 で扱った**（下の PR-4 の節） | — |

P1〜P7 は、下の「2026-10-12: 出力文の見直し PR-3（意味の食い違いの修正）」の節で直した。P8 は、その下の「2026-10-12: 出力文の見直し PR-4（doctorの修復手順）」の節で扱った。

補足: P6 は、行 #7 の関数 `relation_type_mismatch` を共通に使うため、#7 の文型の変更（「関係型{relation}」）が ADR の場合の出力にも及ぶ。PR-3 がこの診断の文言を差し替えるまでは、#7 の変更後の文型で出る。PR-3 の対象のfixture（P1〜P5）は 12 件ある。

### 変更したfixture

- 期待値を変えたfixtureは140件（SINGLE 112、MULTI 28）。承認時の対応表の予測133件に、`MULTI-021-01`〜`MULTI-021-03`、`MULTI-021-05`〜`MULTI-021-08`の7件を加えた。
  この7件は、複合ワークスペースのリソースの上限の超過（`SPEC-MULTI-LIMIT-001`）の診断を、結果のハッシュ値（`resultDigest`）で固定している。
  診断の`summary`が次元の名前を含む（行#95〜#101）ので、`resultDigest`を、生成器`multi_limit_fixtures.py`の`blocked_result`から再計算した。
  fixtureの`description`（`LABELS`）は、Coreの出力ではないので変えていない。
- 期待値の更新は、承認済みの対応表の文言に合わせて、生成器のリテラルとfixtureの期待値（`expected/*`、`manifest.json`の`description`）を同じ置換で直した。
  Coreを実行して期待値を作っていない。`generate`を持つ8つの生成器は、書換え後に再生成して、期待値がバイト一致することを確かめた。

### 固定しない範囲

- 標準エラー出力の`<reason>`の文字列。適合fixtureは接頭辞、1行、理由が空でないこと、端末の制御文字がないことだけを確かめる。
- PR-3に回した文言（上の「PR-3に回した文言」）。
- すでに§3.5に合っていた文言（承認時の対応表で「適合」とした53件）。
- fixtureの`description`のうち、Coreの出力ではないもの。
- 診断の`summary`の文字列を規範文で1つに定めること（ADR-062 Decision 4）。診断コード、重大度、結果への効果、発生元、`evidence`は変えていない。

## 2026-10-12: 出力文の見直し PR-3（意味の食い違いの修正）

### 追加の理由

- 出力文の計画の PR-3。PR-2 で言葉を日本語にした後も、同じ条件IDの診断の文型が操作や経路によって割れたり、診断が原因を表さなかったり、
  目的を取り違えたりする文言が残っていた。上の「PR-3 に回した文言」（P1〜P7）がこれにあたる。
- 表記規則 §3.5の7は、同じ条件IDの診断を、それを返す操作によらず同じ文型にすると定める。次の食い違いがこれに反していた。
  - `CTX-COVERAGE-TEST-001`（C10）: `context`は「{modality} {stmt_id}がtestされていません」、`verify`は「対象{modality} {stmt_id}にtest対応がありません」と割れていた。
  - `CTX-STATE-001`: 経路ごとに「{doc_id}は現在のpurposeに適用できません」と「起点{doc_id}はcancelledでありverifyに適用できません」の2つの文型があった。
- 起点が`cancelled`のTASKのとき、`targetexpand.py`は目的によらず「…verifyに適用できません」の文言を使っていた。目的`implement`で起点にした`context`でも「verify」と出る、
  目的の取り違えである（修正前のCoreで実測し、単体試験で押さえた）。
- 承認されていない（状態が`accepted`でない）ADRへの`requires`の文言は、種別の組合せの誤りと同じ文型で、原因（ADRの状態）が文に現れなかった。
- 先行TASKが完了していないときの文言は、先行TASKの状態を示さず、利用者が次に何をすればよいかも示さなかった。`suggestedAction`は現在のCoreに無かった。

### 管理者の承認

- 2026-10-12、人間の管理者（ユーザー）が、下の表のA〜Eを**このまま承認した**（ADR-062 Decision 2）。
- D・Eは、当初「先行するTASK{prereq}」と提案した。`{prereq}`がTASKのIDそのもの（`TASK-002`）なので「先行するTASKTASK-002」になる誤りが見つかり、
  管理者が同日に「先行する{prereq}」へ直すことを承認した。下の表は直した後の文言である。
- **変更後の文字列は、規範文から一意に導いた値ではなく、表記規則 §3.5に合わせて管理者が承認した値である。**
  期待値の根拠はこの承認済みの表であり、Coreの出力ではない（ADR-051、ADR-062）。

### 承認済みの表

`{…}`は実行時に差し込む値を示す。`{doc_id}`と`{prereq}`は、Coreが従来差し込んでいた値（複合ワークスペースでは修飾ID）をそのまま使う。

| # | 診断（条件ID） | 場所 | 変更前 | 変更後（承認済み） | 固定しているfixture |
|---|---|---|---|---|---|
| A | `CTX-STATE-001`（CTX-STATE-INAPPLICABLE） | messages.py（`state_inapplicable`、`state_task_cancelled`）、targetexpand.py（3か所） | `{doc_id}は現在のpurposeに適用できません`<br>`起点{doc_id}はcancelledでありverifyに適用できません` | `{doc_id}は状態{status}のため目的{purpose}に適用できません`（どの経路も1つの文型。`{status}`は対象の文書の状態、`{purpose}`は操作の目的。`verify`操作からの検査では目的は`verify`） | SINGLE-067、SINGLE-146、SINGLE-148、SINGLE-159（`state_task_cancelled`を廃止し、すべての経路が`state_inapplicable`を使う） |
| B | `CTX-COVERAGE-TEST-001`（CTX-COVERAGE-TEST-SHOULD／MUST／MUST-IMPLEMENT） | messages.py（`coverage_test_untested`、`verify_coverage_untested`） | context: `{modality} {stmt_id}がtestされていません`<br>verify: `対象{modality} {stmt_id}にtest対応がありません` | `対象規範文{modality} {stmt_id}にテスト対応がありません`（`context`と`verify`で同じ） | SINGLE-060、SINGLE-064、SINGLE-134、SINGLE-142、SINGLE-145 |
| C | `CTX-RELATION-TYPE-001`（RELATION-TYPE。承認されていないADRへの`requires`） | relations.py、multirelate.py、targetexpand.py（共通の`type_mismatch_summary`） | `{source_kind}からADRへの関係型requiresは許可されません`（出力は`{source_kind}から{target_kind}への関係型{relation}は許可されません`の形） | `{source_kind}から状態{status}のADRへの関係型requiresは許可されません`（`{status}`はADRの状態）。種別の組合せの誤りの文言（`{source_kind}から{target_kind}への関係型{relation}は許可されません`）は変えない。同じ文型の中で参照先の部分にだけ状態を添える | SINGLE-147、SINGLE-148、SINGLE-149、MULTI-027-01、MULTI-027-02 |
| D | `CTX-TASK-DEPENDENCY-001`（CTX-TASK-DEPENDENCY） | messages.py（`task_dependency_incomplete`）、targetexpand.py | `先行{prereq}が完了していません` | `先行する{prereq}が状態{status}で、状態doneではありません`（`{prereq}`は先行TASKのID、`{status}`はその状態。未完了も`cancelled`も同じ文型） | SINGLE-051（`open`）、SINGLE-137（`open`）、SINGLE-144（`cancelled`） |
| E | `CTX-TASK-DEPENDENCY-001`の`suggestedAction`（新設） | messages.py（`task_dependency_suggested_action`）、targetexpand.py、context.py、verify.py | なし | `先行する{prereq}を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください` | SINGLE-051、SINGLE-137、SINGLE-144 |

- P1 はD、P2・P3はA、P4・P5はB、P6はC、P7はEにあたる。P8（`doctor`の診断の`suggestedAction`の追加。C29）は、この節の範囲に含めない。
- E の`suggestedAction`は、既存の`suggestedAction`を持つ診断（`SPEC-DOCTOR-WORKSPACE-001`）と同じく、結果のスキーマが許す任意のフィールドとして`context`と`verify`の診断に出る。
  テキスト出力と`context`のMarkdown出力は、`suggestedAction`を持つ診断の直後に`  -> `の継続行を1行出す（結果・診断・終了コード §7、`context`仕様 §9.4）。

### 変更したfixture

- 期待値を変えたfixtureは16件（SINGLE 14、MULTI 2）。承認時の予測と一致した。

| fixture | 変えた期待値 | 理由（表の行） |
|---|---|---|
| SINGLE-051 | `summary`、`suggestedAction`の追加、manifestの`description` | D、E |
| SINGLE-137 | `summary`、`suggestedAction`の追加 | D、E |
| SINGLE-144 | `summary`、`suggestedAction`の追加、manifestの`description` | D、E |
| SINGLE-060 | `summary` | B |
| SINGLE-064 | `summary` | B |
| SINGLE-134 | `summary` | B |
| SINGLE-142 | `summary`（`CTX-COVERAGE-TEST-001`の1件） | B |
| SINGLE-145 | `summary` | B |
| SINGLE-067 | `summary` | A（`cancelled`のTASKを起点にした`verify`） |
| SINGLE-146 | `summary` | A（`draft`のREQ-002） |
| SINGLE-159 | `summary` | A（状態`done`のTASKを目的`implement`の起点にする） |
| SINGLE-147 | `summary`、manifestの`description` | C |
| SINGLE-148 | `summary`（型制約の診断と、REQ-002の`CTX-STATE-001`）、manifestの`description` | C、A |
| SINGLE-149 | `summary` | C |
| MULTI-027-01 | `summary` | C |
| MULTI-027-02 | `summary` | C |

- manifestの`description`は、`context_failure_fixtures.py`が診断の`summary`をそのまま説明に使う件（SINGLE-051、144、147、148）で、`summary`と同じ文字列に変わった。
- 入力、状態、終了コード、診断コード、重大度、結果への効果、発生元、`evidence`、コンテキストのハッシュ値は変えていない。
- 期待値の更新は、承認済みの表の文言を生成器（`context_failure_fixtures.py`、`verify_fixtures.py`、`verify_binding_fixtures.py`、`verify_task_root_fixtures.py`、
  `expansion_fixtures.py`、`multi_relation_type_fixtures.py`）のリテラルへ書き、各生成器の期待値の構築関数から`expected/*`とmanifestを書き直した。
  Coreを実行して期待値を作っていない。監査の回帰試験（`test_conformance_audit.py`）のリテラルも、承認済みの文型に直した。
- 参照計算（`multi_relation_type_fixtures.py`の`type_summary`）は、参照先が承認されていないADRなら状態を添え、そうでなければ種別の組合せの文言を返す。

### 固定しない範囲

- 先行TASKが`open`と`cancelled`以外の状態の場合（TASKの状態は`open`、`done`、`cancelled`の3つだけ）。
- ADRの状態が`proposed`以外（`rejected`、`superseded`）の場合の`summary`は、fixtureでは固定しない（単体試験で押さえる）。
- 診断の`summary`と`suggestedAction`の文字列を規範文で1つに定めること（ADR-062 Decision 4）。

## 2026-10-12: 出力文の見直し PR-4（doctorの修復手順）

### 追加の理由

- 出力文の計画の PR-4。[`doctor`仕様](../../docs/03.詳細設計/03_操作仕様/04_doctor.md) §1は、診断に「貼付け可能な最小の修復手順」を付けると定める。
  実際に`suggestedAction`を持つ`doctor`の診断は`SPEC-DOCTOR-WORKSPACE-001`の1件だけだった（実装の確認事項C29）。
- §8に、`SPEC-DOCTOR-CORE-002`（Core実行体を観測できない）と`SPEC-MULTI-DEPENDENCY-001`（根本の原因は別の検査項目の診断にある）を除く
  §8の表の診断のすべてに`suggestedAction`を付けることを明記した（コミット`ae7bdd0c`。文字列そのものは規範文で定めない。ADR-062）。
  §8の表にない、`doctor`が返す設定の診断（`SPEC-CONFIG-SCHEMA-001`など）と複合ワークスペースの診断（`SPEC-MULTI-PATH-001`、`SPEC-MULTI-GIT-001`など）に
  修復手順を付けるかは、ユーザーの決定で実装の確認事項C32として後で決める。
  これは上の「PR-3 に回した文言」のP8にあたる。
- `check`などが返す`SPEC-EARS-VERSION-001`には付けない。`SPEC-DOCTOR-EARS-001`は`doctor`の診断だけに付ける。
- 修復手順を足すと、`SPEC-DOCTOR-PLUGIN-001`の`summary`が末尾に同じ内容を含んでしまうため、`summary`を短くする。

### 管理者の承認

- 2026-10-12、人間の管理者（ユーザー）が、下の表の`suggestedAction`の文言と、`SPEC-DOCTOR-PLUGIN-001`の`summary`の短縮を**このまま承認した**（ADR-062 Decision 2）。
- **変更後の文字列は、規範文から一意に導いた値ではなく、表記規則 §3.5に合わせて管理者が承認した値である。**
  期待値の根拠はこの承認済みの表であり、Coreの出力ではない（ADR-051、ADR-062）。

### 承認済みの表

`{…}`は実行時に差し込む値を示す。`SPEC-DOCTOR-WORKSPACE-001`の既存の`suggestedAction`は変えない。

| 診断（条件ID） | `suggestedAction`（新設、承認済み） | 差し込む値 |
|---|---|---|
| `SPEC-DOCTOR-CORE-001`（DOCTOR-RUNTIME-VERSION） | `CPython 3.12以上でCoreを実行してください` | なし |
| `SPEC-DOCTOR-PLUGIN-001`（DOCTOR-PLUGIN-FORMAT） | `--plugin、--plugin-version、--require-core-apiを同時に指定してください` | なし |
| `SPEC-DOCTOR-API-001`（DOCTOR-API-VERSION） | `範囲{required}を満たすCoreへ更新するか、Core APIのバージョン{core_api}に対応するプラグインを使ってください` | `{required}`は指定した範囲の文字列そのまま（`evidence.required`と同じ）、`{core_api}`はCore APIのバージョン（`1.0`） |
| `SPEC-DOCTOR-CAPABILITY-001`（DOCTOR-CAPABILITY） | `対応機能{missing}を公開するCoreへ更新するか、プラグインの要求を見直してください` | `{missing}`は不足した対応機能の名前を`evidence.missing`と同じ辞書順で「、」で連結したもの |
| `SPEC-DOCTOR-EARS-001`（DOCTOR-EARS-VERSION） | `設定キーearsAiをCoreが対応するメジャーバージョン1に合わせてください` | なし |
| `SPEC-DOCTOR-GIT-001`（DOCTOR-GIT-DEGRADED） | `Git 2.30以上をインストールし、ワークスペースをGitのリポジトリで管理してください` | なし |
| `SPEC-DOCTOR-COMMAND-001`（DOCTOR-COMMAND-CWD） | `設定キーverify.commands.{name}.cwdのディレクトリを作成するか、正しいパスを指定してください` | `{name}`はコマンド名（発生元の`key`と同じ名前） |
| `SPEC-DOCTOR-COMMAND-001`（DOCTOR-COMMAND-FILE） | `設定キーverify.commands.{name}.argvの先頭の実行可能ファイルをインストールするか、正しいパスを指定してください` | 同上 |

あわせて承認した変更: `SPEC-DOCTOR-PLUGIN-001`の`summary`を「プラグインの要求が不完全です。--plugin、--plugin-version、--require-core-apiを同時に指定してください」から
**「プラグインの要求が不完全です」**へ短くする（修復手順と重なるため）。

### 変更したfixture

- 期待値を変えたfixtureは9件（SINGLE 7、MULTI 2）。承認前の予測と一致した。`SINGLE-002`（`SPEC-DOCTOR-WORKSPACE-001`）は既存の`suggestedAction`を変えないので対象外である。
  `SPEC-DOCTOR-CORE-001`と`SPEC-DOCTOR-EARS-001`を固定するfixtureは現在ない。単体試験で押さえる。
  （2026-10-12追記: `SPEC-DOCTOR-EARS-001`は、その後の実装の確認事項C31の修正で追加した`MULTI-033`が、`doctor --all-workspaces`の全体事前検査の経路で固定する。）

| fixture | 診断 | 変えた期待値 |
|---|---|---|
| SINGLE-006-01 | `SPEC-DOCTOR-COMMAND-001`（実行ファイル） | `suggestedAction`の追加（`{name}`は`default`） |
| SINGLE-006-02 | `SPEC-DOCTOR-COMMAND-001`（作業ディレクトリ） | `suggestedAction`の追加（`{name}`は`default`） |
| SINGLE-093 | `SPEC-DOCTOR-GIT-001` | `suggestedAction`の追加 |
| SINGLE-127-15 | `SPEC-DOCTOR-GIT-001` | `suggestedAction`の追加 |
| SINGLE-161 | `SPEC-DOCTOR-API-001` | `suggestedAction`の追加（`{required}`は`>=1.1`） |
| SINGLE-162 | `SPEC-DOCTOR-CAPABILITY-001` | `suggestedAction`の追加（`{missing}`は`context.v2`） |
| SINGLE-163 | `SPEC-DOCTOR-PLUGIN-001` | `suggestedAction`の追加、`summary`の短縮 |
| MULTI-026-02 | `SPEC-DOCTOR-COMMAND-001`（実行ファイル） | `suggestedAction`の追加（`{name}`は`backend`）、テキストの期待値に`  -> `の継続行の追加 |
| MULTI-032 | `SPEC-DOCTOR-API-001` | `suggestedAction`の追加（`{required}`は`^2.0`） |

- 入力、状態、終了コード、診断コード、重大度、結果への効果、発生元、`evidence`、検査項目、manifest、副作用の期待値は変えていない。
- 期待値の更新は、承認済みの表の文言を生成器・監査（`doctor_plugin_fixtures.py`、`registry_closure_fixtures.py`、`environment_fixtures.py`、`multi_doctor_fixtures.py`、
  `initial_fixtures.py`）のリテラルへ書き、`expected/*`を書き直した。Coreを実行して期待値を作っていない。
  `doctor_plugin_fixtures.py`の参照計算は、承認済みの文型へ`evidence`の値を差し込んで求め、リテラルとの一致を要求する。
  `generate`を持つ`doctor_plugin_fixtures.py`は再生成して差分が期待値の行だけであること、`PYTHONHASHSEED`を変えても同じことを確かめた。
- 監査の回帰試験（`test_conformance_audit.py`）に、`suggestedAction`の欠落、別の条件の文言との取り違え、旧`summary`の復活、テキストの継続行の欠落を拒否する変異を足した。

### 固定しない範囲

- `SPEC-DOCTOR-CORE-001`（CPythonの下限未満）、`SPEC-DOCTOR-EARS-001`、複数の対応機能の連結（辞書順）の文字列。fixtureがなく、単体試験
  （`tests/bitz-core/test_doctor_suggested_action.py`）で押さえる（`SPEC-DOCTOR-EARS-001`の全体事前検査の経路は、2026-10-12に追加した`MULTI-033`が固定する）。
- `SPEC-DOCTOR-CORE-002`と`SPEC-MULTI-DEPENDENCY-001`に`suggestedAction`を付けないこと（`SPEC-DOCTOR-CORE-002`はCoreが返す経路を持たない。`SPEC-MULTI-DEPENDENCY-001`は根本の原因が別の検査項目の診断にある）。
- 診断の`summary`と`suggestedAction`の文字列を規範文で1つに定めること（ADR-062 Decision 4）。

## 2026-10-18: 単独操作の全体事前検査の文言の追加（ADR-063）

### 追加の理由

- 実装の確認事項C27の修正で、複合ワークスペースの単独の`context`、`check`、`verify`は、Gitが認識する設定を列挙せず、
  選択した最も近い設定だけをカタログと照合するようになった（ADR-063 決定2）。この照合で未登録と判定したときの
  `SPEC-MULTI-UNREGISTERED-001`（`MULTI-UNREGISTERED`）の`summary`が新たに要る。
- 既存の行#117「Gitが認識する設定ファイルがカタログに登録されていません」は、Gitが認識する設定の比較の文言であり、
  選択した設定の照合には当てはまらない。

### 管理者の承認

- 2026-10-18、人間の管理者（ユーザー）が、次の文言を承認した（ADR-062 Decision 2、ADR-063 決定7）。既存の行#117と同じ文型であり、
  既存のfixtureの期待値は変えない。
- **この文字列は、規範文から一意に導いた値ではなく、表記規則 §3.5に合わせて管理者が承認した値である。**

| 種類 | 診断（条件） | Coreの位置 | 文言 | 固定しているfixture |
|---|---|---|---|---|
| summary | `SPEC-MULTI-UNREGISTERED-001`（`MULTI-UNREGISTERED`、選択した設定の照合） | `messages.py`の`MULTI_UNREGISTERED_SELECTED` | `選択した設定ファイルがカタログに登録されていません` | `MULTI-036-01`、`MULTI-036-02`、`MULTI-036-13`；生成器・監査`multi_single_precheck_fixtures.py` |

- 単独の`doctor`で、Gitが認識する設定の比較と選択した設定の照合が同じパスを見つけた場合は、1つの元の原因から同義の診断を複数生成しない
  （診断レジストリ §2）ため、Gitが認識する設定の比較の文言の1件だけを返す。この組合せは単体試験（`tests/bitz-core/test_multi_single_precheck_stop.py`）で押さえる。

## 2026-10-18: 複合ワークスペースの除外の文言の追加（ADR-064）

### 追加の理由

- ルートワークスペースの設定に`multiWorkspace.exclude`を置けるようにした（ADR-064）。除外のパスの不正と、メンバーのパスが除外した範囲にあることを
  診断にするため、`SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`）と`SPEC-MULTI-PATH-001`（`MULTI-PATH`）の`summary`が新たに要る。
- 既存の`SPEC-MULTI-PATH-001`の文言（「メンバーのパスが別のメンバーの配下にあります」）は、メンバーどうしの入れ子の文言であり、除外には当てはまらない。
  `SPEC-MULTI-CONFIG-001`は、これまでfixtureに現れない。

### 管理者の承認

- 2026-10-18、人間の管理者（ユーザー）が、次の7件の文言を承認した（ADR-062 Decision 2、ADR-064 決定8）。
- **この文字列は、規範文から一意に導いた値ではなく、表記規則 §3.5に合わせて管理者が承認した値である。**

| 種類 | 診断（条件） | Coreの位置 | 文言 | 固定しているfixture |
|---|---|---|---|---|
| summary | `SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、`exclude`が文字列の配列でない） | `messages.py`の`MULTI_CONFIG_EXCLUDE_TYPE` | `設定キーmultiWorkspace.excludeは文字列の配列で指定してください` | `MULTI-037-14`；生成器・監査`multi_exclude_fixtures.py` |
| summary | `SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、`exclude`が100件を超える） | `messages.py`の`MULTI_CONFIG_EXCLUDE_COUNT` | `設定キーmultiWorkspace.excludeは100件以下で指定してください` | `MULTI-037-15` |
| summary | `SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、除外のパスの字句の不正。`..`、末尾の`/`など） | `messages.py`の`MULTI_EXCLUDE_INVALID` | `除外のパスの形式が不正です` | `MULTI-037-09`、`MULTI-037-10` |
| summary | `SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、除外のパスの重複） | `messages.py`の`MULTI_EXCLUDE_DUPLICATE` | `除外のパスが重複しています` | `MULTI-037-11`、`MULTI-037-18` |
| summary | `SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、除外のパスが別の除外のパスの配下） | `messages.py`の`MULTI_EXCLUDE_NESTED` | `除外のパスが別の除外のパスの配下にあります` | `MULTI-037-12` |
| summary | `SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、名前が`.spec`のセグメントを含む除外） | `messages.py`の`MULTI_EXCLUDE_SPEC` | `除外のパスに.specが含まれています` | `MULTI-037-13` |
| summary | `SPEC-MULTI-PATH-001`（`MULTI-PATH`、メンバーのパスが除外のパスと同じ、またはその配下） | `messages.py`の`MULTI_PATH_EXCLUDED` | `メンバーのパスが除外した範囲にあります` | `MULTI-037-16`、`MULTI-037-17` |

- `suggestedAction`は付けない。複合ワークスペースの診断は`doctor`仕様 §8の表の診断ではないので、`doctor`でも`suggestedAction`を付けない（`doctor`仕様 §8）。
- 既存のfixtureの期待値は変えない。
- 同日、`multiWorkspace`が設定不適合なら除外を信用しない規則を固定する`MULTI-037-24`〜`27`は、2026-10-12の対応表の承認済みの文言（行#86「設定キーmultiWorkspace.membersは1件以上指定してください」、
  行#87「…membersは配列で指定してください」、行#89「設定キーmultiWorkspace.maxMembersは1〜100の整数で指定してください」）を期待値に使う。新しい文言の承認ではない。

## 2026-10-25: 複合ワークスペースのルートのworkspace.idの省略の文言の追加（C42）

### 追加の理由

- 実装の確認事項C42の修正で、複合ワークスペースのルートの設定が`workspace.id`を省略した場合を、既定値`root`をルートのIDとして通さず、
  全体事前検査で`SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、ルートの条件）の1件だけで止めるようにした。複合ワークスペース仕様 §2は、ルートワークスペースと
  全メンバーで`workspace.id`を必須とし、結果・診断・終了コード §2は複合ワークスペースでは既定値`root`を有効なIDとみなさないと定める（§4.1の写像は`multiWorkspace`のない基準版との比較だけ）。
- 既存の`SPEC-MULTI-CONFIG-001`の文言（行#85〜#89、2026-10-18の除外の7件）は、`multiWorkspace`の型・件数・除外のパスの文言であり、ルートの`workspace.id`の省略には当てはまらない。

### 管理者の承認

- 2026-10-25、人間の管理者（ユーザー）が、次の1件の文言を承認した（ADR-062 Decision 2）。
- **この文字列は、規範文から一意に導いた値ではなく、表記規則 §3.5に合わせて管理者が承認した値である。**

| 種類 | 診断（条件） | Coreの位置 | 文言 | 固定しているfixture |
|---|---|---|---|---|
| summary | `SPEC-MULTI-CONFIG-001`（`MULTI-CONFIG`、ルートの設定が`workspace.id`を省略） | `messages.py`の`MULTI_CONFIG_ROOT_ID_REQUIRED` | `ルートワークスペースの設定キーworkspace.idがありません` | `MULTI-043-01`〜`09`、`MULTI-043-17`、`MULTI-043-18`；生成器・監査`multi_workspace_id_fixtures.py` |

- `source`は`{"kind": "file", "workspaceId": null, "path": ".spec/bitz.yaml", "key": "workspace.id"}`である。ルートのIDを構成できないので`workspaceId`は`null`（結果・診断・終了コード §5）。
- `suggestedAction`は付けない。複合ワークスペースの診断は`doctor`仕様 §8の表の診断ではないので、`doctor`でも`suggestedAction`を付けない（`doctor`仕様 §8）。
- メンバーの`workspace.id`の省略は、既存の承認済みの文言（行#103「メンバーの設定キーworkspace.idがカタログのIDと一致しません」、`SPEC-MULTI-MEMBER-001`）を再利用する。
  新しい文言の承認ではない。`MULTI-043-10`、`MULTI-043-11`がこの文言を期待値に使う。
- 既存のfixtureの期待値は変えない（既存のfixtureのルートは、すべて`workspace.id`を明示している）。
- 同日に足した`MULTI-043-13`〜`16`（ルートが`workspace.id`を省略したまま版の非対応で止まる）は、既存の承認済みの文言（`summary`は行#31・#45の版の非対応の`SPEC-CONFIG-SCHEMA-001`・`SPEC-EARS-VERSION-001`・`SPEC-DOCTOR-EARS-001`、`suggestedAction`は2026-10-12のPR-4の`SPEC-DOCTOR-EARS-001`。`MULTI-033`・`MULTI-040-02`が固定済み）を期待値に使う。新しい文言の承認ではない。

### 固定しない範囲

- ルートの`workspace`が空のマッピング（`workspace: {}`）や`id`が文字列でない場合の文言。この群は`workspace`キーそのものを持たない形だけを固定する。

## 2026-10-26（2026-10-27 適用）: SPEC-TEST-COVERAGE-001 の文言の拡張（C67）

### 変更の理由

- 実装の確認事項C67。`SPEC-TEST-COVERAGE-001`（`TRACE-COVERAGE-INVALID`）の`summary`は、Coreでは参照先が存在しない場合だけでなく、実在するが`covers`に指定できない参照
  （`refines`で直接参照していない規範文など。複合ワークスペース仕様 §4、文書・フロントマター・状態仕様 §5）にも使っている。
  旧い文言「フィールドcoversが存在しない規範文を参照しています」は、後者には意味が合わない。
- 診断レジストリの`TRACE-COVERAGE-INVALID`の条件の説明に「対応できない参照」を加えた（`f92583d7`）。
- 補強の規範は、表記規則 §3.5の7（同じ条件IDの診断は、同じ文型にする）である。

### 管理者の承認

- 2026-10-26、人間の管理者（ユーザー）が、次の文言を承認した（ADR-062 Decision 2）。適用は2026-10-27である。
- **この文字列は、規範文から一意に導いた値ではなく、管理者が承認した値である。一字も変えない。**

| 種類 | 診断（条件） | Coreの位置 | 旧い文言 | 新しい文言 | 固定しているfixture |
|---|---|---|---|---|---|
| summary | `SPEC-TEST-COVERAGE-001`（`TRACE-COVERAGE-INVALID`） | `messages.py`の`TEST_COVERAGE_INVALID` | `フィールドcoversが存在しない規範文を参照しています` | `フィールドcoversの参照先が存在しないか、対応できません` | `SINGLE-026`、`MULTI-046-03`（2件）；生成器・監査`trace_fixtures.py`、`multi_self_qualified_covers_fixtures.py` |

- 変えたfixtureは`SINGLE-026`（`expected/check.json`と`manifest.json`の`description`）と`MULTI-046-03`（`expected/check.json`の`diagnostics`2件）の2件である。
  入力、状態、終了コード、`source`、`evidence`は変えていない。
- 2026-10-12の承認済みの対応表の行#139の「訂正後」の文言（`フィールドcoversが存在しない規範文を参照しています`）は、そのときの履歴として残し、変えない。
  現在の文言は、この節が正である。
- 期待値の訂正の記録は[適合fixture検証記録](適合fixture検証記録.md)に置く。

### 固定しない範囲

- 「参照先が存在しない」場合と「対応できない」場合の`summary`を、別の文言に分けることは固定しない。この2つは同じ条件IDなので、同じ文型の1つの文言で扱う。
