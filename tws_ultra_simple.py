#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from ib_insync import *
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("[WARNING] ib_insync not found. Install with: pip install ib_insync")

class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class TradingSignal:
    ticker: str
    signal_type: SignalType
    trigger_price: float
    current_price: float
    timestamp: datetime
    signal_text: str

class UltraSimpleTWSTrader:
    def __init__(self):
        self.ib = None
        self.connected = False
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 启动事件循环
        if IB_AVAILABLE:
            util.startLoop()
    
    def connect_tws(self, host="127.0.0.1", port=7497, client_id=37):
        """连接到TWS"""
        try:
            if not IB_AVAILABLE:
                self.logger.error("[错误] ib_insync库不可用")
                return False
                
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id)
            self.connected = True
            self.logger.info(f"[成功] TWS连接成功! {host}:{port} (客户端ID: {client_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"[错误] TWS连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.connected and self.ib:
            self.ib.disconnect()
            self.connected = False
            self.logger.info("[断开] TWS连接已断开")
    
    def parse_discord_message(self, message_text: str) -> Optional[TradingSignal]:
        """解析Discord消息，提取交易信号"""
        try:
            # 检查是否包含日内短线触发
            if "日内短线触发" not in message_text:
                return None
            
            # 提取信息的正则表达式
            ticker_match = re.search(r'Ticker:\s+([A-Z]+)', message_text)
            type_match = re.search(r'Type:\s+(LONG|SHORT)', message_text)
            trigger_price_match = re.search(r'Trigger Price:\s+\$([0-9.]+)', message_text)
            current_price_match = re.search(r'Current Price:\s+\$([0-9.]+)', message_text)
            
            if all([ticker_match, type_match, trigger_price_match, current_price_match]):
                signal = TradingSignal(
                    ticker=ticker_match.group(1),
                    signal_type=SignalType(type_match.group(1)),
                    trigger_price=float(trigger_price_match.group(1)),
                    current_price=float(current_price_match.group(1)),
                    timestamp=datetime.now(),
                    signal_text=message_text
                )
                
                self.logger.info(f"[解析] 成功解析交易信号: {signal.ticker} {signal.signal_type.value}")
                return signal
            
        except Exception as e:
            self.logger.error(f"[错误] 解析消息失败: {e}")
        
        return None
    
    def query_price_simple(self, signal: TradingSignal):
        """简化的价格查询 - 模仿测试脚本"""
        try:
            if not self.connected:
                self.logger.error("[错误] TWS未连接")
                return
            
            self.logger.info(f"[查询] 开始查询 {signal.ticker} 价格 (简化模式)...")
            
            # 完全按照你的测试脚本逻辑
            contract = Stock(signal.ticker, 'SMART', 'USD')
            self.logger.info(f"[步骤] 创建合约: {signal.ticker}")
            
            # 跳过qualifyContracts - 在多线程环境中会卡住
            self.logger.info(f"[步骤] 跳过合约限定，直接使用Stock合约")
            
            # 使用历史数据获取最新价格 - 这个方法工作正常！
            self.logger.info(f"[步骤] 请求历史数据获取最新价格...")
            try:
                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime='',
                    durationStr='1 D',
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )
                
                if bars:
                    latest_bar = bars[-1]
                    self.logger.info(f"[价格] {signal.ticker} 最新价格: {latest_bar.close}")
                    self.logger.info(f"[价格] 开高低收: {latest_bar.open}/{latest_bar.high}/{latest_bar.low}/{latest_bar.close}")
                    
                    # 也尝试快照数据作为备用
                    self.logger.info(f"[步骤] 同时获取bid/ask快照...")
                    ticker = self.ib.reqMktData(contract, '', True, False)
                    self.ib.sleep(2)
                    self.logger.info(f"[价格] bid/ask: {ticker.bid}/{ticker.ask}")
                    self.ib.cancelMktData(contract)
                else:
                    self.logger.warning(f"[警告] 没有获取到 {signal.ticker} 的历史数据")
                    
            except Exception as hist_e:
                self.logger.error(f"[错误] 历史数据请求失败: {hist_e}")
                # fallback到快照模式
                try:
                    ticker = self.ib.reqMktData(contract, '', True, False)
                    self.ib.sleep(3)
                    self.logger.info(f"[价格] {signal.ticker} (快照) last: {ticker.last}")
                    self.logger.info(f"[价格] bid/ask: {ticker.bid}/{ticker.ask}")
                    self.ib.cancelMktData(contract)
                except Exception as snap_e:
                    self.logger.error(f"[错误] 快照数据也失败: {snap_e}")
            
            # 显示信号信息
            self.logger.info(f"[信号] 交易信号: {signal.signal_type.value}")
            self.logger.info(f"[信号] 触发价: ${signal.trigger_price}, 当前价: ${signal.current_price}")
            
            # 清理
            self.ib.cancelMktData(contract)
            self.logger.info(f"[完成] {signal.ticker} 查询完成")
            
        except Exception as e:
            self.logger.error(f"[错误] 查询失败: {e}")
            import traceback
            traceback.print_exc()
    
    def process_discord_message(self, message_data: dict):
        """处理来自Discord的消息"""
        try:
            content = message_data.get("content", "")
            author = message_data.get("author", "")
            
            self.logger.info(f"[消息] 收到消息: {author}: {content[:50]}...")
            
            # 解析交易信号
            signal = self.parse_discord_message(content)
            
            if signal:
                self.logger.info(f"[信号] 检测到交易信号! {signal.ticker} {signal.signal_type.value}")
                
                # 使用简化的价格查询
                self.query_price_simple(signal)
            else:
                self.logger.info("[信息] 消息中未找到有效的交易信号")
                
        except Exception as e:
            self.logger.error(f"[错误] 处理Discord消息失败: {e}")
            import traceback
            traceback.print_exc()
    
    def get_status(self) -> dict:
        """获取交易状态"""
        return {
            "connected": self.connected,
            "positions": 0,
            "daily_pnl": 0.0,
            "pending_orders": 0,
            "position_details": {}
        }

if __name__ == "__main__":
    # 测试代码
    trader = UltraSimpleTWSTrader()
    if trader.connect_tws():
        print("[成功] 连接成功，可以开始接收Discord消息")
        try:
            input("按Enter键退出...")
        except KeyboardInterrupt:
            pass
        finally:
            trader.disconnect()
    else:
        print("[失败] 无法连接TWS")