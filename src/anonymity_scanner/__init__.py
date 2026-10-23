"""匿名性攻击面搜索器（Anonymity Surface Scanner）。

定位：k/l/t 公式是商品，**没人回答"哪几列组合会让 k 崩塌"**。
本包输入一张表 + 列角色声明，输出最小 k、最小崩塌集、每处违例的等价类与行号清单，以及可挂 CI 的 gate 结论。

版本号是本项目的**唯一可编辑副本**（`pyproject.toml` 用 `dynamic = ["version"]` 从本轮读取）。
"""
__version__ = "0.1.1"
