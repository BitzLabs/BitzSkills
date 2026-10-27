#!/bin/sh
# CI用イメージの版を判定する（ADR-069）。uv と Python は固定した版と完全に一致し、Git は下限以上であること。
set -eu
uv_version=$(uv --version)
python_version=$(uv run --no-project python --version)
git_version=$(git --version)
echo "$git_version"
echo "$uv_version"
echo "$python_version"
case "$uv_version" in
  "$EXPECTED_UV "*|"$EXPECTED_UV") ;;
  *) echo "uv の版が固定値と一致しません: $uv_version" >&2; exit 1 ;;
esac
test "$python_version" = "$EXPECTED_PYTHON" || { echo "Python の版が固定値と一致しません: $python_version" >&2; exit 1; }
actual=$(echo "$git_version" | sed -n 's/^git version \([0-9]*\.[0-9]*\).*/\1/p')
lowest=$(printf '%s\n%s\n' "$MIN_GIT" "$actual" | sort -V | head -n 1)
test -n "$actual" && test "$lowest" = "$MIN_GIT" || { echo "Git が $MIN_GIT 未満です: $git_version" >&2; exit 1; }
