#!/usr/bin/env python3
# 独立的下单脚本

import sys
from ib_insync import *

def place_order(ticker, action, quantity):
    """下单函数"""
    try:
        util.startLoop()
        
        ib = IB()
        ib.connect('127.0.0.1', 7497, clientId=41)
        
        # 创建合约
        contract = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        
        # 创建市价订单
        order = MarketOrder(action, quantity)
        
        # 下单
        trade = ib.placeOrder(contract, order)
        
        print(f"ORDER_PLACED:{ticker}:{action}:{quantity}:{trade.order.orderId}")
        
        # 等待订单状态更新
        ib.sleep(2)
        
        # 输出订单状态
        print(f"ORDER_STATUS:{trade.orderStatus.status}")
        
        ib.disconnect()
        
    except Exception as e:
        print(f"ORDER_ERROR:{ticker}:{e}")

def main():
    if len(sys.argv) != 4:
        print("ORDER_ERROR:USAGE:python standalone_order.py TICKER ACTION QUANTITY")
        sys.exit(1)
    
    ticker = sys.argv[1]
    action = sys.argv[2].upper()  # BUY or SELL
    
    try:
        quantity = int(sys.argv[3])
    except ValueError:
        print(f"ORDER_ERROR:{ticker}:Invalid quantity: {sys.argv[3]}")
        sys.exit(1)
    
    if action not in ['BUY', 'SELL']:
        print(f"ORDER_ERROR:{ticker}:Invalid action: {action}")
        sys.exit(1)
    
    place_order(ticker, action, quantity)

if __name__ == "__main__":
    main()