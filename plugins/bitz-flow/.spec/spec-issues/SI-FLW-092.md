---
id: SI-FLW-092
raised_by: FLW-TSK-115〜122の実走・confirmation再実走
target: evals/flow-core/m1-eval/run_qualification.py の --out 検証、FLW-DSN-017 用語表
proposed_change_type: modify
status: open
---
- **目的**: 実走手順の誤りが「安全欠陥の検出」に見える状態と、`platform`という語の
  二義性が「片方の達成をもう片方の達成として読める」状態を解消する。
- **発見した事実**:
  - `run_qualification.py`は`--out`を**被験リポジトリ内へ指定できる**。
    `repo_state_digest()`が`git status --porcelain`を含むため、runnerが作った出力
    ディレクトリが`??`として現れ被験リポジトリのdigestが変わる。gitは未追跡ディレクトリを
    1行に畳むので**最初のplatformだけ**がその瞬間をまたぎ、`hazardous event`と
    `残存副作用`が計上される。2026-08-24の実走でclaudeがこれでFAILし、
    切り分けに時間を要した。検出器は正しく、変化させたのは実走手順である。
  - `platform`という語が2つの軸へ使われている。`target OS`（Linux／macOS／Windows）と
    `agent platform`（claude／codex／antigravity）である。`FLW-REV-027`のGate blocking
    条件「3platform実観測」は前者を指すが、後者の3者PASSを達成と誤読できる。
    confirmationは3者とも**同一Linuxホスト**で走るため、揃っても`target OS`の
    実観測にはならない。
  - `run_local_confirmation.py`のattempt ledgerはハッシュチェーンであり、別ディレクトリで
    実走したledgerを既存ファイルへ単純追記すると連鎖が壊れる。`--out`をリポジトリの
    `evals/flow-core/m2-eval/`へ向ける必要があるが、この前提はどこにも明文化されていない。
- **提案する修正**: **accept推薦**。
  - `run_qualification.py`と`run_local_confirmation.py`で、`--out`が被験リポジトリ配下か
    どうかを起動時に判定する。qualificationは**配下なら拒否**（誤検出を必ず生むため）、
    confirmationは**配下であることを要求**（ledger連鎖のため）し、それぞれ理由を明示して
    非ゼロ終了する。両者で要求が逆であることをhelpと`references/`へ明記する。
  - `FLW-DSN-017`の用語表へ`target OS`と`agent platform`を追加し、`platform`の単独使用を
    禁止する（本issueで既に実施。以後の機械検査対象化を検討する）。
- **対象ファイル**: `evals/flow-core/m1-eval/run_qualification.py`、
  `evals/flow-core/m2-eval/run_local_confirmation.py`、`FLW-DSN-017` §1.4、
  関連test、`skills/flow-core/references/`。
- **確認観点**: qualificationが被験リポジトリ配下の`--out`を拒否すること。confirmationが
  配下以外の`--out`を拒否すること。用語の単独使用が残っていないこと。
- **影響推定・ロールバック**: runtime公開面は変えない。実走harnessとドキュメントに閉じる。
- **依存**: なし。`FLW-REV-028`の前に用語の是正だけ先行済み。
