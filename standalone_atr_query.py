#!/usr/bin/env python3
# 独立的ATR查询脚本 - 计算14日平均真实波幅

import sys
from ib_insync import *

def query_atr(ticker, period=14):
    try:
        util.startLoop()

        ib = IB()
        ib.connect('127.0.0.1', 7497, clientId=42)

        contract = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(contract)

        # 请求30天日线数据以确保有足够的bar计算ATR
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='30 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        ib.disconnect()

        if not bars or len(bars) < 2:
            print(f"ERROR:{ticker}:Insufficient historical data")
            return

        # 计算True Range
        trs = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)

        # 取最近period个TR的简单平均
        recent_trs = trs[-period:] if len(trs) >= period else trs
        atr = sum(recent_trs) / len(recent_trs)

        print(f"ATR_DATA:{ticker}:{atr:.4f}:{len(recent_trs)}")

    except Exception as e:
        print(f"ERROR:{ticker}:{e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR:USAGE:python standalone_atr_query.py TICKER [PERIOD]")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    period = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    query_atr(ticker, period)
