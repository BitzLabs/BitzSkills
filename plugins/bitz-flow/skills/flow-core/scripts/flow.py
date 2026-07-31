#!/usr/bin/env python3
"""bitz-flow の唯一の公開実行入口。

```
python3 <flow-core>/scripts/flow.py
  [--repo PATH] [--format compact|json] [--timeout-seconds N]
  <domain> <action> [operation options]
```

M0 で公開するのは read-only の3 operation（``repo inspect`` / ``git status`` /
``git diff-summary``）だけである。それ以外は ``UNSUPPORTED``（exit 8）で停止し、
生の ``git`` / ``gh`` コマンドを代替案として提示しない。

``flowlib`` を直接呼ぶことは公開契約外（FLW-DSN-004）。
"""

from __future__ import annotations

import os
import sys

# スキルはフォルダ単位でコピーされる。自分の位置から flowlib を解決し、
# 実行時の current directory やインストール先に依存しない（CORE-CON-004）。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowlib import cli  # noqa: E402 - sys.path 設定後に import する


if __name__ == "__main__":
    raise SystemExit(cli.main())
