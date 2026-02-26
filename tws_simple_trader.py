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

class SimpleTWSTrader:
    def __init__(self):
        self.ib = None
        self.connected = False
        
        # 加载配置
        try:
            with open('trading_config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.tws_config = config_data['tws_connection']
        except FileNotFoundError:
            self.tws_config = {"host": "127.0.0.1", "port": 7497, "client_id": 34}
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 启动事件循环
        if IB_AVAILABLE:
            util.startLoop()
    
    def connect_tws(self, host=None, port=None, client_id=None):
        """连接到TWS"""
        try:
            if not IB_AVAILABLE:
                self.logger.error("[错误] ib_insync库不可用")
                return False
            
            # 使用配置文件参数
            host = host or self.tws_config.get("host", "127.0.0.1")
            port = port or self.tws_config.get("port", 7497)
            client_id = client_id or self.tws_config.get("client_id", 34)
                
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
    
    def query_price(self, signal: TradingSignal):
        """查询股票价格"""
        try:
            if not self.connected:
                self.logger.error("[错误] TWS未连接")
                return
            
            self.logger.info(f"[查询] 开始查询 {signal.ticker} 的价格信息...")
            
            # 创建股票合约
            contract = Stock(signal.ticker, 'SMART', 'USD')
            
            # 限定合约，带超时
            self.logger.info(f"[步骤] 正在限定合约 {signal.ticker}...")
            qualified = self.ib.qualifyContracts(contract)
            
            if not qualified:
                self.logger.error(f"[错误] 无法找到合约: {signal.ticker}")
                return
            
            contract = qualified[0]
            self.logger.info(f"[步骤] 合约限定成功: {contract.symbol}")
            
            # 请求市场数据
            self.logger.info(f"[步骤] 请求市场数据...")
            ticker = self.ib.reqMktData(contract, '', False, False)
            
            # 等待数据返回，最多等待3秒
            self.logger.info(f"[步骤] 等待数据返回...")
            self.ib.sleep(3)
            
            # 显示价格信息
            self.logger.info(f"[价格] {signal.ticker} 最新价格:")
            self.logger.info(f"[价格]   Last: ${ticker.last if ticker.last else 'N/A'}")
            self.logger.info(f"[价格]   Bid: ${ticker.bid if ticker.bid else 'N/A'}")
            self.logger.info(f"[价格]   Ask: ${ticker.ask if ticker.ask else 'N/A'}")
            
            # 显示信号信息
            self.logger.info(f"[信号] 信号类型: {signal.signal_type.value}")
            self.logger.info(f"[信号] 触发价格: ${signal.trigger_price}")
            self.logger.info(f"[信号] 当前价格: ${signal.current_price}")
            
            # 取消市场数据订阅
            self.ib.cancelMktData(contract)
            self.logger.info(f"[完成] {signal.ticker} 价格查询完成")
            
        except Exception as e:
            self.logger.error(f"[错误] 查询价格失败: {e}")
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
                
                # 查询价格
                self.query_price(signal)
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
    trader = SimpleTWSTrader()
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