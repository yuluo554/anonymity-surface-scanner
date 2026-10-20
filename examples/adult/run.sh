#!/usr/bin/env bash
# UCI Adult 端到端演示：表 + 声明 → gate.json + gate.md + 退出码。
#
# 只读本地文件，**绝不联网**。数据请自行下载（见 examples/adult/README.md）。
# 用法：
#   bash examples/adult/run.sh [adult.data 路径]
#   PYTHON="py -3.12" bash examples/adult/run.sh
#   OUT_DIR=out/adult-2 bash examples/adult/run.sh
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
source_data="${1:-$here/adult.data}"
out_dir="${OUT_DIR:-$repo/out/adult}"

if [ -n "${PYTHON:-}" ]; then
  read -r -a python_argv <<< "$PYTHON"
elif command -v py >/dev/null 2>&1; then
  python_argv=(py -3.12)          # 本机：`python` 是商店占位符
else
  python_argv=(python3)
fi

if [ ! -f "$source_data" ]; then
  echo "adult.data not found at: $source_data" >&2
  echo "download it yourself (see examples/adult/README.md); this script never downloads." >&2
  exit 3
fi

"${python_argv[@]}" "$here/prepare.py" --input "$source_data" --output "$here/adult.csv"

if command -v anonymity-scanner >/dev/null 2>&1; then
  runner=(anonymity-scanner)
else
  export PYTHONPATH="$repo/src${PYTHONPATH:+:$PYTHONPATH}"
  runner=("${python_argv[@]}" -m anonymity_scanner.cli)
fi

cd "$repo"
set +e
"${runner[@]}" gate --criteria "$here/criteria.json" --out-dir "$out_dir" --root "$repo"
code=$?
set -e
echo "gate exit code: $code"
echo "artifacts: $out_dir/gate.json + $out_dir/gate.md"
exit "$code"
