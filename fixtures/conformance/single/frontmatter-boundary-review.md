# Frontmatter境界fixtureレビュー

2026-09-17。SINGLE-114〜119と120-03、120-04の20件を追加する。
根拠は[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[文書・Frontmatter仕様](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の各matrix IDと
`frontmatter.schema.json`である。

| ID | 唯一の条件 | status／終了コード | 検査文書／句 | Diagnostic key |
|---|---|---|---|---|
| SINGLE-114 | REQの`tests` object配列 | passed／0 | 1／1 | — |
| SINGLE-115-01 | 最小REQ | passed／0 | 1／1 | — |
| SINGLE-115-02 | 最小TECH | passed／0 | 1／0 | — |
| SINGLE-115-03 | 最小ADR | passed／0 | 1／0 | — |
| SINGLE-115-04 | `changes`省略の最小TASK | passed／0 | 1／0 | — |
| SINGLE-116-01 | titleが120 code point | passed／0 | 1／1 | — |
| SINGLE-116-02 | titleが121 code point | failed／1 | 0／0 | `title` |
| SINGLE-116-03 | titleが空string | failed／1 | 0／0 | `title` |
| SINGLE-116-04 | titleが空白だけ | failed／1 | 0／0 | `title` |
| SINGLE-116-05 | titleが改行を含む | failed／1 | 0／0 | `title` |
| SINGLE-117-01 | title欠落（`SPEC-FM-REQUIRED-001`） | failed／1 | 0／0 | `title` |
| SINGLE-117-02 | titleがnull | failed／1 | 0／0 | `title` |
| SINGLE-117-03 | `tests[0].covers`が空配列 | failed／1 | 0／0 | `tests[0].covers` |
| SINGLE-118-01 | `relations.related`の値重複 | failed／1 | 0／0 | `relations.related` |
| SINGLE-119-01 | `relations`内の未知key | failed／1 | 0／0 | `relations.future` |
| SINGLE-119-02 | `tests[]`内の未知key | failed／1 | 0／0 | `tests[0].future` |
| SINGLE-119-03 | top-level未知field（`SPEC-FM-UNKNOWN-001`） | passed_with_warnings／0 | 1／1 | `future` |
| SINGLE-119-04 | `x-reviewed`拡張field | passed／0 | 1／1 | — |
| SINGLE-120-03 | REQに正しい型の`changes`（`SPEC-FM-UNAVAILABLE-001`） | passed_with_warnings／0 | 1／1 | `changes` |
| SINGLE-120-04 | REQに型不正の`changes` | failed／1 | 0／0 | `changes` |

明記のないfailedは`SPEC-FM-SCHEMA-001`だけを持つ。検査句はREQの規範文1件だけであり、TECH、ADR、TASKは0件である。

共通入力は最小設定と対象文書1件である。各fieldをJSON構文のYAML flow valueとして1行ずつ書く。
auditはその行を`json.loads`で独立にdecodeし、期待fieldと一致すること、
`frontmatter.schema.json`の種別definitionの合否がfailed期待と一致することを確認する。
H1は有効なtitleと一致させ、failed時は固定titleを使う。title長以外の独立原因を混ぜないためである。
`tests`を持つ場合だけtest fileと`default` command bindingを置く。test fileは実行されると例外を送出し、
checkがtestを実行しないことを入力側でも示す。

実行は`check --full --base HEAD --format json`とし、入力をbase commitへ入れてGit縮退や変更保護を混ぜない。
副作用はread-onlyとし、before／afterを同一に固定する。隔離repositoryを2回setupし、固定snapshotと相互の一致を検査する。
回帰試験では、status、件数、診断コードの改変、二重診断、診断の削除、cache書込みの許容、
121 code point titleの境界内への修復をいずれも拒否する。

matrix同範囲のSINGLE-118-02、118-03、120-01、120-02は含めない。118系はtest要素のkey tuple比較、
120-01／02は明示TASK checkとworktree差分のsetupが要るため、別batchで扱う。
検証用YAML loaderやCoreは実装しない。実YAML解析と拒否順序はStep 2のGate Bで受け入れる。
