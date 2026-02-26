from ib_insync import *

util.startLoop()  # 在某些环境下需要

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=33)  # Paper

contract = Stock('NVDA', 'SMART', 'USD')
ib.qualifyContracts(contract)

ticker = ib.reqMktData(contract, '', False, False)
ib.sleep(1)  # 等待行情

print('NVDA last:', ticker.last)
print('bid/ask:', ticker.bid, ticker.ask)