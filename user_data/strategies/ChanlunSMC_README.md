# Chanlun + SMC 策略说明

## 策略概述

**ChanlunSMC** 结合了：
- **缠论（Chanlun）**：分型识别、背驰检测
- **SMC（Smart Money Concepts）**：Order Block、Fair Value Gap（FVG）
- **多周期对齐**：4h确认趋势 + 1h精确入场
- **高R:R设置**：目标2:1或更高的风险回报比

---

## 核心逻辑

### 做多信号（Long Entry）
1. ✅ **4h趋势向上** - EMA 20 > 50 > 200
2. ✅ **价格回调至Bullish OB或FVG** - 机构订单区域
3. ✅ **底分型确认** - 缠论分型识别
4. ✅ **MACD看涨背驰** - 价格新低但MACD不新低
5. ✅ **RSI < 40** - 超卖区域
6. ✅ **Volume确认** - 成交量 > 20MA的80%

### 做空信号（Short Entry）
1. ✅ **4h趋势向下** - EMA 20 < 50 < 200
2. ✅ **价格反弹至Bearish OB或FVG**
3. ✅ **顶分型确认**
4. ✅ **MACD看跌背驰** - 价格新高但MACD不新高
5. ✅ **RSI > 60** - 超买区域
6. ✅ **Volume确认**

### 出场信号
- 反向分型出现
- MACD反向背驰
- 突破关键EMA（21）

### 止损策略
- **硬止损**：3%（配置）
- **动态止损**：Order Block边界 ± 1 ATR
- **Trailing Stop**：盈利2%后启动，盈利3%开始trailing

---

## 使用方法

### 1. 安装依赖（如果freqtrade未配置）
```bash
cd /Users/mxzhang/Documents/Crypto/freqtrade
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 验证策略加载
```bash
freqtrade list-strategies --strategy-path user_data/strategies
```

应该看到：`ChanlunSMC`

### 3. 下载历史数据（回测需要）
```bash
# 下载BTC/USDT 1小时数据（最近30天）
freqtrade download-data \
    --exchange binance \
    --pairs BTC/USDT ETH/USDT \
    --timeframes 1h 4h \
    --days 30 \
    --datadir user_data/data/binance
```

### 4. 运行回测
```bash
freqtrade backtesting \
    --strategy ChanlunSMC \
    --timeframe 1h \
    --datadir user_data/data/binance \
    --timerange 20250101-20250226 \
    --stake-amount 1000 \
    --dry-run-wallet 10000
```

### 5. 优化参数（Hyperopt）
```bash
freqtrade hyperopt \
    --strategy ChanlunSMC \
    --hyperopt-loss SharpeHyperOptLoss \
    --timeframe 1h \
    --epochs 500 \
    --spaces buy sell \
    --datadir user_data/data/binance
```

可优化参数：
- `ob_lookback` - Order Block回看期（10-50）
- `fvg_threshold` - FVG阈值（0.001-0.01）
- `min_rr_ratio` - 最小R:R比例（1.5-3.0）

### 6. 实盘/模拟盘运行
```bash
# Dry-run（模拟盘）
freqtrade trade \
    --strategy ChanlunSMC \
    --config user_data/config.json \
    --dry-run

# 实盘（谨慎！）
freqtrade trade \
    --strategy ChanlunSMC \
    --config user_data/config.json
```

---

## 配置文件示例

创建 `user_data/config_chanlun_smc.json`：

```json
{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.3,
    "fiat_display_currency": "USD",
    "dry_run": true,
    
    "timeframe": "1h",
    
    "exchange": {
        "name": "binance",
        "key": "YOUR_API_KEY",
        "secret": "YOUR_API_SECRET",
        "ccxt_config": {},
        "ccxt_async_config": {},
        "pair_whitelist": [
            "BTC/USDT",
            "ETH/USDT",
            "BNB/USDT",
            "SOL/USDT"
        ],
        "pair_blacklist": []
    },
    
    "entry_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1,
        "check_depth_of_market": {
            "enabled": false,
            "bids_to_ask_delta": 1
        }
    },
    
    "exit_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },
    
    "pairlists": [
        {
            "method": "StaticPairList"
        }
    ],
    
    "telegram": {
        "enabled": false,
        "token": "YOUR_TELEGRAM_TOKEN",
        "chat_id": "YOUR_CHAT_ID"
    },
    
    "api_server": {
        "enabled": true,
        "listen_ip_address": "127.0.0.1",
        "listen_port": 8080,
        "verbosity": "info",
        "jwt_secret_key": "your_secret_key",
        "username": "freqtrader",
        "password": "your_password"
    },
    
    "bot_name": "ChanlunSMC_Bot",
    "initial_state": "running",
    "force_entry_enable": false
}
```

---

## 关键参数调整

### 时间周期
- 默认：1h（主周期）+ 4h（确认周期）
- 可改为：15m + 1h（更频繁交易）或 4h + 1d（更稳健）

### 风险管理
- `stoploss = -0.03` → 调整到你的风险承受能力
- `minimal_roi` → 根据回测结果调整
- `max_open_trades` → 控制并发持仓数

### 入场条件严格度
策略中的条件可以放宽或收紧：
- RSI阈值（当前：多头<40，空头>60）
- Volume倍数（当前：>0.8x MA）
- 是否要求所有条件同时满足

---

## 回测结果解读

关键指标：
- **Total trades** - 交易次数（太少=条件太严，太多=噪音）
- **Win rate** - 胜率（目标：>40%）
- **Avg profit** - 平均盈利（应 > 平均亏损）
- **Sharpe ratio** - 风险调整后收益（>1为好）
- **Max drawdown** - 最大回撤（控制在<20%）

---

## 调试技巧

### 查看策略生成的指标
```bash
freqtrade plot-dataframe \
    --strategy ChanlunSMC \
    --timeframe 1h \
    --pairs BTC/USDT \
    --indicators1 ema_9,ema_21,ema_50 \
    --indicators2 rsi,macd_hist
```

### 查看详细日志
在config中设置：
```json
"verbosity": 3,
"logfile": "user_data/logs/freqtrade.log"
```

---

## 进一步优化方向

1. **动态参数**：根据市场波动性调整止损/OB lookback
2. **多品种适配**：不同币种可能需要不同参数
3. **时间过滤**：避开低流动性时段（如周末）
4. **Volume Profile**：整合成交量分布分析
5. **机器学习**：用FreqAI模块训练更智能的入场

---

## 风险警告

⚠️ **本策略仅供学习和研究使用**
- 回测表现 ≠ 实盘表现
- 加密货币市场波动极大
- 请先在模拟盘充分测试
- 实盘使用小资金验证
- 永远不要投入超过你能承受的损失

---

## 常见问题

**Q: 为什么策略没有生成交易信号？**
A: 检查：
1. 数据是否完整（需要4h数据）
2. 条件是否太严格（暂时放宽RSI/Volume条件测试）
3. 市场是否在盘整（策略偏向趋势市场）

**Q: 如何提高交易频率？**
A: 
1. 降低时间周期（1h → 15m）
2. 放宽RSI阈值
3. 减少必要条件（如去掉Volume确认）

**Q: 如何降低风险？**
A:
1. 增加4h趋势确认强度
2. 提高RSI超买/超卖阈值
3. 要求更多确认条件（如加入ADX趋势强度）

---

## 支持

- Freqtrade文档：https://www.freqtrade.io/en/stable/
- Discord社区：https://discord.gg/freqtrade

---

**祝交易顺利！** 🚀📈
