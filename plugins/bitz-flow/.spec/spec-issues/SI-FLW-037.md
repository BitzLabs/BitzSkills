---
id: SI-FLW-037
raised_by: M0第14ラウンド振り返り（agy r14環境エラーで123 trial無効）
target: FLW-DSN-014・M1以降のeval/canary runner・run manifest
proposed_change_type: modify
status: open
---
- **目的**: M0第14ラウンドのantigravity初回実測では、CLIがホーム配下へログを書けない環境を
  正式母数123件の完走後に検出し、全件を無効化した。既存の`--trials` smoke機能、runner自己診断、
  陽性対照は個別に存在するが、正式測定へ入る前の必須Gateとして結合されていない。M1以降の
  write/fault canaryで同じ順序を繰り返さないよう、計測器と実行環境の適格性を少数trialで先に判定する。
- **提案する修正**:
  1. 正式測定を`qualification`と`confirmation`の2段階へ分離し、qualification PASSなしでは
     confirmationの所要母数を実行できないようにする。
  2. qualificationは各platform・各operation/cellの最小trialで、CLI起動・認証、必要な書込先、
     raw log永続化、event抽出、runner終了コード、agent unavailable署名、envelope/schema抽出、
     必須observation fieldの対称性を検査する。
  3. 危険事象proxyは陰性対照だけでなく、既知入力を確実に検出する陽性対照を必須にする。
  4. qualification成果物はGate証跡として保存するが、confirmationの出口母数・合否へ混入させない。
  5. qualification失敗時は正式runを開始せず、platform / environment / instrumentのどの軸で
     不適格かを構造化して返す。
- **対象ファイル**: `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`、M1以降のtask / test-spec、
  `evals/flow-core/m0-eval/`のrunner共通部（一般化する場合）、run manifest schema、
  `tests/test_m0_eval_runner.py`。bitz-sdd V4テーマ13-Cのmeasurability入力にも接続する。
- **確認観点**:
  - agyのホーム書込み不可、Claudeのレート制限、Codexのevent出力欠落をfixtureで注入すると、
    confirmation開始前にfail-closedで止まること。
  - 陽性対照を故意に無効化するとqualificationがFAILし、危険事象0件を合格へ使わないこと。
  - qualification trialが正式母数・Parity・危険事象率へ混入しないこと。
  - 3 runnerの必須field集合と終了コード意味論が一致すること。
- **影響推定・ロールバック**: 検証プロトコルとGate契約を変更するため軽量レーン不適、Design Gateが必要。
  公開dispatcherのoperation/result契約は変更しない。qualification段階を外せば現行の直接confirmationへ
  戻せるが、既に保存したqualification証跡は監査履歴として保持する。
- **依存**: `SI-FLW-019`案3、`FLW-NFR-009`、`FLW-NFR-010`、`FLW-REV-006:SYN-015`、
  bitz-sdd V4 ROADMAPテーマ13-C。**推薦: accept**。個別の陽性対照案を重複実装せず、
  既存自己診断を正式測定の入口Gateへ昇格する補強として扱う。
