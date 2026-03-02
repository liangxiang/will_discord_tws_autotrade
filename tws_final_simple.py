#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum
import logging
import threading
import subprocess
from position_manager import PositionManager

try:
    from ib_insync import *
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("[WARNING] ib_insync not found.")

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

class FinalSimpleTWSTrader:
    def __init__(self):
        self.ib = None
        self.connected = False
        self.lock = threading.Lock()  # 防止并发调用
        
        # 初始化仓位管理器
        self.position_manager = PositionManager()
        
        # 加载交易配置
        try:
            with open('trading_config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.trading_config = config_data['trading_settings']
        except FileNotFoundError:
            # 默认配置
            self.trading_config = {
                "position_size_usd": 10000,
                "enable_trading": True
            }
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 启动事件循环
        if IB_AVAILABLE:
            util.startLoop()
    
    def connect_tws(self, host="127.0.0.1", port=7497, client_id=39):
        """测试独立脚本是否能工作"""
        try:
            self.logger.info("[测试] 测试独立价格查询脚本...")
            
            # 测试独立脚本
            result = subprocess.run(
                ['python', 'standalone_price_query.py', 'NVDA'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and "PRICE_DATA:" in result.stdout:
                self.connected = True
                self.logger.info("[成功] 独立价格查询脚本工作正常!")
                return True
            else:
                self.logger.error(f"[错误] 独立脚本测试失败: {result.stdout} {result.stderr}")
                return False
            
        except Exception as e:
            self.logger.error(f"[错误] 测试独立脚本失败: {e}")
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
            if "日内短线触发" not in message_text:
                return None
            
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
    
    def query_price_subprocess(self, signal: TradingSignal):
        """使用独立进程查询价格 - 避免多线程问题"""
        try:
            self.logger.info(f"[查询] 启动独立进程查询 {signal.ticker} 价格...")
            
            # 调用独立的价格查询脚本
            result = subprocess.run(
                ['python', 'standalone_price_query.py', signal.ticker],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output.startswith("PRICE_DATA:"):
                    # 解析返回的价格数据
                    parts = output.split(":")
                    if len(parts) >= 5:
                        ticker_name = parts[1]
                        last_price = parts[2]
                        bid_price = parts[3] 
                        ask_price = parts[4]
                        
                        self.logger.info(f'[结果] {ticker_name} last: {last_price}')
                        self.logger.info(f'[结果] bid/ask: {bid_price} {ask_price}')
                        
                        # 显示信号信息
                        self.logger.info(f"[信号] 交易信号: {signal.signal_type.value}")
                        self.logger.info(f"[信号] 触发价: ${signal.trigger_price}, 当前价: ${signal.current_price}")
                        self.logger.info(f"[完成] {signal.ticker} 查询完成")
                    else:
                        self.logger.error(f"[错误] 价格数据格式错误: {output}")
                elif output.startswith("ERROR:"):
                    error_msg = output.split(":", 2)[2] if len(output.split(":", 2)) > 2 else output
                    self.logger.error(f"[错误] 独立进程查询失败: {error_msg}")
                else:
                    self.logger.error(f"[错误] 未知输出格式: {output}")
            else:
                self.logger.error(f"[错误] 独立进程执行失败，返回码: {result.returncode}")
                if result.stderr:
                    self.logger.error(f"[错误] 错误信息: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"[错误] {signal.ticker} 价格查询超时")
        except Exception as e:
            self.logger.error(f"[错误] 启动独立进程失败: {e}")
            import traceback
            traceback.print_exc()
    
    def place_order_subprocess(self, signal: TradingSignal):
        """使用独立进程下单"""
        try:
            if not self.trading_config.get("enable_trading", False):
                self.logger.info("[交易] 交易功能已禁用，跳过下单")
                return
            
            # 检查是否已有该股票的仓位
            if signal.ticker in self.position_manager.positions:
                self.logger.info(f"[交易] {signal.ticker} 已有仓位，跳过下单")
                return
            
            # 确定买卖方向
            action = "BUY" if signal.signal_type == SignalType.LONG else "SELL"
            
            # 基于当前价格计算仓位大小（$10,000资金）
            quantity = self.position_manager.calculate_position_size(signal.current_price)
            
            self.logger.info(f"[下单] 准备下单: {action} {quantity} {signal.ticker}")
            
            # 调用独立的下单脚本
            result = subprocess.run(
                ['python', 'standalone_order.py', signal.ticker, action, str(quantity)],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                output_lines = result.stdout.strip().split('\n')
                
                for line in output_lines:
                    if line.startswith("ORDER_PLACED:"):
                        parts = line.split(":")
                        if len(parts) >= 5:
                            ticker_name = parts[1]
                            action_name = parts[2] 
                            quantity_name = parts[3]
                            order_id = int(parts[4])
                            
                            self.logger.info(f"[成功] 订单已提交: {action_name} {quantity_name} {ticker_name}")
                            self.logger.info(f"[订单] 订单ID: {order_id}")
                            
                            # 添加到仓位管理器
                            self.position_manager.add_position(
                                ticker=ticker_name,
                                action=action_name,
                                entry_price=signal.current_price,  # 使用信号中的当前价格作为入场价
                                order_id=order_id
                            )
                    
                    elif line.startswith("ORDER_STATUS:"):
                        status = line.split(":", 1)[1] if ":" in line else line
                        self.logger.info(f"[状态] 订单状态: {status}")
                    
                    elif line.startswith("ORDER_ERROR:"):
                        error_msg = line.split(":", 2)[2] if len(line.split(":", 2)) > 2 else line
                        self.logger.error(f"[错误] 下单失败: {error_msg}")
            else:
                self.logger.error(f"[错误] 下单脚本执行失败，返回码: {result.returncode}")
                if result.stderr:
                    self.logger.error(f"[错误] 错误信息: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"[错误] {signal.ticker} 下单超时")
        except Exception as e:
            self.logger.error(f"[错误] 启动下单进程失败: {e}")
            import traceback
            traceback.print_exc()
    
    def process_discord_message(self, message_data: dict):
        """处理来自Discord的消息"""
        try:
            content = message_data.get("content", "")
            author = message_data.get("author", "")
            
            self.logger.info(f"[消息] 收到消息: {author}: {content[:50]}...")
            
            signal = self.parse_discord_message(content)
            
            if signal:
                self.logger.info(f"[信号] 检测到交易信号! {signal.ticker} {signal.signal_type.value}")
                
                # 先查询价格
                self.query_price_subprocess(signal)
                
                # 然后下单
                self.place_order_subprocess(signal)
            else:
                self.logger.info("[信息] 消息中未找到有效的交易信号")
                
        except Exception as e:
            self.logger.error(f"[错误] 处理Discord消息失败: {e}")
            import traceback
            traceback.print_exc()
    
    def get_status(self) -> dict:
        """获取交易状态"""
        position_status = self.position_manager.get_status()
        
        return {
            "connected": self.connected,
            "positions": position_status["active_positions"],
            "daily_pnl": 0.0,  # TODO: 计算实际盈亏
            "pending_orders": 0,  # TODO: 跟踪挂单
            "position_details": position_status["positions"],
            "monitoring": position_status["monitoring"]
        }
    
    def emergency_close_all(self):
        """紧急平仓所有仓位"""
        self.logger.warning("[紧急] 执行紧急平仓!")
        self.position_manager.close_all_positions()