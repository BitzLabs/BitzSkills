---
implements: FLW-FR-003, FLW-FR-004, FLW-CON-001, FLW-CON-002
depends_on: [FLW-TSK-007, FLW-TSK-008]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flow.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/__init__.py
status: pending
---

### M0 単一 dispatcher の結線（flow.py と3 operation）

- **作業内容**: FLW-DSN-003 の公開入口を `flow.py` として実装し、M0 の3 operation を結線する。

  ```text
  python3 <flow-core>/scripts/flow.py
    [--repo PATH] [--format compact|json] [--timeout-seconds N]
    <domain> <action> [operation options]
  ```

  `--repo` 省略時は current directory から repo root を解決する。`--format compact` を既定とする。
  timeout は read 1〜300 秒、既定 30 秒。`argparse` を使い、解釈できない引数は非ゼロ終了させる
  （CORE-CON-011）。
  公開するのは `repo inspect` / `git status` / `git diff-summary` の3つだけとし、
  それ以外の domain / action は `UNSUPPORTED`（exit 8）を返して停止する。
  `UNSUPPORTED` 時に生の `git` / `gh` コマンドを代替案として出力しない。
  `--apply` / `--confirm` / `--approval-ref` は M0 では受理せず `UNSUPPORTED` とする
  （write operation は M1 以降）。
  cli は入力を canonical 化し、adapter から事実を取得し、renderer へ渡す。
  `flowlib` を直接呼ぶことは公開契約外であり、`flow.py` だけを public executable とする。
  件数上限で result を省略する場合は `shown` / `total` / snapshot 拘束 cursor と
  絞込み next action を返す。
- **完了条件**: 3 operation が compact と JSON の両方で operation 別 JSON Schema を満たす result を
  返すこと。終了コードが FLW-TSK-005 の表と一致すること。未対応 operation で raw fallback を
  出力しないこと。`python3 -m py_compile` と canonical spec inspect、release_check が PASS すること。
- **備考**: FLW-DSN-004 の実装ビューにない module 名を新設しない。application service 層が
  独立 module を必要とすると判明した場合は、実装を中断して `.spec/spec-issues/` へ起票し、
  人間の裁定を待つ（設計の独断変更をしない）。
