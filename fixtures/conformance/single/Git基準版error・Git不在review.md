# Git基準版エラー・Git不在fixtureレビュー

2026-09-14。SINGLE-036〜038の3件を追加する。Coreの実行結果ではなく、入力・manifest・唯一の期待値・
副作用期待値を固定したStep 0Bの準備証拠である。

## ケースと期待値

| ID | 入力・呼出し | 期待値 |
|---|---|---|
| SINGLE-036 | 最小設定・approved TECH・既存reportをcommit済み。check --base fixture-missing-base --report --format json | 終了コード4、stdout空、stderrに理由1行、結果JSONなし、既存report不変・新規reportなし |
| SINGLE-037 | Gitを実行できない環境の最小設定・approved TECH。check --format json | full、passed_with_warnings / 0、SPEC-GIT-DEGRADED-001のみ、revision=null |
| SINGLE-038 | 同じGit不在環境の最小設定・open TASK。check TASK-001 --format json | selected、blocked / 2、SPEC-TASK-BOUNDARY-002のみ、revision=null |

036はHEADが正常に解決でき、指定したfixture-missing-baseだけが解決できないことを確認する。
既存reportは.spec/reports/existing.jsonの固定byte列で、変更前後snapshotへ含める。
--report指定を加えても引数エラー時には新しいreportも部分結果も出さない期待を固定する。
manifestにはstatus/resultFile/textFileを置かず、expected/の結果fileも作らない。

stderrの自然言語文言は機械判定に使わないという正本に従い、fixture直下のcli-output.jsonは
stdout空・終了コード4・stderrのprefix・非空理由・1行・端末制御文字禁止だけを固定する。
check_cli_error_outputはその出力形状を検査するtest用assertionであり、Coreのargv解析ではない。
日本語・英語の異なる理由文が通ること、空理由・複数行・制御文字・不正UTF-8・stdoutへの空JSONなどが
拒否されることを自己試験する。manifestの公開fieldや規範Schemaは増やさない。

037・038ではsetup.git=falseに加え、invocation.envのPATHをLinuxの非directory /dev/nullへ固定する。
空PATHによるcurrent directory検索やhost PATHへのfallbackを避け、shutil.whichでGit解決不能を確認する。
Core起動時は絶対pathのentry point/interpreterを使い、このPATHはそのprocess環境へ適用する必要がある。
Core本体は未起動であり、起動・環境適用と実結果はGate Bで検証する。
fixture自体に.gitを置かない。hostの一時directoryの親にGit metadataがあっても、実行環境にGitがないため
そのGitを代わりに起動して状態を取得しない。

037のsummaryは全体検査への縮退と、REQ保護・状態遷移・管理済みSPEC削除の失われる差分保証を明示する。
038は境界不能をblockedとし、引数なし用の縮退warningを重ねない。TASKはchangesや関係を持たない正常なopen文書で、
checkの文書検査後のTASK境界段階で停止するため、selected結果の検査文書数は1、規範文数は0とする。
037も全文書検査は1文書・0規範文である。両件ともsourceはenvironment / component=git / identifier=git、
summaryはexpected/check.jsonの今回選択した文字列、durationMsは0とする。追加の比較除外を設けない。

根拠は[check仕様 §5・§7・§9・§10](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[安全な入出力 §8](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md)、
[終了コード4の出力契約](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)、
[CLI基盤のGit要件](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md)、
[適合fixture仕様 §3・§6.4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証と補助Schema

既存の副作用Schemaのgitだけにnullを許可し、Git不在と正常なGitの空status/indexを区別する。
既存Gitありfixtureのobject形式は維持し、各validatorが実際の準備状態へ照合する。
Git取得失敗をcatchしてnullへ変換せず、Git不在を明示した2件だけがnullを持つ。

3件とも2回の隔離setupを行い、固定入力byte列、Frontmatter値、manifest、結果またはCLI出力形状、副作用期待値を照合する。
036ではHEAD/index blobと無効ref、037・038ではGitの解決不能とローカル.git不在を直接検査する。
HOME/cache/TMPDIRも固定snapshotで比較し、before=afterを要求する。Coreの実副作用を観測したとは扱わない。

回帰試験は終了コード4へのstatus追加、CLI出力形状の改変、report消失、Git不在の正常Git化、PATH制約の除去、
warning消去、TASK診断の置換・重複を拒否する。無効refが実際に解決可能になった状態、fixtureへの.git追加も拒否する。

## 前回fixtureの補正

適合fixture仕様 §3はbaseCommitがあるfixtureに明示--baseを要求する。
前回のSINGLE-040・041に不足していた--base HEADをmanifestとレビュー済みargvへ追加した。
Git入力、対象集合、期待JSON、副作用期待値は変わらない。unbornの039には--baseを加えない。
matrix検査へ明示baseの欠落とGit不在時のbase指定を検出する規則・回帰試験を追加した。

準備済み60/311件、残251件。Git基準版matrixのSINGLE-027〜041は実fixture準備済みとなる。
golden Digest等とfresh checkoutからの全Gate A検証は残るため、Gate AはBlockedを維持する。
