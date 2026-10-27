# Phase 4：契約束縛・一次台帳とCLI宣言検査

固定source10 `abfdb8f4aba25a3f4e6b56ec259c29896983a196` の公開コンポーネントを独立SOLで検分し、P1=0/P2=0。
検分者は最初の対象コード読取り前と保存前にsource10を照合した。
親も対象21件を実再実行し、原ログ/hash/予約/source/レシートを照合した。

| 実行者・対象 | 実出力 | exit |
|---|---|---|
| 親・確定source、clean全skills | Ran 341 tests in 60.758s / OK | 0 |
| 独立SOL・台帳 | Ran 13 tests in 0.161s / OK | 0 |
| 独立SOL・プローブ | Ran 8 tests in 0.001s / OK | 0 |
| 独立SOL・全skills | Ran 341 tests in 60.825s / OK | 0 |
| 親・対象再実行 | Ran 21 tests in 0.151s / OK | 0 |

入力はケース/catalog/manifest/共通指示/環境の原bytes hashを固定契約へ束縛する。
モデルpayloadは共通指示/catalogとprompt/contextだけで、case ID・期待値・controlは投影しない。
初期公開canary用の最大2ケース×2反復。台帳はgit-common-dirの共通場所へ固定し、起動前に排他予約する。
並行予約・再起動・campaign/入力/出力先変更による枠回避を拒否し、未検分・停止後は後続を予約しない。

台帳はproviderを起動せず、sourceの実行時一致や受入れ証拠の意味・原bytes・独立性を認定しない。
それらは製品接続側の親監査で確認し、その結果だけを台帳へ渡す。storage指定は合成試験用、製品はopen_ledgerを使う。

無課金の実CLIプローブ2条件はどちらも停止した。外部network遮断/home遮蔽、ローカル模擬Responses最大1要求/条件。
模擬turn完了/server exit0を実モデルの成功と扱わない。
初版はtop-level toolsだけを検査しinput.additional_toolsを見落とした。原を上書きせず再解析を別保存した。
追加欄にはfunctions.execとcollaboration.spawn_agent等の10宣言が残る。
feature=falseの指定だけをtool除外の成功と扱わず、検証した2条件を有料一次へ接続しない。
この停止は2条件に限定し、他の版/設定を含めた不可能性の証明へ拡張しない。
provider stderrは原bytesとhashだけを扱い、復号・出力していない。

次の接続調査用に公式tag rust-v0.160.1のsource `d27764b82f7118f674371e6d6e76271d9d606edb` をrepo内へ取得した。
tool modeや複数agentをmodel情報が選ぶ箇所、tool登録前のToolPolicy.allowed_toolsの制限APIを確認した。
専用adapterやモデル情報の別設定はまだビルド/通信検証しておらず、有料一次の起動条件に使わない。

独立SOL消費1/残0、一次0/有料自動retry0/追加委譲0。今回の公開コード検分にはprovider原bytesがない。
コンポーネント確認をPhase完了、native provider・行動・Skill Gate・製品完了へ拡張しない。
Core/fixtureの変更はなく、Gate A/B再認定対象ではない。

原証拠は `.venv/production-infrastructure-review-01/`、公開summaryにhashを固定した。
`verify-parent-artifacts.py` は原ログ・予約・guard・公開元プローブを再照合する。原証拠がなければ停止する。
次は読取り2toolだけを提供するCLI接続方式の実装・無課金通信検証と、起動前独立検分・別有限canary契約である。
