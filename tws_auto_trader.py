#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
import time

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.common import OrderId
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("[WARNING] IB API not found. Install with: pip install ibapi")

class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

@dataclass
class TradingSignal:
    ticker: str
    signal_type: SignalType
    trigger_price: float
    current_price: float
    timestamp: datetime
    signal_text: str

@dataclass
class Position:
    ticker: str
    quantity: int
    entry_price: float
    signal_type: SignalType
    entry_time: datetime
    stop_loss: float
    take_profit: float
    status: str = "OPEN"

class TWSAutoTrader(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        
        # 加载交易配置
        try:
            with open('trading_config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.config = config_data['trading_settings']
                self.tws_config = config_data['tws_connection']
                self.signal_filters = config_data['signal_filters']
        except FileNotFoundError:
            # 默认配置
            self.config = {
                "default_quantity": 100,  # 默认交易股数
                "stop_loss_percent": 0.02,  # 2% 止损
                "take_profit_percent": 0.04,  # 4% 止盈
                "max_positions": 5,  # 最大持仓数量
                "daily_loss_limit": 1000,  # 日亏损限制
                "position_size_percent": 0.1,  # 仓位大小 (10% of portfolio)
            }
            self.tws_config = {"host": "127.0.0.1", "port": 7497, "client_id": 1}
            self.signal_filters = {"required_keywords": ["日内短线触发"]}
        
        # 交易状态
        self.positions: Dict[str, Position] = {}
        self.pending_orders: Dict[int, dict] = {}
        self.daily_pnl = 0.0
        self.next_order_id = 1
        self.connected = False
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def connect_tws(self, host=None, port=None, client_id=None):
        """连接到TWS"""
        try:
            # 使用配置文件中的连接参数
            host = host or self.tws_config.get("host", "127.0.0.1")
            port = port or self.tws_config.get("port", 7497)
            client_id = client_id or self.tws_config.get("client_id", 1)
            
            self.connect(host, port, client_id)
            self.logger.info(f"正在连接TWS: {host}:{port}")
            
            # 等待连接
            timeout = 10
            start_time = time.time()
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if self.connected:
                self.logger.info("TWS连接成功!")
                self.reqIds(-1)  # 请求下一个有效订单ID
                return True
            else:
                self.logger.error("[错误] TWS连接超时")
                return False
                
        except Exception as e:
            self.logger.error(f"连接TWS失败: {e}")
            return False
    
    def connectAck(self):
        """连接确认回调"""
        self.connected = True
        self.logger.info("TWS连接已确认")
    
    def nextValidId(self, orderId: OrderId):
        """接收下一个有效订单ID"""
        self.next_order_id = orderId
        self.logger.info(f"下一个订单ID: {orderId}")
    
    def error(self, reqId: int, errorCode: int, errorString: str):
        """错误处理回调"""
        if errorCode in [2104, 2106, 2158]:  # 数据农场连接警告，可以忽略
            return
        elif errorCode == 502:  # 无法连接TWS
            self.logger.error(f"[错误] 无法连接TWS: {errorString}")
            self.connected = False
        else:
            self.logger.warning(f"[错误] TWS错误 {errorCode}: {errorString}")
    
    def connectionClosed(self):
        """连接关闭回调"""
        self.connected = False
        self.logger.warning("[断开] TWS连接已断开")
    
    def run(self):
        """运行IB API消息循环"""
        while self.connected:
            try:
                time.sleep(0.1)
            except KeyboardInterrupt:
                break
    
    def disconnect(self):
        """断开连接"""
        if self.connected:
            super().disconnect()
            self.connected = False
    
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """接收价格数据回调"""
        if tickType == 1:  # Bid price
            self.logger.info(f"[价格] Bid: ${price:.2f}")
        elif tickType == 2:  # Ask price  
            self.logger.info(f"[价格] Ask: ${price:.2f}")
        elif tickType == 4:  # Last price
            self.logger.info(f"[价格] Last: ${price:.2f}")
    
    def tickSize(self, reqId: int, tickType: int, size: int):
        """接收交易量数据回调"""
        if tickType == 0:  # Bid size
            self.logger.info(f"[数量] Bid Size: {size}")
        elif tickType == 3:  # Ask size
            self.logger.info(f"[数量] Ask Size: {size}")
    
    def parse_discord_message(self, message_text: str) -> Optional[TradingSignal]:
        """解析Discord消息，提取交易信号"""
        try:
            # 检查是否包含日内短线触发
            if "日内短线触发" not in message_text:
                self.logger.info("[解析] 消息不包含'日内短线触发'关键词")
                return None
            
            self.logger.info("[解析] 检测到交易信号关键词，开始解析...")
            
            # 提取信息的正则表达式（允许多个空格）
            ticker_match = re.search(r'Ticker:\s+([A-Z]+)', message_text)
            type_match = re.search(r'Type:\s+(LONG|SHORT)', message_text)  
            trigger_price_match = re.search(r'Trigger Price:\s+\$([0-9.]+)', message_text)
            current_price_match = re.search(r'Current Price:\s+\$([0-9.]+)', message_text)
            
            self.logger.info(f"[解析] Ticker匹配: {ticker_match.group(1) if ticker_match else 'None'}")
            self.logger.info(f"[解析] Type匹配: {type_match.group(1) if type_match else 'None'}")
            self.logger.info(f"[解析] Trigger Price匹配: {trigger_price_match.group(1) if trigger_price_match else 'None'}")
            self.logger.info(f"[解析] Current Price匹配: {current_price_match.group(1) if current_price_match else 'None'}")
            
            if all([ticker_match, type_match, trigger_price_match, current_price_match]):
                signal = TradingSignal(
                    ticker=ticker_match.group(1),
                    signal_type=SignalType(type_match.group(1)),
                    trigger_price=float(trigger_price_match.group(1)),
                    current_price=float(current_price_match.group(1)),
                    timestamp=datetime.now(),
                    signal_text=message_text
                )
                
                self.logger.info(f"[解析] 解析到交易信号: {signal.ticker} {signal.signal_type.value} @ ${signal.current_price}")
                return signal
            else:
                self.logger.warning("[解析] 某些必需字段未匹配成功")
            
        except Exception as e:
            self.logger.error(f"[错误] 解析消息失败: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def create_stock_contract(self, ticker: str) -> Contract:
        """创建股票合约"""
        contract = Contract()
        contract.symbol = ticker
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    def create_market_order(self, action: str, quantity: int) -> Order:
        """创建市价订单"""
        order = Order()
        order.action = action
        order.totalQuantity = quantity
        order.orderType = "MKT"
        return order
    
    def create_stop_order(self, action: str, quantity: int, stop_price: float) -> Order:
        """创建止损订单"""
        order = Order()
        order.action = action
        order.totalQuantity = quantity
        order.orderType = "STP"
        order.auxPrice = stop_price
        return order
    
    def create_limit_order(self, action: str, quantity: int, limit_price: float) -> Order:
        """创建限价订单"""
        order = Order()
        order.action = action
        order.totalQuantity = quantity
        order.orderType = "LMT"
        order.lmtPrice = limit_price
        return order
    
    def calculate_position_size(self, price: float) -> int:
        """计算仓位大小"""
        # 简化版本，可以根据账户净值动态调整
        return self.config["default_quantity"]
    
    def calculate_stop_loss(self, entry_price: float, signal_type: SignalType) -> float:
        """计算止损价格"""
        stop_percent = self.config["stop_loss_percent"]
        if signal_type == SignalType.LONG:
            return entry_price * (1 - stop_percent)
        else:  # SHORT
            return entry_price * (1 + stop_percent)
    
    def calculate_take_profit(self, entry_price: float, signal_type: SignalType) -> float:
        """计算止盈价格"""
        profit_percent = self.config["take_profit_percent"]
        if signal_type == SignalType.LONG:
            return entry_price * (1 + profit_percent)
        else:  # SHORT
            return entry_price * (1 - profit_percent)
    
    def can_open_position(self, signal: TradingSignal) -> Tuple[bool, str]:
        """检查是否可以开仓"""
        # 检查是否已有该股票的持仓
        if signal.ticker in self.positions:
            return False, f"已有 {signal.ticker} 的持仓"
        
        # 检查最大持仓数量
        if len(self.positions) >= self.config["max_positions"]:
            return False, "已达到最大持仓数量"
        
        # 检查日亏损限制
        if self.daily_pnl <= -self.config["daily_loss_limit"]:
            return False, "已达到日亏损限制"
        
        return True, "可以开仓"
    
    def execute_trading_signal(self, signal: TradingSignal):
        """查询股票价格（简化版本，不下单）"""
        try:
            if not self.connected:
                self.logger.error("[错误] TWS未连接")
                return
            
            self.logger.info(f"[查询] 开始查询 {signal.ticker} 的价格信息...")
            
            # 创建合约
            contract = self.create_stock_contract(signal.ticker)
            
            # 请求市场数据
            req_id = 1
            self.reqMktData(req_id, contract, "", False, False, [])
            
            self.logger.info(f"[发送] 已发送 {signal.ticker} 价格查询请求")
            self.logger.info(f"[信号] 信号类型: {signal.signal_type.value}")
            self.logger.info(f"[价格] 触发价格: ${signal.trigger_price}, 当前价格: ${signal.current_price}")
            
            # 等待数据返回
            self.logger.info("[等待] 等待市场数据返回...")
            time.sleep(2)
            
            # 取消市场数据订阅
            self.cancelMktData(req_id)
            self.logger.info("[完成] 价格查询完成")
            
        except Exception as e:
            self.logger.error(f"[错误] 查询价格失败: {e}")
            import traceback
            traceback.print_exc()
    
    def orderStatus(self, orderId: OrderId, status: str, filled: float, 
                   remaining: float, avgFillPrice: float, permId: int,
                   parentId: int, lastFillPrice: float, clientId: int, whyHeld: str):
        """订单状态回调"""
        self.logger.info(f"订单 {orderId} 状态: {status}, 成交: {filled}, 均价: {avgFillPrice}")
        
        if orderId in self.pending_orders and status == "Filled":
            order_info = self.pending_orders[orderId]
            
            if order_info["order_type"] == "ENTRY":
                # 入场订单成交，创建持仓
                self.create_position(order_info, avgFillPrice)
            
            elif order_info["order_type"] in ["STOP_LOSS", "TAKE_PROFIT"]:
                # 止损或止盈订单成交，关闭持仓
                self.close_position(order_info["ticker"], avgFillPrice, order_info["order_type"])
            
            # 清理已完成的订单
            del self.pending_orders[orderId]
    
    def create_position(self, order_info: dict, fill_price: float):
        """创建持仓记录并设置止损止盈"""
        signal = order_info["signal"]
        quantity = order_info["quantity"]
        
        # 调整数量符号
        if signal.signal_type == SignalType.SHORT:
            quantity = -quantity
        
        # 计算止损止盈价格
        stop_loss = self.calculate_stop_loss(fill_price, signal.signal_type)
        take_profit = self.calculate_take_profit(fill_price, signal.signal_type)
        
        # 创建持仓
        position = Position(
            ticker=signal.ticker,
            quantity=quantity,
            entry_price=fill_price,
            signal_type=signal.signal_type,
            entry_time=datetime.now(),
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        self.positions[signal.ticker] = position
        
        self.logger.info(f"[成功] 建仓成功: {signal.ticker} {quantity} @ ${fill_price:.2f}")
        self.logger.info(f"   止损: ${stop_loss:.2f}, 止盈: ${take_profit:.2f}")
        
        # 立即设置止损和止盈订单
        self.place_exit_orders(position)
    
    def place_exit_orders(self, position: Position):
        """设置止损和止盈订单"""
        try:
            contract = self.create_stock_contract(position.ticker)
            abs_quantity = abs(position.quantity)
            
            # 平仓方向（与开仓相反）
            exit_action = "SELL" if position.quantity > 0 else "BUY"
            
            # 止损订单
            stop_order = self.create_stop_order(exit_action, abs_quantity, position.stop_loss)
            stop_order_id = self.next_order_id
            self.placeOrder(stop_order_id, contract, stop_order)
            
            self.pending_orders[stop_order_id] = {
                "ticker": position.ticker,
                "order_type": "STOP_LOSS"
            }
            
            self.next_order_id += 1
            
            # 止盈订单
            profit_order = self.create_limit_order(exit_action, abs_quantity, position.take_profit)
            profit_order_id = self.next_order_id
            self.placeOrder(profit_order_id, contract, profit_order)
            
            self.pending_orders[profit_order_id] = {
                "ticker": position.ticker,
                "order_type": "TAKE_PROFIT"
            }
            
            self.next_order_id += 1
            
            self.logger.info(f"📋 已设置止损止盈订单: {position.ticker}")
            
        except Exception as e:
            self.logger.error(f"设置止损止盈失败: {e}")
    
    def close_position(self, ticker: str, exit_price: float, exit_reason: str):
        """关闭持仓"""
        if ticker in self.positions:
            position = self.positions[ticker]
            
            # 计算盈亏
            if position.signal_type == SignalType.LONG:
                pnl = (exit_price - position.entry_price) * abs(position.quantity)
            else:
                pnl = (position.entry_price - exit_price) * abs(position.quantity)
            
            self.daily_pnl += pnl
            
            self.logger.info(f"[平仓] 平仓: {ticker} @ ${exit_price:.2f}, "
                           f"盈亏: ${pnl:.2f}, 原因: {exit_reason}")
            
            # 移除持仓
            del self.positions[ticker]
    
    def process_discord_message(self, message_data: dict):
        """处理来自Discord的消息"""
        try:
            content = message_data.get("content", "")
            author = message_data.get("author", "")
            
            self.logger.info(f"[消息] 收到消息: {author}: {content[:100]}...")
            
            # 解析交易信号
            self.logger.info("[步骤] 开始解析交易信号...")
            signal = self.parse_discord_message(content)
            
            if signal:
                self.logger.info(f"[信号] 检测到交易信号! Ticker: {signal.ticker}, 类型: {signal.signal_type}")
                
                # 如果未连接TWS，尝试连接
                if not self.connected:
                    self.logger.warning("TWS未连接，尝试重新连接...")
                    if not self.connect_tws():
                        self.logger.error("无法连接TWS，跳过交易")
                        return
                
                self.logger.info("[步骤] 开始执行信号...")
                # 执行交易
                self.execute_trading_signal(signal)
                self.logger.info("[步骤] 信号执行完成")
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
            "positions": len(self.positions),
            "daily_pnl": self.daily_pnl,
            "pending_orders": len(self.pending_orders),
            "position_details": {
                ticker: {
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "entry_time": pos.entry_time.isoformat()
                }
                for ticker, pos in self.positions.items()
            }
        }
    
    def emergency_close_all(self):
        """紧急平仓所有持仓"""
        self.logger.warning("[紧急] 执行紧急平仓!")
        
        for ticker, position in self.positions.items():
            try:
                contract = self.create_stock_contract(ticker)
                abs_quantity = abs(position.quantity)
                exit_action = "SELL" if position.quantity > 0 else "BUY"
                
                order = self.create_market_order(exit_action, abs_quantity)
                order_id = self.next_order_id
                self.placeOrder(order_id, contract, order)
                self.next_order_id += 1
                
                self.logger.info(f"[平仓] 紧急平仓: {ticker}")
                
            except Exception as e:
                self.logger.error(f"紧急平仓失败 {ticker}: {e}")

def main():
    if not IB_AVAILABLE:
        print("请安装IB API: pip install ibapi")
        return
    
    # 创建交易实例
    trader = TWSAutoTrader()
    
    # 连接TWS
    print("正在连接TWS...")
    if trader.connect_tws():
        print("[成功] TWS连接成功，开始监听Discord消息...")
        
        # 启动消息处理循环
        def message_loop():
            while True:
                try:
                    # 这里会集成Discord消息接收
                    # 实际使用时会从webhook接收消息
                    time.sleep(1)
                except KeyboardInterrupt:
                    break
        
        try:
            trader.run()  # 启动IB API事件循环
        except KeyboardInterrupt:
            print("\n正在断开连接...")
            trader.disconnect()
    else:
        print("[失败] 无法连接TWS")

if __name__ == "__main__":
    main()