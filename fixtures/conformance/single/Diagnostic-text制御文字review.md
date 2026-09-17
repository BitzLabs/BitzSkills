# Diagnostic text制御文字の裁定とfixture

ユーザー承認により、Diagnosticのtext表示field内のC0、DEL、C1をbackslash 1文字＋u＋小文字16進4桁へ
変換する。LF/TABも可視化し、Diagnosticを1行に保つ。規範は
[結果契約 §7](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#7-textとjson)へ反映した。
JSON値とreport、sort順序は変えず、行形式自体の改行・字下げも変えない。
process抜粋のLF/TAB保持規則は別の契約であり変更しない。

SINGLE-076はSINGLE-075-02の単一strong relation不在を使う。隔離setupでTECH-001のfile名slugに
ESC＋[31m、TAB、DEL、C1 U+0085を含めてrenameする。Frontmatter IDと本文は不変であり、
余計なfile名ID不一致や参照不正は生じない。実repositoryには制御文字を含むfile名をcommitせず、
manifestのJSON escapeから隔離treeだけに生成する。基準commit後のrenameなのでrevision.dirtyはtrue。

summaryは参照元pathを含む説明を今回の固定値として選択した。pathとsummary双方で制御文字の可視化を確認する。
期待JSONには元のcode pointを保持し、期待textにだけ可視escapeを置く。出力は要約＋Diagnosticの2行。
LF/TAB等すべての制御範囲、隣接する可視文字、既存backslash、非ASCII文字はfixture側referenceの回帰試験で確認する。
NULをfile名に使う試験ではない。report生成0件で、Git status/indexを含むbefore/afterは一致させる。

Schema・完全結果・入力byte列・2回の隔離setupを検証する。Diagnostic registryの条件・severity・statusには
変更がなく、意味網羅台帳は結果契約の参照hashだけを更新した。
Coreの表示実装は追加せず、実際の標準出力と副作用はGate Bで検証する。
