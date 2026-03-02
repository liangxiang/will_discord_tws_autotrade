#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict

@dataclass
class Position:
    ticker: str
    action: str  # BUY/SELL
    quantity: int
    entry_price: float
    entry_time: datetime
    stop_loss_price: float
    take_profit_price: float
    order_id: Optional[int] = None
    status: str = "OPEN"  # OPEN, CLOSED, STOP_LOSS, TAKE_PROFIT

class PositionManager:
    def __init__(self, config_file='trading_config.json'):
        self.positions: Dict[str, Position] = {}
        self.config = self.load_config(config_file)
        self.monitoring = False
        self.monitor_thread = None
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self, config_file):
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)['trading_settings']
        except FileNotFoundError:
            return {
                "position_size_usd": 10000,
                "stop_loss_percent": 0.02,
                "take_profit_percent": 0.04,
                "risk_management": {"monitoring_interval_seconds": 5}
            }
    
    def calculate_position_size(self, price: float) -> int:
        """计算仓位大小 - 基于$10,000资金"""
        position_size_usd = self.config.get("position_size_usd", 10000)
        quantity = int(position_size_usd / price)
        
        # 至少1股，最多避免超出资金
        return max(1, quantity)
    
    def calculate_stop_loss_take_profit(self, entry_price: float, action: str):
        """计算止损止盈价格"""
        stop_loss_pct = self.config.get("stop_loss_percent", 0.02)
        take_profit_pct = self.config.get("take_profit_percent", 0.04)
        
        if action == "BUY":  # 做多
            stop_loss = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
        else:  # 做空
            stop_loss = entry_price * (1 + stop_loss_pct)
            take_profit = entry_price * (1 - take_profit_pct)
            
        return stop_loss, take_profit
    
    def add_position(self, ticker: str, action: str, entry_price: float, order_id: int = None):
        """添加新仓位"""
        quantity = self.calculate_position_size(entry_price)
        stop_loss, take_profit = self.calculate_stop_loss_take_profit(entry_price, action)
        
        position = Position(
            ticker=ticker,
            action=action,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.now(),
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            order_id=order_id,
            status="OPEN"
        )
        
        self.positions[ticker] = position
        
        self.logger.info(f"[仓位] 新增仓位: {action} {quantity} {ticker} @ ${entry_price:.2f}")
        self.logger.info(f"[仓位] 止损: ${stop_loss:.2f}, 止盈: ${take_profit:.2f}")
        
        # 如果还没开始监控，启动监控
        if not self.monitoring:
            self.start_monitoring()
            
        return position
    
    def remove_position(self, ticker: str, reason: str = "MANUAL"):
        """移除仓位"""
        if ticker in self.positions:
            position = self.positions.pop(ticker)
            position.status = reason
            
            self.logger.info(f"[仓位] 移除仓位: {ticker} ({reason})")
            
            # 如果没有仓位了，停止监控
            if not self.positions and self.monitoring:
                self.stop_monitoring()
                
            return position
        return None
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """获取当前价格"""
        try:
            result = subprocess.run(
                ['python', 'standalone_price_query.py', ticker],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and "PRICE_DATA:" in result.stdout:
                parts = result.stdout.strip().split(":")
                if len(parts) >= 3:
                    return float(parts[2])  # last price
        except Exception as e:
            self.logger.error(f"[价格] 获取 {ticker} 价格失败: {e}")
        
        return None
    
    def check_stop_loss_take_profit(self, position: Position, current_price: float):
        """检查止损止盈条件"""
        ticker = position.ticker
        
        if position.action == "BUY":  # 做多仓位
            if current_price <= position.stop_loss_price:
                self.logger.warning(f"[止损] {ticker} 触发止损! 当前价 ${current_price:.2f} <= 止损价 ${position.stop_loss_price:.2f}")
                self.execute_close_position(ticker, "STOP_LOSS")
                return True
            elif current_price >= position.take_profit_price:
                self.logger.info(f"[止盈] {ticker} 触发止盈! 当前价 ${current_price:.2f} >= 止盈价 ${position.take_profit_price:.2f}")
                self.execute_close_position(ticker, "TAKE_PROFIT")  
                return True
        else:  # 做空仓位
            if current_price >= position.stop_loss_price:
                self.logger.warning(f"[止损] {ticker} 触发止损! 当前价 ${current_price:.2f} >= 止损价 ${position.stop_loss_price:.2f}")
                self.execute_close_position(ticker, "STOP_LOSS")
                return True
            elif current_price <= position.take_profit_price:
                self.logger.info(f"[止盈] {ticker} 触发止盈! 当前价 ${current_price:.2f} <= 止盈价 ${position.take_profit_price:.2f}")
                self.execute_close_position(ticker, "TAKE_PROFIT")
                return True
                
        return False
    
    def execute_close_position(self, ticker: str, reason: str):
        """执行平仓"""
        if ticker not in self.positions:
            return
            
        position = self.positions[ticker]
        
        # 确定平仓方向
        close_action = "SELL" if position.action == "BUY" else "BUY"
        
        try:
            self.logger.info(f"[平仓] 执行平仓: {close_action} {position.quantity} {ticker} ({reason})")
            
            # 调用独立的下单脚本
            result = subprocess.run(
                ['python', 'standalone_order.py', ticker, close_action, str(position.quantity)],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0 and "ORDER_PLACED:" in result.stdout:
                self.logger.info(f"[平仓] {ticker} 平仓订单已提交")
                self.remove_position(ticker, reason)
            else:
                self.logger.error(f"[平仓] {ticker} 平仓失败: {result.stdout} {result.stderr}")
                
        except Exception as e:
            self.logger.error(f"[平仓] {ticker} 平仓异常: {e}")
    
    def monitor_positions(self):
        """监控仓位的主循环"""
        interval = self.config.get("risk_management", {}).get("monitoring_interval_seconds", 5)
        
        self.logger.info("[监控] 开始监控仓位...")
        
        while self.monitoring and self.positions:
            try:
                for ticker, position in list(self.positions.items()):
                    current_price = self.get_current_price(ticker)
                    
                    if current_price:
                        self.logger.info(f"[监控] {ticker}: 当前 ${current_price:.2f}, 入场 ${position.entry_price:.2f}, "
                                       f"止损 ${position.stop_loss_price:.2f}, 止盈 ${position.take_profit_price:.2f}")
                        
                        # 检查止损止盈
                        if self.check_stop_loss_take_profit(position, current_price):
                            continue  # 仓位已关闭，继续下一个
                    else:
                        self.logger.warning(f"[监控] {ticker} 无法获取价格")
                
                time.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"[监控] 监控异常: {e}")
                time.sleep(interval)
        
        self.logger.info("[监控] 监控已停止")
    
    def start_monitoring(self):
        """启动监控"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_positions, daemon=True)
            self.monitor_thread.start()
            self.logger.info("[监控] 启动仓位监控")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        self.logger.info("[监控] 停止仓位监控")
    
    def get_status(self):
        """获取状态"""
        return {
            "active_positions": len(self.positions),
            "positions": {ticker: asdict(pos) for ticker, pos in self.positions.items()},
            "monitoring": self.monitoring
        }
    
    def close_all_positions(self):
        """紧急平仓所有仓位"""
        self.logger.warning("[紧急] 执行全部平仓!")
        
        for ticker in list(self.positions.keys()):
            self.execute_close_position(ticker, "EMERGENCY")

if __name__ == "__main__":
    # 测试代码
    pm = PositionManager()
    
    # 模拟添加仓位
    pm.add_position("NVDA", "BUY", 195.0, 123)
    
    print("测试仓位管理器...")
    print(f"当前仓位: {pm.get_status()}")
    
    input("按Enter键停止...")
    pm.stop_monitoring()