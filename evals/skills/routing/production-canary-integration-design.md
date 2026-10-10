# Phase 4：実provider公開canaryと一次台帳の統合設計

状態：draft。対象は初回の小規模な接続検証であり、実装・一次起動・測定適格性・Phase完了は未認定。
正本の評価条件は `docs/04.提案資料/30_bitz-sdd・品質管理・Coreスキル化実装計画.md` の7.5〜7.7。
承認済みREQ/TECHの意味や、試行版・RCの分母・閾値を変更しない。

## 1. 目的と既存証拠の限界

局所SDK0.160.1の固定1exec、exec/wait、2execの診断から、実OpenAI providerと永続一次台帳へ接続する。
PythonからSDK/CLIを操作し、一覧と選択したスキル本文の読取りを観測する。
既存の固定call ID、cell、日付、最終文、LOCAL_SIMULATION_ONLYを、実モデル出力の別名置換に使わない。
`production_sdk_probe.py` / `production_cli_probe.py` は局所模擬用であり、そのまま実provider用に流用しない。
新入口を別に用意し、既存診断の未知入力停止と `eligibleForMeasurement=false` を維持する。

SDK raw通知で観測した初期入力はSDK補足developerと2userだけであり、additional_tools/baseInstructionsを網羅しない。
局所模擬で保存したHTTP/SSEを、実providerのHTTP/SSE取得証拠に代用しない。
実providerで未取得の層を明示し、全wire本文一致や課金額の確定を主張しない。

## 2. 固定入力と隔離

起動前にsource ref、候補6スキル・71資源のmanifest、catalog、共通指示、ケース、環境の原bytesとhashを固定する。
SDK/CLI versionとSDK tree hash、設定、共通補足文脈も環境に固定する。
モデル入力は `project_case()` によるprompt/context、全ケース共通の指示とcatalogだけ。
ケースID・期待値・controlは親側に保持し、モデル用入力のhashを `BoundInputs.attempt()` に結ぶ。
source guardを入力読取り前・モデル起動直前・終了後に照合する。実行中のtracked変更は禁止する。

候補snapshotだけを読取り専用で渡す。書込みは試行専用出力に限定し、ユーザーのhome、他worktree、保持入力を隠す。
shell、ファイル変更、web、apps、plugins、追加agent、質問、未知server requestを拒否する。
実provider通信はSDK/CLI自身の標準認証を使い、認証情報をコードで読み取り・コピー・出力しない。
局所模擬の `--unshare-net` は実通信に使えない。実通信の隔離差分と宛先制限を実装前に検分する。

実行可能な子操作は既存の資源一覧と資源読取りの2種類だけ。
code-modeのexec/waitはその2操作への経路として観測し、任意Python/OSアクセスの許可にはしない。
初回は並列操作と未解決pendingを禁止する。段階ごとの完了を受けて次を開始する。
制限を緩める場合も、許可toolを増やす前に、この2操作を1exec・2exec・yield/waitで呼べる範囲を検証する。

## 3. 有限の初回案と共通台帳

案は公開positive1件と公開negative1件、各2反復。一次4軌跡と独立SOL検分4回、自動retry・委譲0。
設計の静的検分1回は別枠であり、一次4枠も独立一次検分4枠も消費しない。
この設計文書は一次起動の契約ではない。全前提が揃った後に原入力hashを持つ有限契約を固定する。
全ケースを開始する前に、`bind_inputs()` の2件・2反復・予算整合を検査する。

製品接続は `open_ledger(repository, bound)` だけを使う。
git-common-dirから求めた共通repository配下の `.venv/production-routing-primary-ledger` を全worktreeで共有する。
campaign ID、output、source、別worktreeの変更で枠を作り直さない。
`reserve()` のlock・O_EXCL・fsync済み予約をモデル起動前に確定し、予約後の起動失敗も消費として保持する。
前試行の親照合と独立検分が未完了、stopped、unknownの場合は次の `reserve()` を許さない。
未解決予約はリセット後も再起動しない。枠のリセット待機は未予約の次試行だけに適用する。

