# Diagnostic順序fixtureレビュー

SINGLE-077はTECH-001、TECH-002、TECH-010の3文書それぞれに同じstrong requires先TECH-999の不在を置く。
各文書のrefinesとtestsは有効で、同一workspace内のtest参照共有は許可される。入力は既存SINGLE-070-02を拡張し、
REQ 1件、ADR 1件、TECH 3件の計5文書、規範文2句を完全検査する。失敗後も独立文書を検査するため
SPEC-RELATION-MISSING-001を3件返し、statusはfailed／1とする。

根拠は[結果契約 §7](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#7-textとjson)と
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)のSINGLE-077。
workspace、line/columnの有無、codeは共通で、sort keyの最初の差はpathである。
期待順はTECH-001.md、TECH-002.md、TECH-010.md。追加文書の生成順はTECH-010、TECH-002と逆にし、
期待値を生成順へ依存させない。line/columnは未付与の空field、specRefsも未付与とする。
この実入力はpathが異なる場合を検証し、同一pathでline/columnだけが異なるケースや連合workspace差は対象外。

JSONの配列順とtextの行順を完全固定し、要約はtargets=5、diagnostics=3。
既存reportを保持し、新規書込みを許可しない。各2回の隔離setupと固定snapshotを比較し、
回帰試験では配列逆転、Diagnostic欠落、文書件数の不足を拒否する。
Coreは実行せず、実際の検査継続と列挙順不変性はGate Bで受け入れる。
