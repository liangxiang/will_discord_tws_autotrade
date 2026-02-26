#!/usr/bin/env python3

from ib_insync import *

# 启动事件循环
util.startLoop()

# 连接TWS - 使用不同的clientId避免冲突
ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=36)
    print("[成功] 连接成功!")
    
    # 测试NVDA
    contract = Stock('NVDA', 'SMART', 'USD')
    print("[步骤] 创建合约: NVDA")
    
    ib.qualifyContracts(contract)
    print("[步骤] 合约限定成功")
    
    ticker = ib.reqMktData(contract, '', False, False)
    print("[步骤] 请求市场数据...")
    
    ib.sleep(1)
    print("[步骤] 等待1秒完成")
    
    print(f"[结果] NVDA last: {ticker.last}")
    print(f"[结果] bid/ask: {ticker.bid} {ticker.ask}")
    
    ib.cancelMktData(contract)
    print("[清理] 取消数据订阅")
    
    ib.disconnect()
    print("[完成] 断开连接")
    
except Exception as e:
    print(f"[错误] 失败: {e}")
    import traceback
    traceback.print_exc()