`record_review()` のhash形式検査だけでは原証拠を検査したことにならない。
別の親照合器が原receipt/応答/stdio/SDK通知/host trace/source guardを再読取りし、実hashと内容を照合する。
その確定した親照合結果へreviewを束縛してから台帳へ記録する。欠落・変造をacceptedにしない。
independentReviewerの起動予約も永続化し、停止後の同枠再起動や別出力への差替えを許さない。

## 4. 実行上限と停止

案の各試行は壁時計300秒、code-mode親呼出し最大2、子操作最大2、子は一覧1回・本文読取り最大1回。
native API要求は最大3を候補とするが、これはまだ実効性を確認した上限ではない。
一次4軌跡はprovider内部retryやHTTP要求4件を意味しない。
SDK/CLIのretry設定・要求数・timeout後の子process終了を原証拠で確認し、要求上限の強制手段を実装するまで起動しない。
認証情報を読むHTTP proxyでこの未証明事項を補わない。
価格・請求額を未確認の数値で予算へ換算しない。token usage、実要求数、実時間と停止理由を原記録へ保存する。

negativeの期待する観測はスキル本文読取り0。positiveは期待する候補本文の実読取りが必要。
期待値は測定者側の判定用であり、実行中にモデルの選択を誘導しない。
制限超過、未知tool、禁止操作、非正常終端、証拠欠落、未知pendingはstoppedにし、残りの自動起動を止める。
選択誤りや期待する読取り不足は試行失敗として原軌跡を保持し、入力変更や再試行で置換しない。

## 5. 可変IDの証拠相関と判定

新照合器は原thread/turn、親call IDとcell、セル内runtime IDとnative child IDを原値のまま結ぶ。
IDの使い回し、交換、欠落、重複、別turn、因果順序の逆転を拒否する。
許可profileは1exec内の一覧→読取り、2execの一覧→読取り、exec→wait内の一覧→読取り。
negativeは子操作0または一覧のみを許し、本文読取り0を検査する。最終応答だけの自己申告は証拠にしない。
任意program、任意cell数、並列、未知native item、未解決継続は推定で許可しない。
host引数と出力全文、固定snapshotの原bytes、native完了、SDK原通知、全対象telemetryを検査する。
呼出し可能な2子操作以外へ到達できないことを、実行環境と拒否試験で確認する。

正常exitだけでは測定適格にしない。実providerの初期tool/基礎指示/補足/ケースの完全入力を証明する方法が未確定なら、
結果を接続診断に留め `eligibleForMeasurement=false` とする。
欠落層を除いて正本の採点条件を弱める案は、この設計の承認対象に含めない。
deterministic→安全・権限→rubric→独立検分の順で判定し、独立SOLのpassだけで必須項目を通過にしない。

## 6. 実装順序と着手条件

1. この設計と公開コードを独立した有限SOL文脈で静的検分し、原応答を親側で照合する。
2. 一次と独立検分の共通台帳接続、予約後停止・保存失敗・二重起動拒否を局所試験する。
3. 可変ID/profileの新照合器を作り、変造・別turn・原本文不一致・未知操作の拒否を局所試験する。
4. provider retry/要求上限、隔離差分、完全初期入力の証明方法を確定し、未解決事項を先に解消する。
5. 有限実行契約と具体的原入力を固定し、許可済み範囲を確認して初回canaryを起動する。

公開記録は件数・hash・ref・実exit・停止理由だけ。原stdio/RPC/raw/host/telemetryとケース判定は私的出力に保持する。
初回canaryでは試行版・RCの全分母、5種実地比較、第二モデル系統、SkillGate、リリースを認定しない。
Phase 5の人間によるリリース承認を独立静的検分で代用しない。
