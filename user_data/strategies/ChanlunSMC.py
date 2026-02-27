"""
Chanlun (缠论) + SMC (Smart Money Concepts) Strategy
结合缠论的分型、背驰 + SMC的Order Block、FVG
多周期对齐，高R:R设置
"""

import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone

from freqtrade.strategy import (
    IStrategy,
    Trade,
    informative,
    DecimalParameter,
    IntParameter,
)
import talib.abstract as ta


class ChanlunSMC(IStrategy):
    """
    Chanlun + SMC混合策略
    - 多周期分析（1h, 4h）
    - 分型识别
    - Order Block检测
    - FVG检测
    - 背驰确认
    - 高R:R入场
    """

    INTERFACE_VERSION = 3
    can_short: bool = True  # 支持做空

    # ROI - 高R:R设置，倾向于让价格运行
    minimal_roi = {
        "0": 0.10,  # 10% exit
    }

    # 止损设置
    stoploss = -0.03  # 3% 硬止损，实际由OB动态计算

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.02  # 盈利2%后启动trailing
    trailing_stop_positive_offset = 0.03  # 盈利3%开始trailing
    trailing_only_offset_is_reached = True

    # 时间周期
    timeframe = '1h'

    # 启动蜡烛数量（需要足够历史数据计算指标）
    startup_candle_count: int = 200

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 超参数 - 可优化
    ob_lookback = IntParameter(10, 50, default=20, space="buy", optimize=True)
    fvg_threshold = DecimalParameter(0.001, 0.01, default=0.003, space="buy", optimize=True)
    min_rr_ratio = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=True)

    # Order配置
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    # ==================== 多周期数据 ====================
    
    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        4小时周期 - 用于确认大趋势
        """
        # EMA趋势
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # MACD - 用于背驰
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macd_signal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']
        
        # ATR - 用于波动性
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # 趋势方向
        dataframe['trend_up'] = (
            (dataframe['ema_20'] > dataframe['ema_50']) & 
            (dataframe['ema_50'] > dataframe['ema_200'])
        )
        dataframe['trend_down'] = (
            (dataframe['ema_20'] < dataframe['ema_50']) & 
            (dataframe['ema_50'] < dataframe['ema_200'])
        )
        
        return dataframe

    # ==================== 主周期指标 ====================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        1小时周期 - 主要交易周期
        计算：分型、Order Block、FVG、背驰
        """
        
        # === 基础指标 ===
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # MACD
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macd_signal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Volume
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=20).mean()
        
        # === Chanlun 分型识别 ===
        dataframe = self.identify_fractals(dataframe)
        
        # === SMC Order Block 识别 ===
        dataframe = self.identify_order_blocks(dataframe)
        
        # === FVG（Fair Value Gap）识别 ===
        dataframe = self.identify_fvg(dataframe)
        
        # === 背驰检测 ===
        dataframe = self.detect_divergence(dataframe)
        
        return dataframe

    # ==================== Chanlun 分型识别 ====================
    
    def identify_fractals(self, dataframe: DataFrame) -> DataFrame:
        """
        识别缠论分型
        顶分型：中间K线高点最高
        底分型：中间K线低点最低
        """
        # 顶分型（Top Fractal）
        dataframe['top_fractal'] = (
            (dataframe['high'].shift(1) > dataframe['high'].shift(2)) &
            (dataframe['high'].shift(1) > dataframe['high']) &
            (dataframe['high'].shift(1) > dataframe['high'].shift(3))
        )
        
        # 底分型（Bottom Fractal）
        dataframe['bottom_fractal'] = (
            (dataframe['low'].shift(1) < dataframe['low'].shift(2)) &
            (dataframe['low'].shift(1) < dataframe['low']) &
            (dataframe['low'].shift(1) < dataframe['low'].shift(3))
        )
        
        return dataframe

    # ==================== SMC Order Block 识别 ====================
    
    def identify_order_blocks(self, dataframe: DataFrame) -> DataFrame:
        """
        识别Order Block（机构订单区域）
        逻辑：强势突破前的最后一个相反色K线
        """
        lookback = self.ob_lookback.value
        
        # 牛市OB（Bullish Order Block）- 上涨前的最后一个阴线
        dataframe['bullish_ob'] = False
        dataframe['bullish_ob_low'] = np.nan
        dataframe['bullish_ob_high'] = np.nan
        
        # 熊市OB（Bearish Order Block）- 下跌前的最后一个阳线
        dataframe['bearish_ob'] = False
        dataframe['bearish_ob_low'] = np.nan
        dataframe['bearish_ob_high'] = np.nan
        
        for i in range(lookback, len(dataframe)):
            # 检测牛市OB：找到大阳线前的最后一个阴线
            if dataframe['close'].iloc[i] > dataframe['open'].iloc[i]:  # 当前是阳线
                # 看前面是否有阴线 + 后面价格突破
                for j in range(1, min(5, i)):
                    prev_idx = i - j
                    if dataframe['close'].iloc[prev_idx] < dataframe['open'].iloc[prev_idx]:  # 阴线
                        # 检查是否是强势突破
                        if dataframe['close'].iloc[i] > dataframe['high'].iloc[prev_idx]:
                            dataframe.loc[dataframe.index[prev_idx], 'bullish_ob'] = True
                            dataframe.loc[dataframe.index[prev_idx], 'bullish_ob_low'] = dataframe['low'].iloc[prev_idx]
                            dataframe.loc[dataframe.index[prev_idx], 'bullish_ob_high'] = dataframe['high'].iloc[prev_idx]
                            break
            
            # 检测熊市OB：找到大阴线前的最后一个阳线
            if dataframe['close'].iloc[i] < dataframe['open'].iloc[i]:  # 当前是阴线
                for j in range(1, min(5, i)):
                    prev_idx = i - j
                    if dataframe['close'].iloc[prev_idx] > dataframe['open'].iloc[prev_idx]:  # 阳线
                        if dataframe['close'].iloc[i] < dataframe['low'].iloc[prev_idx]:
                            dataframe.loc[dataframe.index[prev_idx], 'bearish_ob'] = True
                            dataframe.loc[dataframe.index[prev_idx], 'bearish_ob_low'] = dataframe['low'].iloc[prev_idx]
                            dataframe.loc[dataframe.index[prev_idx], 'bearish_ob_high'] = dataframe['high'].iloc[prev_idx]
                            break
        
        # Forward fill OB区域（保持有效直到被破坏）
        dataframe['active_bullish_ob_low'] = dataframe['bullish_ob_low'].ffill()
        dataframe['active_bullish_ob_high'] = dataframe['bullish_ob_high'].ffill()
        dataframe['active_bearish_ob_low'] = dataframe['bearish_ob_low'].ffill()
        dataframe['active_bearish_ob_high'] = dataframe['bearish_ob_high'].ffill()
        
        return dataframe

    # ==================== FVG 识别 ====================
    
    def identify_fvg(self, dataframe: DataFrame) -> DataFrame:
        """
        识别Fair Value Gap（公平价值缺口）
        FVG = 三根K线中间出现的价格跳空
        """
        threshold = self.fvg_threshold.value
        
        # 牛市FVG：K1的high < K3的low
        dataframe['bullish_fvg'] = (
            (dataframe['high'].shift(2) < dataframe['low']) &
            ((dataframe['low'] - dataframe['high'].shift(2)) / dataframe['close'] > threshold)
        )
        dataframe['bullish_fvg_low'] = np.where(
            dataframe['bullish_fvg'],
            dataframe['high'].shift(2),
            np.nan
        )
        dataframe['bullish_fvg_high'] = np.where(
            dataframe['bullish_fvg'],
            dataframe['low'],
            np.nan
        )
        
        # 熊市FVG：K1的low > K3的high
        dataframe['bearish_fvg'] = (
            (dataframe['low'].shift(2) > dataframe['high']) &
            ((dataframe['low'].shift(2) - dataframe['high']) / dataframe['close'] > threshold)
        )
        dataframe['bearish_fvg_low'] = np.where(
            dataframe['bearish_fvg'],
            dataframe['high'],
            np.nan
        )
        dataframe['bearish_fvg_high'] = np.where(
            dataframe['bearish_fvg'],
            dataframe['low'].shift(2),
            np.nan
        )
        
        return dataframe

    # ==================== 背驰检测 ====================
    
    def detect_divergence(self, dataframe: DataFrame) -> DataFrame:
        """
        检测MACD背驰
        价格新高但MACD不新高（看跌背驰）
        价格新低但MACD不新低（看涨背驰）
        """
        lookback = 20
        
        # 找最近的price peaks/troughs
        dataframe['price_peak'] = dataframe['high'].rolling(window=lookback, center=True).max() == dataframe['high']
        dataframe['price_trough'] = dataframe['low'].rolling(window=lookback, center=True).min() == dataframe['low']
        
        # 看跌背驰（Bearish Divergence）
        # 价格创新高，但MACD histogram 降低
        dataframe['bearish_div'] = (
            dataframe['price_peak'] &
            (dataframe['high'] > dataframe['high'].shift(lookback)) &
            (dataframe['macd_hist'] < dataframe['macd_hist'].shift(lookback))
        )
        
        # 看涨背驰（Bullish Divergence）
        # 价格创新低，但MACD histogram 升高
        dataframe['bullish_div'] = (
            dataframe['price_trough'] &
            (dataframe['low'] < dataframe['low'].shift(lookback)) &
            (dataframe['macd_hist'] > dataframe['macd_hist'].shift(lookback))
        )
        
        return dataframe

    # ==================== 入场信号 ====================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        多头入场条件：
        1. 4h趋势向上（ema对齐）
        2. 价格回调至1h的bullish OB或FVG
        3. 出现底分型
        4. MACD看涨背驰
        5. RSI < 40（超卖）
        6. R:R ≥ 2:1
        """
        
        # 做多信号
        dataframe.loc[
            (
                # 1. 高周期趋势确认
                (dataframe['trend_up_4h'] == True) &
                
                # 2. 价格在OB或FVG区域
                (
                    (
                        (dataframe['close'] >= dataframe['active_bullish_ob_low']) &
                        (dataframe['close'] <= dataframe['active_bullish_ob_high'])
                    ) |
                    (dataframe['bullish_fvg'] == True)
                ) &
                
                # 3. 底分型确认
                (dataframe['bottom_fractal'] == True) &
                
                # 4. MACD背驰或转强
                (
                    (dataframe['bullish_div'] == True) |
                    (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1))
                ) &
                
                # 5. RSI超卖
                (dataframe['rsi'] < 40) &
                
                # 6. Volume确认
                (dataframe['volume'] > dataframe['volume_ma'] * 0.8) &
                
                # 7. 价格在EMA上方（结构支撑）
                (dataframe['close'] > dataframe['ema_50'])
            ),
            'enter_long'
        ] = 1

        # 做空信号
        dataframe.loc[
            (
                # 1. 高周期趋势向下
                (dataframe['trend_down_4h'] == True) &
                
                # 2. 价格在bearish OB或FVG区域
                (
                    (
                        (dataframe['close'] >= dataframe['active_bearish_ob_low']) &
                        (dataframe['close'] <= dataframe['active_bearish_ob_high'])
                    ) |
                    (dataframe['bearish_fvg'] == True)
                ) &
                
                # 3. 顶分型确认
                (dataframe['top_fractal'] == True) &
                
                # 4. MACD背驰或转弱
                (
                    (dataframe['bearish_div'] == True) |
                    (dataframe['macd_hist'] < dataframe['macd_hist'].shift(1))
                ) &
                
                # 5. RSI超买
                (dataframe['rsi'] > 60) &
                
                # 6. Volume确认
                (dataframe['volume'] > dataframe['volume_ma'] * 0.8) &
                
                # 7. 价格在EMA下方
                (dataframe['close'] < dataframe['ema_50'])
            ),
            'enter_short'
        ] = 1

        return dataframe

    # ==================== 出场信号 ====================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场条件：
        - 反向分型出现
        - MACD反向背驰
        - 突破关键EMA
        """
        
        # 多头出场
        dataframe.loc[
            (
                (
                    (dataframe['top_fractal'] == True) |  # 顶分型
                    (dataframe['bearish_div'] == True) |  # 看跌背驰
                    (dataframe['close'] < dataframe['ema_21'])  # 跌破快速EMA
                ) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'
        ] = 1

        # 空头出场
        dataframe.loc[
            (
                (
                    (dataframe['bottom_fractal'] == True) |  # 底分型
                    (dataframe['bullish_div'] == True) |  # 看涨背驰
                    (dataframe['close'] > dataframe['ema_21'])  # 突破快速EMA
                ) &
                (dataframe['volume'] > 0)
            ),
            'exit_short'
        ] = 1

        return dataframe

    # ==================== 自定义止损 ====================

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs
    ) -> Optional[float]:
        """
        动态止损：基于ATR和Order Block
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        
        last_candle = dataframe.iloc[-1]
        atr = last_candle['atr']
        
        # 基于ATR的动态止损
        if trade.is_short:
            # 空头：止损在OB上方 + 1 ATR
            sl_price = last_candle.get('active_bearish_ob_high', current_rate) + atr
            return (sl_price - current_rate) / current_rate
        else:
            # 多头：止损在OB下方 - 1 ATR
            sl_price = last_candle.get('active_bullish_ob_low', current_rate) - atr
            return (current_rate - sl_price) / current_rate
