# datachannel

A股龙虎榜 / 游资席位跟踪与数据工具集合。

## 模块

- [`dragon_tiger/`](./dragon_tiger/)：龙虎榜 + 游资席位 + 涨跌停博弈分析 CLI  
  - 书单与数据源：[`dragon_tiger/docs/books_and_datasources.md`](./dragon_tiger/docs/books_and_datasources.md)

```bash
cd dragon_tiger
pip install -r requirements.txt
python cli.py --date 20260810 --top 15
```
