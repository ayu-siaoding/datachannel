# datachannel

A 股短线题材工具与相关脚本。

## 开盘前 10 分钟自动扫描（排除北交所）

每个交易日 **09:20（Asia/Shanghai）** 运行，按短线题材方法（见 `docs/SHORT_TERM_THEME_METHOD.md`，参考 [X 视频](https://x.com/cj3214567667/status/2114717684827037856/video/1)）输出 **观察池股票代码**（空间龙、中军、补涨）。

### 一次性安装

```bash
cd /path/to/datachannel
python3 -m pip install -r requirements.txt
chmod +x scripts/run_premarket.sh
```

### 手动运行

```bash
# 默认：1～3 板接力模式
./scripts/run_premarket.sh

# 龙头分歧回封
MODE=dragon ./scripts/run_premarket.sh

# 指定交易日、保存 JSON
python3 scripts/premarket_scan.py --date 2026-10-27 --out reports/premarket.json

# 仅输出代码（方便粘贴自选）
python3 scripts/premarket_scan.py --method short-theme --codes-only
```

### 定时任务（本机 crontab）

```cron
# 周一至周五 09:20 上海时间
20 9 * * 1-5 cd /path/to/datachannel && ./scripts/run_premarket.sh >> logs/premarket.log 2>&1
```

说明：cron 使用系统时区时，请将系统时区设为 `Asia/Shanghai`，或在 crontab 行首设置 `CRON_TZ=Asia/Shanghai`（视系统而定）。

### 输出说明

| 字段 | 含义 |
|------|------|
| `观察池代码` | 逗号分隔，可直接导入自选 |
| `角色.空间龙` | 连板高度 + 成交额优先 |
| `角色.中军` | 同主题大成交额 |
| `昨日涨停溢价` | 09:20 附近腾讯行情 `zdf`（集合竞价涨幅） |

数据源：东方财富昨涨停 / 涨停股池（备用）+ 腾讯全 A 竞价涨幅。**需在可访问国内行情接口的网络运行**（云主机可能拉不到涨停池）。

非投资建议。
