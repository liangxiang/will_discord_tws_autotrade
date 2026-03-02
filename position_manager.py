#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class Position:
    ticker: str
    action: str          # BUY (long) / SELL (short)
    total_quantity: int  # original total shares
    remaining_qty: int   # shares still held
    entry_price: float
    entry_time: str      # ISO string
    atr: float           # 14-day ATR at entry

    # Tier split quantities (~1/3 each)
    t1_qty: int = 0
    t2_qty: int = 0
    t3_qty: int = 0      # gets any remainder

    # Dynamic price levels
    stop_loss_price: float = 0.0   # starts at entry - ATR*1.5, moves to entry after T1
    target1_price: float = 0.0     # entry + ATR * target1_factor
    target2_price: float = 0.0     # entry + ATR * target2_factor
    trailing_stop_price: float = 0.0

    # Phase: INITIAL -> T1_HIT -> T2_HIT -> CLOSED
    phase: str = "INITIAL"
    peak_price: float = 0.0  # tracks highest (LONG) or lowest (SHORT) for trailing stop

    order_id: Optional[int] = None
    status: str = "OPEN"


class PositionManager:
    def __init__(self, config_file='trading_config.json'):
        self.positions: Dict[str, Position] = {}
        self.config = self._load_config(config_file)
        self.atr_settings = self.config.get("atr_settings", {
            "atr_period": 14,
            "stop_loss_factor": 1.5,
            "target1_factor": 1.0,
            "target2_factor": 2.0,
            "trailing_stop_factor": 1.0
        })
        self.monitoring = False
        self.monitor_thread = None

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)['trading_settings']
        except FileNotFoundError:
            return {
                "position_size_usd": 10000,
                "atr_settings": {
                    "atr_period": 14,
                    "stop_loss_factor": 1.5,
                    "target1_factor": 1.0,
                    "target2_factor": 2.0,
                    "trailing_stop_factor": 1.0
                },
                "risk_management": {"monitoring_interval_seconds": 5}
            }

    # ------------------------------------------------------------------
    # ATR
    # ------------------------------------------------------------------

    def get_atr(self, ticker: str) -> Optional[float]:
        """通过独立进程获取14日ATR"""
        try:
            period = self.atr_settings.get("atr_period", 14)
            result = subprocess.run(
                ['python', 'standalone_atr_query.py', ticker, str(period)],
                capture_output=True,
                text=True,
                timeout=25
            )
            if result.returncode == 0 and "ATR_DATA:" in result.stdout:
                parts = result.stdout.strip().split(":")
                if len(parts) >= 3:
                    return float(parts[2])
            self.logger.warning(f"[ATR] {ticker} 查询失败: {result.stdout.strip()} {result.stderr.strip()}")
        except Exception as e:
            self.logger.error(f"[ATR] {ticker} 异常: {e}")
        return None

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def calculate_position_size(self, price: float) -> int:
        position_size_usd = self.config.get("position_size_usd", 10000)
        return max(1, int(position_size_usd / price))

    @staticmethod
    def split_into_thirds(total: int):
        """将总股数分成三批"""
        if total < 3:
            t1 = 1 if total >= 1 else 0
            t2 = 1 if total >= 2 else 0
            t3 = max(0, total - t1 - t2)
        else:
            t1 = total // 3
            t2 = total // 3
            t3 = total - t1 - t2  # remainder (could be t1+1 or t2+1)
        return t1, t2, t3

    # ------------------------------------------------------------------
    # Add position
    # ------------------------------------------------------------------

    def add_position(self, ticker: str, action: str, entry_price: float, order_id: int = None):
        """添加新仓位，获取ATR并计算动态止损止盈"""
        # Fetch ATR
        atr = self.get_atr(ticker)
        if atr is None or atr <= 0:
            atr = entry_price * 0.02  # fallback: 2% of price
            self.logger.warning(f"[ATR] {ticker} 使用回退ATR: ${atr:.4f}")
        else:
            self.logger.info(f"[ATR] {ticker} 14日ATR: ${atr:.4f}")

        # Position sizing
        quantity = self.calculate_position_size(entry_price)
        t1_qty, t2_qty, t3_qty = self.split_into_thirds(quantity)

        # Price levels based on ATR
        sl_factor  = self.atr_settings.get("stop_loss_factor",  1.5)
        t1_factor  = self.atr_settings.get("target1_factor",    1.0)
        t2_factor  = self.atr_settings.get("target2_factor",    2.0)

        is_long = (action == "BUY")
        if is_long:
            stop_loss  = entry_price - atr * sl_factor
            target1    = entry_price + atr * t1_factor
            target2    = entry_price + atr * t2_factor
            peak_price = entry_price  # will track highest reached
        else:
            stop_loss  = entry_price + atr * sl_factor
            target1    = entry_price - atr * t1_factor
            target2    = entry_price - atr * t2_factor
            peak_price = entry_price  # will track lowest reached

        position = Position(
            ticker=ticker,
            action=action,
            total_quantity=quantity,
            remaining_qty=quantity,
            entry_price=entry_price,
            entry_time=datetime.now().isoformat(),
            atr=atr,
            t1_qty=t1_qty,
            t2_qty=t2_qty,
            t3_qty=t3_qty,
            stop_loss_price=stop_loss,
            target1_price=target1,
            target2_price=target2,
            trailing_stop_price=0.0,
            phase="INITIAL",
            peak_price=peak_price,
            order_id=order_id,
            status="OPEN"
        )

        self.positions[ticker] = position

        self.logger.info(
            f"[仓位] 新建 {action} {quantity}股 {ticker} @ ${entry_price:.2f} | "
            f"ATR=${atr:.4f}"
        )
        self.logger.info(
            f"[仓位] 止损 ${stop_loss:.2f} | 目标1 ${target1:.2f} | 目标2 ${target2:.2f}"
        )
        self.logger.info(
            f"[仓位] 批次: T1={t1_qty}股 T2={t2_qty}股 T3={t3_qty}股"
        )

        if not self.monitoring:
            self.start_monitoring()

        return position

    # ------------------------------------------------------------------
    # Order execution helpers
    # ------------------------------------------------------------------

    def _run_order(self, ticker: str, close_action: str, qty: int) -> bool:
        """调用独立下单脚本，返回是否成功"""
        try:
            result = subprocess.run(
                ['python', 'standalone_order.py', ticker, close_action, str(qty)],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0 and "ORDER_PLACED:" in result.stdout:
                return True
            self.logger.error(f"[下单] {ticker} 失败: {result.stdout.strip()} {result.stderr.strip()}")
        except Exception as e:
            self.logger.error(f"[下单] {ticker} 异常: {e}")
        return False

    def _close_action(self, position: Position) -> str:
        return "SELL" if position.action == "BUY" else "BUY"

    def execute_partial_close(self, ticker: str, qty: int, reason: str):
        """部分平仓（不从仓位表删除）"""
        position = self.positions.get(ticker)
        if not position or qty <= 0:
            return
        action = self._close_action(position)
        self.logger.info(f"[部分平仓] {ticker} {action} {qty}股 ({reason})")
        self._run_order(ticker, action, qty)

    def execute_full_close(self, ticker: str, reason: str):
        """全部平仓并从仓位表删除"""
        position = self.positions.get(ticker)
        if not position:
            return
        qty = position.remaining_qty
        action = self._close_action(position)
        self.logger.info(f"[全部平仓] {ticker} {action} {qty}股 ({reason})")
        if self._run_order(ticker, action, qty):
            self.remove_position(ticker, reason)
        # Even on failure, log and leave position open for retry

    # ------------------------------------------------------------------
    # Core monitoring logic
    # ------------------------------------------------------------------

    def check_and_update(self, position: Position, current_price: float) -> bool:
        """
        检查仓位条件并执行相应动作。
        返回 True 表示仓位已全部关闭。
        """
        ticker = position.ticker
        is_long = (position.action == "BUY")
        atr = position.atr
        trailing_factor = self.atr_settings.get("trailing_stop_factor", 1.0)

        # ---- INITIAL phase ----
        if position.phase == "INITIAL":
            # Stop loss -> full exit
            if (is_long and current_price <= position.stop_loss_price) or \
               (not is_long and current_price >= position.stop_loss_price):
                self.logger.warning(
                    f"[止损] {ticker} 全部止损! 当前 ${current_price:.2f} | 止损 ${position.stop_loss_price:.2f}"
                )
                self.execute_full_close(ticker, "STOP_LOSS")
                return True

            # Target 1 -> sell first 1/3, move stop to breakeven
            if (is_long and current_price >= position.target1_price) or \
               (not is_long and current_price <= position.target1_price):
                self.logger.info(
                    f"[目标1] {ticker} 达到目标1! 当前 ${current_price:.2f} | 卖出 {position.t1_qty}股"
                )
                self.execute_partial_close(ticker, position.t1_qty, "TARGET1")
                # Move stop to entry (breakeven)
                position.stop_loss_price = position.entry_price
                position.remaining_qty = position.t2_qty + position.t3_qty
                position.phase = "T1_HIT"
                self.logger.info(
                    f"[保本] {ticker} 止损上移至入场价 ${position.entry_price:.2f} | 剩余 {position.remaining_qty}股"
                )

        # ---- T1_HIT phase ----
        elif position.phase == "T1_HIT":
            # Breakeven stop -> sell remaining 2/3
            if (is_long and current_price <= position.stop_loss_price) or \
               (not is_long and current_price >= position.stop_loss_price):
                self.logger.warning(
                    f"[保本止损] {ticker} 触发保本止损! 当前 ${current_price:.2f} | 止损 ${position.stop_loss_price:.2f}"
                )
                self.execute_full_close(ticker, "BREAKEVEN_STOP")
                return True

            # Target 2 -> sell second 1/3, activate trailing stop on last 1/3
            if (is_long and current_price >= position.target2_price) or \
               (not is_long and current_price <= position.target2_price):
                self.logger.info(
                    f"[目标2] {ticker} 达到目标2! 当前 ${current_price:.2f} | 卖出 {position.t2_qty}股"
                )
                self.execute_partial_close(ticker, position.t2_qty, "TARGET2")
                # Activate trailing stop
                position.peak_price = current_price
                if is_long:
                    position.trailing_stop_price = current_price - atr * trailing_factor
                else:
                    position.trailing_stop_price = current_price + atr * trailing_factor
                position.remaining_qty = position.t3_qty
                position.phase = "T2_HIT"
                self.logger.info(
                    f"[追踪止损] {ticker} 激活! 追踪止损 ${position.trailing_stop_price:.2f} | 剩余 {position.remaining_qty}股"
                )

        # ---- T2_HIT phase: trailing stop on final 1/3 ----
        elif position.phase == "T2_HIT":
            if is_long:
                # Update peak and trailing stop upward
                if current_price > position.peak_price:
                    position.peak_price = current_price
                    position.trailing_stop_price = position.peak_price - atr * trailing_factor
                    self.logger.info(
                        f"[追踪止损] {ticker} 更新 -> 高峰 ${position.peak_price:.2f} | 追踪止损 ${position.trailing_stop_price:.2f}"
                    )
                # Check trailing stop hit
                if current_price <= position.trailing_stop_price:
                    self.logger.info(
                        f"[追踪止损] {ticker} 触发! 当前 ${current_price:.2f} | 止损 ${position.trailing_stop_price:.2f}"
                    )
                    self.execute_full_close(ticker, "TRAILING_STOP")
                    return True
            else:
                # Short: track lowest, trailing stop moves down
                if current_price < position.peak_price:
                    position.peak_price = current_price
                    position.trailing_stop_price = position.peak_price + atr * trailing_factor
                    self.logger.info(
                        f"[追踪止损] {ticker} 更新 -> 低谷 ${position.peak_price:.2f} | 追踪止损 ${position.trailing_stop_price:.2f}"
                    )
                if current_price >= position.trailing_stop_price:
                    self.logger.info(
                        f"[追踪止损] {ticker} 触发! 当前 ${current_price:.2f} | 止损 ${position.trailing_stop_price:.2f}"
                    )
                    self.execute_full_close(ticker, "TRAILING_STOP")
                    return True

        return False

    # ------------------------------------------------------------------
    # Price query
    # ------------------------------------------------------------------

    def get_current_price(self, ticker: str) -> Optional[float]:
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
                    val = float(parts[2])
                    return val if val > 0 else None
        except Exception as e:
            self.logger.error(f"[价格] {ticker} 获取失败: {e}")
        return None

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    def monitor_positions(self):
        interval = self.config.get("risk_management", {}).get("monitoring_interval_seconds", 5)
        self.logger.info("[监控] 开始监控仓位...")

        while self.monitoring and self.positions:
            try:
                for ticker, position in list(self.positions.items()):
                    current_price = self.get_current_price(ticker)

                    if current_price:
                        self._log_position_status(position, current_price)
                        self.check_and_update(position, current_price)
                    else:
                        self.logger.warning(f"[监控] {ticker} 无法获取价格")

                time.sleep(interval)

            except Exception as e:
                self.logger.error(f"[监控] 异常: {e}")
                time.sleep(interval)

        self.logger.info("[监控] 监控已停止")

    def _log_position_status(self, position: Position, current_price: float):
        ticker = position.ticker
        if position.phase == "INITIAL":
            self.logger.info(
                f"[监控] {ticker} [初始] 当前 ${current_price:.2f} | "
                f"止损 ${position.stop_loss_price:.2f} | "
                f"目标1 ${position.target1_price:.2f} | "
                f"目标2 ${position.target2_price:.2f} | "
                f"ATR ${position.atr:.4f}"
            )
        elif position.phase == "T1_HIT":
            self.logger.info(
                f"[监控] {ticker} [目标1已达] 当前 ${current_price:.2f} | "
                f"保本止损 ${position.stop_loss_price:.2f} | "
                f"目标2 ${position.target2_price:.2f} | "
                f"剩余 {position.remaining_qty}股"
            )
        elif position.phase == "T2_HIT":
            self.logger.info(
                f"[监控] {ticker} [目标2已达] 当前 ${current_price:.2f} | "
                f"追踪止损 ${position.trailing_stop_price:.2f} | "
                f"高峰 ${position.peak_price:.2f} | "
                f"剩余 {position.remaining_qty}股"
            )

    # ------------------------------------------------------------------
    # Start/stop monitoring
    # ------------------------------------------------------------------

    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_positions, daemon=True)
            self.monitor_thread.start()
            self.logger.info("[监控] 启动仓位监控")

    def stop_monitoring(self):
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        self.logger.info("[监控] 停止仓位监控")

    # ------------------------------------------------------------------
    # Position management helpers
    # ------------------------------------------------------------------

    def remove_position(self, ticker: str, reason: str = "MANUAL"):
        if ticker in self.positions:
            position = self.positions.pop(ticker)
            position.status = reason
            self.logger.info(f"[仓位] 移除 {ticker} ({reason})")
            if not self.positions and self.monitoring:
                self.stop_monitoring()
            return position
        return None

    def get_status(self):
        return {
            "active_positions": len(self.positions),
            "positions": {ticker: asdict(pos) for ticker, pos in self.positions.items()},
            "monitoring": self.monitoring
        }

    def close_all_positions(self):
        """紧急全部平仓"""
        self.logger.warning("[紧急] 执行全部平仓!")
        for ticker in list(self.positions.keys()):
            self.execute_full_close(ticker, "EMERGENCY")


