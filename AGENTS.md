# AGENTS.md

本仓库遵循 **`ai-tool-project-sprint`** 方法论（装订日期：2026-10-20）。

## 任何新对话的第一件事

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（CI / 非 Windows 用 python tools/check_sprint_layout.py）
```

- 必须全绿；红了先修布局再干活。
- 续接对话：先读 `plan/HANDOFF-M<k>.md`（第 k 棒的收尾交接单），**再跑上面这条门**。
- 接手对话（无 HANDOFF）：先读 `plan/00`、`plan/05`、`plan/06`，重建"当前状态 + 既定口径清单"再动手。
- **门不存在 = 本项目没装订** → 先补装订三件（本文件 + `tools/check_sprint_layout.py` + `plan/00` 顶部装订行），再做别的。

## 强制布局（布局门逐条断言，改动前先看这里）

| 项 | 位置 | 判据 |
| --- | --- | --- |
| 计划套件 | `plan/00`–`plan/06` + `data/README.md` | 存在且各含必需小节（标题关键词） |
| 数据台账 | `data/README.md` | 含"依据查证记录"与"数值口径"两节；§四大类是数值口径唯一出处 |
| 交接单 | `plan/HANDOFF-M<k>.md` | 每个 ✅ 里程碑一份（M0 已声明豁免），**七节**齐：当前进度 / 当前事实 / 待办 / 既定口径 / 环境坑 / DoD / 命令速查 |
| 里程碑状态副本 | `plan/00` 里程碑表 + `plan/05` 状态表 + `README` 状态行 + `plan/06` 覆盖对标表 | **逐处一致**；门按"逐副本采集、任一不一致即红"判定，不以任何单一副本为真值 |
| 缺口表 | `plan/06` 的"缺口"列 | 已 ✅ 的里程碑不得再出现在缺口格里（关闭缺口时只描述、不点名文件） |
| 发布留档 | `plan/RELEASE-M7.md`（两栏）或 `plan/WRAPUP-M7.md` | 仅当发布里程碑 M6 已 ✅ 时断言；两栏 + 覆盖对账小节 + 三态行 ≥ 3 |
| 文档点名的工具 | `tools/*.py` 被文档引用 | `AGENTS.md`、`README.md`、`plan/*.md` 里出现的 `tools/*.py` 必须**真实存在**（防"文档点名的门没有实物"） |
| 装订行 | `plan/00` 顶部 | 同一行同现：方法论名 + 布局门命令 + 装订日期 |

## 变异验证（改门或改文档后必跑）

```bash
py -3.12 tools/verify_layout_gate.py
```

它会在临时目录里逐条构造"缺件 / 状态冲突 / 过期缺口 / 留档缺节"等 10 组故障，**每一组都要求布局门变红**并报出对应判据 id。任一组仍绿 = 假门，先修门再继续。

## 环境事实与禁忌（2026-10-20 实测）

- Windows + Git Bash（CI 为 ubuntu/windows 双矩阵）。`py -0p` 实测两条通道：3.8.8 与 3.12.10；`pytest` 7.4.4 / 8.4.2。`node v24.15.0` 在但本项目不依赖 Node。
- `python` 是商店占位符 → 本机一律 `py -3.12 ...`（或在 venv 里用 `./.venv/Scripts/python.exe`）。
- 运行时**零第三方依赖**；测试期只依赖 `pytest`（dev extra）。
- 编码：入口按 `stream.encoding` 探针决定是否 reconfigure 到 UTF-8；CI 另设 `PYTHONUTF8=1`。
- 禁止：把"未执行"写成已完成；未实现的能力返回 `0` 或空结果（fail-closed 到退出码 `2`）；在 tag 之后改交付面（`src/`、`pyproject.toml`）。
