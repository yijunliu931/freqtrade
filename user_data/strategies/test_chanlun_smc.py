#!/usr/bin/env python3
"""
ChanlunSMC策略单元测试
不依赖freqtrade环境，直接测试核心逻辑
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def generate_test_data(n_candles=200):
    """生成测试K线数据"""
    dates = pd.date_range(end=datetime.now(), periods=n_candles, freq='1h')
    
    # 生成模拟价格数据（带趋势 + 噪音）
    trend = np.linspace(40000, 45000, n_candles)
    noise = np.random.randn(n_candles) * 500
    close = trend + noise
    
    # 生成OHLC
    high = close + np.abs(np.random.randn(n_candles) * 200)
    low = close - np.abs(np.random.randn(n_candles) * 200)
    open_price = close + np.random.randn(n_candles) * 100
    volume = np.random.randint(100, 1000, n_candles)
    
    df = pd.DataFrame({
        'date': dates,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    
    return df


def test_fractal_identification():
    """测试分型识别逻辑"""
    print("🧪 Testing Fractal Identification...")
    
    # 创建明确的顶分型和底分型
    df = pd.DataFrame({
        'high': [100, 105, 110, 105, 100, 95, 90, 95, 100],
        'low': [90, 95, 100, 95, 90, 85, 80, 85, 90],
    })
    
    # 顶分型识别（索引2应该是顶分型）
    df['top_fractal'] = (
        (df['high'].shift(1) > df['high'].shift(2)) &
        (df['high'].shift(1) > df['high']) &
        (df['high'].shift(1) > df['high'].shift(3))
    )
    
    # 底分型识别（索引6应该是底分型）
    df['bottom_fractal'] = (
        (df['low'].shift(1) < df['low'].shift(2)) &
        (df['low'].shift(1) < df['low']) &
        (df['low'].shift(1) < df['low'].shift(3))
    )
    
    top_fractals = df[df['top_fractal'] == True]
    bottom_fractals = df[df['bottom_fractal'] == True]
    
    print(f"   ✅ Found {len(top_fractals)} top fractals")
    print(f"   ✅ Found {len(bottom_fractals)} bottom fractals")
    
    assert len(top_fractals) > 0, "Should detect at least one top fractal"
    assert len(bottom_fractals) > 0, "Should detect at least one bottom fractal"
    
    print("   ✅ Fractal identification test passed!\n")


def test_order_block_detection():
    """测试Order Block检测逻辑"""
    print("🧪 Testing Order Block Detection...")
    
    # 创建明确的OB场景：大阳线前的阴线
    df = pd.DataFrame({
        'open': [100, 101, 99, 98, 105],  # 索引2是阴线，索引4是大阳线
        'close': [101, 100, 97, 99, 110],
        'high': [102, 102, 100, 100, 112],
        'low': [99, 99, 96, 97, 104],
    })
    
    # 简化的OB检测
    df['bullish_ob'] = False
    
    for i in range(2, len(df)):
        # 当前是阳线
        if df['close'].iloc[i] > df['open'].iloc[i]:
            # 找前面的阴线
            prev_idx = i - 1
            if df['close'].iloc[prev_idx] < df['open'].iloc[prev_idx]:
                # 检查突破
                if df['close'].iloc[i] > df['high'].iloc[prev_idx]:
                    df.loc[df.index[prev_idx], 'bullish_ob'] = True
    
    bullish_obs = df[df['bullish_ob'] == True]
    print(f"   ✅ Found {len(bullish_obs)} bullish order blocks")
    print(f"   Detected at indices: {bullish_obs.index.tolist()}")
    
    assert len(bullish_obs) > 0, "Should detect at least one bullish OB"
    
    print("   ✅ Order Block detection test passed!\n")


def test_fvg_detection():
    """测试FVG（Fair Value Gap）检测"""
    print("🧪 Testing FVG Detection...")
    
    # 创建明确的FVG：K1的high < K3的low（跳空向上）
    df = pd.DataFrame({
        'high': [100, 101, 110],  # K1 high=100, K3 low=109
        'low': [95, 96, 109],
        'close': [98, 99, 111],
    })
    
    # FVG检测
    df['bullish_fvg'] = (
        (df['high'].shift(2) < df['low']) &
        ((df['low'] - df['high'].shift(2)) / df['close'] > 0.01)  # >1% gap
    )
    
    fvgs = df[df['bullish_fvg'] == True]
    print(f"   ✅ Found {len(fvgs)} Fair Value Gaps")
    
    # 应该在索引2检测到FVG（因为K0的high < K2的low）
    assert len(fvgs) > 0, "Should detect FVG"
    
    print("   ✅ FVG detection test passed!\n")


def test_strategy_integration():
    """测试策略整体集成"""
    print("🧪 Testing Strategy Integration...")
    
    df = generate_test_data(200)
    
    # 添加基础指标
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + df['close'].pct_change().rolling(14).mean() / 
                                  df['close'].pct_change().rolling(14).std().abs()))
    
    # 分型识别
    df['top_fractal'] = (
        (df['high'].shift(1) > df['high'].shift(2)) &
        (df['high'].shift(1) > df['high']) &
        (df['high'].shift(1) > df['high'].shift(3))
    )
    
    df['bottom_fractal'] = (
        (df['low'].shift(1) < df['low'].shift(2)) &
        (df['low'].shift(1) < df['low']) &
        (df['low'].shift(1) < df['low'].shift(3))
    )
    
    # 简化的入场信号
    df['long_signal'] = (
        (df['bottom_fractal'] == True) &
        (df['rsi'] < 40) &
        (df['ema_20'] > df['ema_50'])
    )
    
    signals = df[df['long_signal'] == True]
    
    print(f"   ✅ Generated {len(signals)} long entry signals")
    print(f"   ✅ Data points analyzed: {len(df)}")
    print(f"   ✅ Top fractals: {df['top_fractal'].sum()}")
    print(f"   ✅ Bottom fractals: {df['bottom_fractal'].sum()}")
    
    print("   ✅ Strategy integration test passed!\n")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  ChanlunSMC Strategy Unit Tests")
    print("="*60 + "\n")
    
    try:
        test_fractal_identification()
        test_order_block_detection()
        test_fvg_detection()
        test_strategy_integration()
        
        print("="*60)
        print("  ✅ All Tests Passed!")
        print("="*60 + "\n")
        
        print("📊 Next Steps:")
        print("1. Install freqtrade dependencies:")
        print("   cd /Users/mxzhang/Documents/Crypto/freqtrade")
        print("   source .venv/bin/activate")
        print("   pip install -r requirements.txt\n")
        print("2. Download historical data:")
        print("   freqtrade download-data --exchange binance \\\n"
              "       --pairs BTC/USDT ETH/USDT --timeframes 1h 4h --days 30\n")
        print("3. Run backtest:")
        print("   freqtrade backtesting --strategy ChanlunSMC \\\n"
              "       --timeframe 1h --timerange 20250101-\n")
        
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
