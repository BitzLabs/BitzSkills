# BOM・Frontmatter fixture review

2026-09-14。SINGLE-081、082、084〜088の11件を追加する。
根拠は[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[文書・Frontmatter仕様](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の各matrix IDである。

| ID | 唯一の条件 | status／終了コード | 検査文書／句 |
|---|---|---|---|
| SINGLE-081 | 設定先頭のUTF-8 BOM | passed_with_warnings／0 | 1／1 |
| SINGLE-082 | SPEC先頭のUTF-8 BOM | passed_with_warnings／0 | 1／1 |
| SINGLE-084 | REQにTASK専用changes | passed_with_warnings／0 | 1／1 |
| SINGLE-085 | 未知のfutureOption field | passed_with_warnings／0 | 1／1 |
| SINGLE-086 | titleのflow sequenceが未閉鎖 | failed／1 | 0／0 |
| SINGLE-087-01 | titleのcustom tag | failed／1 | 0／0 |
| SINGLE-087-02 | titleのanchor | failed／1 | 0／0 |
| SINGLE-087-03 | titleのalias | failed／1 | 0／0 |
| SINGLE-087-04 | merge key | failed／1 | 0／0 |
| SINGLE-087-05 | 同値のtitle重複 | failed／1 | 0／0 |
| SINGLE-088 | titleが整数 | failed／1 | 0／0 |

共通入力は既存の有効なREQ文書1件と最小設定。文書・句の欠落や関係切れを混ぜない。
BOMは片方のfileだけへbyteで付け、warning後も文書と規範文を検査する。BOM除去は解析上だけであり、fileは変更しない。
changesと未知fieldは無視して解析を続ける。changesに記したpathはREQのTASK境界やpath検査へ渡さない。
構文・禁止構文・型不正はskip-documentで、本文のH1や規範文検査へ進まずSchema診断1件だけにする。
aliasはanchorを同居させず、alias token自体の禁止を検査する。未定義aliasの解決を試みる前に拒否するため、
別の参照解決Diagnosticは出さない。merge keyは空mappingを使い、anchor/aliasを同居させない。
重複keyは同値を使い、後勝ち・同値許容の実装も不適合とする。

全件で有効設定からworkspace rootが確定する。BOM診断sourceは対象fileだけ、Frontmatter診断は該当keyを付ける。
line/column、証跡、suggestedActionはこの期待値では付加しない。診断summaryは期待JSONの文字列を固定する。
Schema不正時は文書を完全検査できないため件数0、warning時は完全検査できるため件数1である。

入力byte列・manifest・完全結果・副作用Schemaを検証し、隔離Git repositoryを2回setupして固定snapshotへ照合する。
baselineへ入力をcommitし、変更保護やunbornの縮退を混ぜない。report・cache等への書込みは許可しない。
回帰試験は警告の削除、件数・診断code・statusの改変、二重診断、副作用の許容と、各不正入力の修復を拒否する。
検証用YAML parserやCoreは実装しない。禁止構文の拒否、BOM後の継続、実副作用はGate Bで受け入れる。
