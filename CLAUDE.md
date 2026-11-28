# CLAUDE.md

共通ルールはすべて @AGENTS.md を正とする。本ファイルには、Claude Code だけに当てはまることを書く。

## Claude Code 固有

- 危険操作の機械的ブロックは `.claude/settings.json` の permissions で強制している
  （AGENTS.md のガードレール節と対応。緩めるときは両方を見直す）
- `deny`の規則は、複合コマンドの途中に現れた場合にも働く。使い捨ての検証のスクリプトに`git add -A`などを
  書くと、コマンド全体が拒否される
- 数分かかるコマンド（fixture の監査、Gate の認定、適合試験の全件）は、バックグラウンドで実行するか、
  制限時間を延ばす
- 応答が英語主体になると、Stop hook の japanese-guard（`.claude/hooks/japanese-guard/`）が終了を止め、日本語で
  書き直させる。差し戻されたら、指示どおり英語の箇所だけを日本語で書き直す

## Git 操作の許可設定

`.claude/settings.json`は、`AGENTS.md`で許可したpushの3つの形だけを完全一致で許可し、
それ以外のpushは確認を求める。規則はコマンドの先頭の文字列で照合されるので、
オプションの順序や`+refspec`による抜け道を`deny`だけでは塞げない。

## 委譲の設定

共通の委譲方針と役割一覧は `AGENTS.md` の「サブエージェントへの委譲」に従う。

- 各役割の登録情報・モデル・ツール設定は `.claude/agents/*.md` の frontmatter に置く
- 各定義の本文から `agents/<役割>.md` を明示的に読む。共通役割定義を複製しない
- コードベースの広範な探索には、組み込みの `Explore` を使う
