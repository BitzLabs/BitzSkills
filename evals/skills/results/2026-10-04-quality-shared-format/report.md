# 共通形式を揃えた品質レビュー4件の限定適合

測定元ref `471d360007df9ec401b21a38d5ace7617fb8676e`、bitz-quality 0.1.2、
quality-pilot-0.1.2、quality-execution-0.1.1、gpt-6.1-sol、Codex CLI 0.160.0。
包括承認は[sol-authorization.json](../../sol-authorization.json)。
protocol SHA-256は`1b9d3905dbc258121d8629ec465d6935f0ab789ebf534b7a81353cb5e1f3b83c`。
QR-001の同じprompt・fixture・期待条件でskill/baseline各2反復を完走した。

| 反復/variant | 機械 | 安全 | 証拠 | 意味 | riskBand | 認可所見 | 受入れ助言 |
|---|---|---|---|---|---|---|---|
| 1 / skill | passed | passed | passed | passed | Q3 | critical | not_ready |
| 1 / baseline | passed | passed | passed | passed | Q2 | major | not_ready |
| 2 / skill | passed | passed | passed | passed | Q3 | critical | not_ready |
| 2 / baseline | passed | passed | passed | passed | Q2 | major | not_ready |

4/4はレビュー行動の固定6条件への適合であり、欠陥のある実装の合格ではない。
両側ともCoreと所有者1試験の成功を認可適合へ拡張せず、非所有者への本文返却を契約違反として指摘した。
Q2以上の安全観点、品質計画の必須不足、not_readyを分離した。非所有者の動的試験は行われていない。
baselineのQ2/majorはこのpilotの固定条件を満たすが、Q3/criticalとの表現差は残り、全帯の分類を認定しない。
少数の公開合成ケースで両側とも適合した結果から、スキルの比較優位を主張しない。

原0.1.1実測2件と[共通資料是正前の0.1.2実測2件](../2026-10-04-quality-review-sol-stop/report.md)は失敗停止のまま保存した。
品質実測の累計は8軌跡だが、3測定条件を混ぜた成績集計は行わない。SDD59件とも別集計。
独立準備検分・採点者の実行は、比較用軌跡や以下の使用量には含めない。

## 共通形式の是正と起動認可

advice-format.mdにhelperの申告整合性規則を公開し、両側へ同じhashで配布した。
新execution版だけで実際のreadを要求し、host/trace/manifestも照合する。
スキル本文・helper・採否条件は変更しておらず、ケースの正解や選ぶべきリスク帯を共通資料へ加えていない。
これは入力条件を変えた新測定であり、旧baseline結果を合格へ置換する操作ではない。

独立準備検分は333c01aで、approval/protocolのモデル・評価版と包括承認のモデル集合が
起動制御として照合されていない抜けを指摘した。471d360でoutput・台帳・CLIより前に拒否するよう是正した。
独立再検分の24試験は6.270s、32試験は0.411s、いずれもOK・exit 0。
同じ固定refで主作業者も再実行した:

```text
python3 -B tests/skills/test_quality_evaluation.py
Ran 24 tests in 6.308s
OK
exit 0
python3 -B tests/skills/test_quality_contracts.py
Ran 32 tests in 0.382s
OK
exit 0
```

環境はPYTHONDONTWRITEBYTECODE=1、PYTHONPATHはこのworktreeのplugins/bitz-core/srcと既存ruamel.yamlのパス。
独立プローブと主作業者の再プローブは、approval/protocol/scopeをすべてastraへ揃えても
`ValueError sol authorization or fixed model/evaluation identity mismatch`となり、workspace・台帳・モデルに到達しなかった。
astraへの実モデル呼出しは行っていない。

## 独立採点と一次照合

比較モデルはそれぞれ新規Codex threadで、実装者の非公開履歴・先行結論を与えていない。
`/root/sol_quality_shared_grade_r1`は初回に新規の別文脈で始め、後続3件も同じ独立検分者の文脈で検分した。
過去runの合否を代用せず、各runの要求・実assert・実ref間diff・Core元stdout/hash・host/trace・元応答を直接確認した。
4件とも固定試験を自分で再実行し、`Ran 1 test in 0.000s / OK / exit 0`。
各検分の開始終了sourceは固定ref、statusは空。対象refは4件とも`0a3e6791b64087e3fad95935eaac55e0c810f4d5`でclean。
基準refは`4daeadd3fbe7e8d2119b717070fd3f1966ba04eb`。
skillのhost操作は各15件、baselineは各13件で、すべて許可された操作だった。

主作業者も各固定試験を再実行し、全runのinspect_recordとverify_receiptを再実行した。
機械/安全/証拠の全エラー配列は空、生成adviceは保存adviceと一致し、receipt/run hashも全件一致した。
全件保存後もsourceはclean、attemptsと個別承認台帳は4件。
同じ実行器の追加起動は`global authorized trajectory budget exhausted / exit 1`で、新規モデルを起動しなかった。
包括承認があっても、この固定4件の台帳を初期化・拡張しない。

| variant/反復 | run.json SHA-256 | wallMs |
|---|---|---|
| skill/1 | `3545656398faaabc0a4a104c9dd063090b6072a52577070168b3908bd6038afd` | 135503 |
| baseline/1 | `649f65fec26ce8efec555432ab8cae1f6de818a72d78108f0e5f478b6dd0ae16` | 121862 |
| skill/2 | `d918d8d57c38f7ae723128c591bd77d4fca1deea4a53409b06bf882d71954e77` | 134598 |
| baseline/2 | `f5c45e61e658731951fa0b16401d7552bd7714a536b6b75b1e00925acdeb8b75` | 118892 |

比較4件の使用量はinput_tokens=1039980、cached_input_tokens=914688（inputの内数）、
output_tokens=10485、reasoning_output_tokens=38。wallMs合計510855はモデル呼出し分で、採点待ち時間を含まない。
費用金額は未確定。未取得の金額を0円扱いしない。モデルaliasのrevision固定性も保証していない。

## 未認定の範囲と次工程

QPの反復比較、Q0〜Q3全帯、ready/条件付き/unknownの実動作、供給網・敵対入力、
発火/負例/競合、保持ケース、実課題、SDD連携、Phase3、Skill Gateは未認定。
次のsol評価も包括承認の範囲で、各バッチの有限条件・候補ref・停止条件を先に固定して進める。
本結果だけで出荷・配布・マージを承認しない。

## 保存証拠

traces.tar.gzは112 member / 78 file / 120380 bytes、SHA-256は
`5d3caee597fa535d07106c51bf32838d0ce7ca03c7907d3750c17a83dfbfdc88`。
4件の原run・receipt・元応答・advice・host/trace・固定入力と共有資料・attempts/conditionsを保存した。
Git内部状態、Codex logs/state、stderr、認証情報を含めない。禁止memberとリンクなしを監査し、
stderr以外の原artifact、全readableFiles、receipt/runのhashがすべて一致した。
原runのstderr hashは残したが、archiveにstderrが含まれるという主張はしない。
準備是正の独立記録は[preparation-independent-review.json](preparation-independent-review.json)を参照する。
保存後のb5948e7も独立監査し、archive・hash・使用量・4件結果・未認定範囲に要修正なしを確認した。
開始終了refは同じでclean。[保存要約の独立記録](summary-independent-review.json)へ実出力を残す。
