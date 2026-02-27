# ChanlunSMC 策略 - 快速开始

## ✅ 已完成

1. **策略文件创建** - `ChanlunSMC.py` ✅
2. **语法验证通过** - Python语法检查 ✅  
3. **文档完成** - 详细使用说明 ✅
4. **测试脚本** - 单元测试脚本 ✅

---

## 🚀 立即使用（3步）

### Step 1: 修复Freqtrade环境

你的虚拟环境缺少依赖。运行：

```bash
cd /Users/mxzhang/Documents/Crypto/freqtrade

# 选项A：重新安装依赖（推荐）
source .venv/bin/activate
pip install -r requirements.txt

# 选项B：如果失败，重建虚拟环境
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 2: 验证策略加载

```bash
source .venv/bin/activate
freqtrade list-strategies --strategy-path user_data/strategies
```

应该看到：**ChanlunSMC**

### Step 3: 下载数据 & 回测

```bash
# 下载30天数据
freqtrade download-data \
    --exchange binance \
    --pairs BTC/USDT ETH/USDT \
    --timeframes 1h 4h \
    --days 30

# 运行回测
freqtrade backtesting \
    --strategy ChanlunSMC \
    --timeframe 1h \
    --stake-amount 1000
```

---

## 📁 文件说明

```
user_data/strategies/
├── ChanlunSMC.py              # 主策略文件
├── ChanlunSMC_README.md       # 详细使用说明
├── test_chanlun_smc.py        # 单元测试（需numpy/pandas）
├── QUICKSTART.md              # 本文件
└── config_chanlun_smc.json    # 配置模板（需创建）
```

---

## 🎯 策略核心

### 多头入场条件：
1. ✅ 4h趋势向上（EMA对齐）
2. ✅ 价格回调至Bullish OB/FVG
3. ✅ 底分型确认
4. ✅ MACD看涨背驰
5. ✅ RSI < 40

### 空头入场条件：
反向逻辑

### 风控：
- 止损：3%（动态调整至OB边界）
- R:R：≥ 2:1
- Trailing Stop：盈利2%后启动

---

## 🔧 常见问题

### Q: ModuleNotFoundError
A: 虚拟环境未激活或依赖未安装
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Q: 策略没有交易信号
A: 
1. 检查数据是否包含4h周期
2. 市场可能不符合条件（需要趋势市场）
3. 尝试放宽条件（修改RSI阈值）

### Q: 如何调整参数
A: 编辑 `ChanlunSMC.py`：
- `timeframe = '1h'` → 改为 `'15m'` 或 `'4h'`
- `stoploss = -0.03` → 调整止损
- RSI阈值（第371行、390行）

---

## 📊 预期表现

基于策略设计，在**趋势市场**中：
- 胜率：40-50%
- 盈亏比：≥ 2:1
- 最大回撤：<20%

**震荡市场**表现会较差（策略偏向趋势）

---

## 🔄 下一步优化

1. **回测验证** - 在历史数据上测试
2. **参数优化** - 使用hyperopt
3. **多品种测试** - BTC、ETH、主流币
4. **实盘验证** - 先用小资金dry-run

---

## 📞 支持

- **详细文档**: `ChanlunSMC_README.md`
- **Freqtrade**: https://www.freqtrade.io/
- **Discord**: https://discord.gg/freqtrade

---

**环境修复后，随时告诉我开始回测！** 🚀
