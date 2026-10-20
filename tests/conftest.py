"""pytest 引导：让测试在**未安装**的仓库树上也能跑（干净 clone / tarball 解包树）。

理由：CI 与发布包验证都要求"从一棵没有 `.git` 的树里直接跑测试"能成立；
依赖 `pip install -e .` 才能 import 会让这条路测不到。
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
