#!/usr/bin/env python3
# 独立的价格查询脚本 - 通过命令行参数接收股票代码

import sys
from ib_insync import *

def query_price(ticker):
    try:
        util.startLoop()
        
        ib = IB()
        ib.connect('127.0.0.1', 7497, clientId=40)
        
        contract = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        
        ticker_obj = ib.reqMktData(contract, '', False, False)
        ib.sleep(1)
        
        print(f"PRICE_DATA:{ticker}:{ticker_obj.last}:{ticker_obj.bid}:{ticker_obj.ask}")
        
        ib.cancelMktData(contract)
        ib.disconnect()
        
    except Exception as e:
        print(f"ERROR:{ticker}:{e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ERROR:USAGE:python standalone_price_query.py TICKER")
        sys.exit(1)
    
    ticker = sys.argv[1]
    query_price(ticker)