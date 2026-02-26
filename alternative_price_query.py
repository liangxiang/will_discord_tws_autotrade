#!/usr/bin/env python3

from ib_insync import *
import datetime

# 测试不同的价格获取方法

util.startLoop()

ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=38)
    print("[连接] 成功连接 clientId=38")
    
    # 创建NVDA合约
    contract = Stock('NVDA', 'SMART', 'USD')
    print("[合约] 创建NVDA合约")
    
    # 方法1: 历史数据请求获取最新价格
    print("\n=== 方法1: 历史数据请求 ===")
    try:
        bars = ib.reqHistoricalData(
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
            print(f"[历史] NVDA 最新价格: {latest_bar.close}")
            print(f"[历史] 开高低收: {latest_bar.open}/{latest_bar.high}/{latest_bar.low}/{latest_bar.close}")
        else:
            print("[历史] 没有获取到历史数据")
    except Exception as e:
        print(f"[历史] 失败: {e}")
    
    # 方法2: 快照市场数据
    print("\n=== 方法2: 快照市场数据 ===")
    try:
        ticker = ib.reqMktData(contract, '', True, False)  # snapshot=True
        ib.sleep(3)
        print(f"[快照] NVDA last: {ticker.last}")
        print(f"[快照] bid/ask: {ticker.bid}/{ticker.ask}")
        ib.cancelMktData(contract)
    except Exception as e:
        print(f"[快照] 失败: {e}")
    
    # 方法3: 实时数据流
    print("\n=== 方法3: 实时数据流 ===")
    try:
        ticker = ib.reqMktData(contract, '', False, False)  # streaming
        ib.sleep(3)
        print(f"[实时] NVDA last: {ticker.last}")
        print(f"[实时] bid/ask: {ticker.bid}/{ticker.ask}")
        ib.cancelMktData(contract)
    except Exception as e:
        print(f"[实时] 失败: {e}")
    
    ib.disconnect()
    print("\n[完成] 测试完成")
    
except Exception as e:
    print(f"[错误] {e}")
    import traceback
    traceback.print_exc()