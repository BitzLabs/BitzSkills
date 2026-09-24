"""指定したtest fileだけをunittestで実行する（bitz-core自身の`.spec/`の`verify` command）。

`bitz verify`は`{tests}`をworkspace相対のtest file pathへ展開して渡す。`python -m unittest`は
`tests/bitz-core/`のようにmodule名へ変換できないpathを受け付けないため、fileから直接loadする。
`uv run --project plugins/bitz-core python tests/bitz-core/run_test_files.py <path>...`で実行する。
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import unittest


def load_tests_from_file(loader: unittest.TestLoader, path: Path) -> unittest.TestSuite:
    spec = importlib.util.spec_from_file_location(f"_bitz_core_test_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"test fileを読み込めません: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="指定したtest fileだけをunittestで実行する。")
    parser.add_argument("paths", nargs="+", type=Path, help="test fileのpath")
    args = parser.parse_args(argv)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(load_tests_from_file(loader, path) for path in args.paths)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