# ------------------------------------------------------------------
# Test / demo
# ------------------------------------------------------------------

if __name__ == "__main__":
    pm = PositionManager()

    # 模拟: 不从TWS获取ATR, 手动设定
    entry = 200.0
    fake_atr = 4.0   # 模拟ATR $4

    # 手动构建一个Position来演示
    t1, t2, t3 = PositionManager.split_into_thirds(50)
    p = Position(
        ticker="TSLA",
        action="BUY",
        total_quantity=50,
        remaining_qty=50,
        entry_price=entry,
        entry_time=datetime.now().isoformat(),
        atr=fake_atr,
        t1_qty=t1,
        t2_qty=t2,
        t3_qty=t3,
        stop_loss_price=entry - fake_atr * 1.5,
        target1_price=entry + fake_atr * 1.0,
        target2_price=entry + fake_atr * 2.0,
        trailing_stop_price=0.0,
        phase="INITIAL",
        peak_price=entry,
    )
    pm.positions["TSLA"] = p

    print(f"仓位详情: {pm.get_status()}")
    print(f"  入场价:  ${p.entry_price:.2f}")
    print(f"  ATR:     ${p.atr:.4f}")
    print(f"  止损:    ${p.stop_loss_price:.2f}  (ATR x1.5 below)")
    print(f"  目标1:   ${p.target1_price:.2f}  (ATR x1.0 above) -> 卖{t1}股,止损移至保本")
    print(f"  目标2:   ${p.target2_price:.2f}  (ATR x2.0 above) -> 卖{t2}股,激活追踪")
    print(f"  目标2后: 追踪止损 = 高峰 - ATR x1.0, 最终卖{t3}股")
    print()
    print("测试完成 (未连接TWS, 不会实际下单)")
