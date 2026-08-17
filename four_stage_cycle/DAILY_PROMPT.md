# 四阶段周期 · 每日扫描 Prompt

将以下内容复制到 Cursor，配合 Longbridge MCP 使用：

---

请按 Ted Zhang 四阶段市场周期框架，对我关注的标的做**周线**扫描：

1. 用 Longbridge MCP `candlesticks` 拉取周线（period=week, count=200, forward_adjust=true）
2. 保存到 `four_stage_cycle/sample_data/<symbol>.json`
3. 运行：
   ```bash
   cd four_stage_cycle && python3 scanner.py --data-dir ./sample_data
   ```
4. 输出表格：代码 | 阶段 | 动作 | 置信度 | 收盘 | SMA10/20/30/40 | 关键备注

**判定标准（简要）**
- P2 做多：价在四均线上，10>20>30>40 且均线上行
- P3 离场：十周线反复被拒，或利好不涨
- P1 观望：均线缠绕，勿抄底
- P4 空仓/做空：空头排列或价在 30/40 周线下

对处于 **P2 且刚进入** 的标的，额外搜索：是否有足够大的基本面/主题催化剂支撑后续上涨。

默认扫描池：SMH.US, NVDA.US, GLD.US, 510300.SH, 512890.SH（可让我追加）。

---
