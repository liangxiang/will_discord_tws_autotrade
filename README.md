# Discord自动交易系统

🎯 **Discord消息驱动的自动交易解决方案**

从Discord频道实时抓取交易信号，自动在TWS (Interactive Brokers) 上执行交易，包含完整的风险管理和止损止盈机制。

## 🚀 系统特点

- ✅ **完全自动化** - 从信号识别到订单执行
- ✅ **实时交易** - 毫秒级响应交易信号
- ✅ **风险管理** - 止损止盈、仓位控制、日亏损限制
- ✅ **TWS集成** - 直接对接Interactive Brokers
- ✅ **智能解析** - 自动识别Discord交易信号
- ✅ **安全可靠** - 紧急平仓、错误处理机制

## 📁 文件说明

### 核心文件
1. **`discord-channel-monitor.user.js`** - Tampermonkey用户脚本
   - 监控Discord频道交易信号
   - 实时POST数据到交易服务器

2. **`discord_trading_server.py`** - 主交易服务器
   - 接收Discord消息并解析交易信号
   - 集成TWS自动交易功能
   - 提供状态监控和紧急平仓接口

3. **`tws_auto_trader.py`** - TWS自动交易核心
   - Interactive Brokers API集成
   - 交易信号解析和执行
   - 风险管理和止损止盈逻辑

### 配置和工具文件
4. **`trading_config.json`** - 交易配置文件
   - 交易参数、风险控制设置
   - TWS连接配置、信号过滤规则

5. **`install_requirements.py`** - 依赖安装脚本
   - 自动安装所需Python包
   - 系统配置检查

6. **`README.md`** - 完整使用文档

## 🛠️ 安装使用

### 前置要求
- Python 3.7+
- Interactive Brokers TWS 或 IB Gateway
- Chrome/Edge浏览器 + Tampermonkey扩展

### 步骤1: 安装依赖

```bash
# 自动安装所有依赖
python install_requirements.py

# 或手动安装
pip install ibapi
```

### 步骤2: 配置TWS
1. 启动TWS (Trader Workstation)
2. 登录您的账户 (建议先使用模拟账户测试)
3. 启用API连接: 
   - 配置 → API → 启用ActiveX和Socket客户端
   - 端口设置为7497 (实盘) 或 7498 (模拟)
   - 添加可信IP: 127.0.0.1

### 步骤3: 配置交易参数
编辑 `trading_config.json`:
```json
{
  "trading_settings": {
    "default_quantity": 100,        // 默认交易股数
    "stop_loss_percent": 0.02,      // 止损 2%
    "take_profit_percent": 0.04,    // 止盈 4%
    "max_positions": 5,             // 最大持仓数
    "daily_loss_limit": 1000        // 日亏损限制
  }
}
```

### 步骤4: 安装Tampermonkey脚本
1. 安装Tampermonkey浏览器扩展
2. 复制 `discord-channel-monitor.user.js` 内容
3. 在Tampermonkey中创建新脚本并保存

### 步骤5: 启动交易系统
```bash
python discord_trading_server.py
```

选择启用自动交易功能，系统会自动连接TWS。

### 步骤6: 开始监控
1. 打开目标Discord频道
2. 点击"Start Monitoring"
3. 系统开始监听交易信号

## 📊 效果展示

### 交易信号识别
```
🎯 [交易信号]
时间: 2026-02-25 12:30:56
用户: TradeSignals
内容: 日内短线触发
Ticker: VSAT
Type: LONG  
Trigger Price: $49.68
Current Price: $49.78
🔄 正在分析交易信号...
--------------------------------------------------------------------------------
```

### 自动交易执行
```
📡 解析到交易信号: VSAT LONG @ $49.78
🎯 已下单: BUY 100 VSAT @ Market Price
✅ 建仓成功: VSAT 100 @ $49.79
   止损: $48.79, 止盈: $51.75
📋 已设置止损止盈订单: VSAT
```

### 实时状态监控
访问 `http://127.0.0.1:8888/status` 查看：
```json
{
  "connected": true,
  "positions": 1,
  "daily_pnl": 45.50,
  "pending_orders": 2,
  "position_details": {
    "VSAT": {
      "quantity": 100,
      "entry_price": 49.79,
      "stop_loss": 48.79,
      "take_profit": 51.75,
      "entry_time": "2026-02-25T12:30:56"
    }
  }
}
```

## 🔧 技术架构

### 系统流程
1. **Discord监控** - Tampermonkey脚本实时监控频道消息
2. **信号解析** - 自动识别包含"日内短线触发"的交易信号
3. **TWS集成** - 通过IB API连接TWS执行交易
4. **风险管理** - 自动设置止损止盈，控制仓位和风险
5. **状态监控** - 实时跟踪持仓、订单和盈亏

### 交易信号格式
系统自动解析以下格式的Discord消息：
```
日内短线触发
Ticker: AAPL
Type: LONG
Trigger Price: $150.50
Current Price: $150.75
```

### 风险管理机制
- **止损止盈**: 自动设置2%止损，4%止盈
- **仓位控制**: 限制最大持仓数量和单笔交易金额
- **日损失限制**: 达到日损失上限自动停止交易
- **紧急平仓**: 可通过API立即平仓所有持仓

### TWS连接安全
- 仅连接本地127.0.0.1地址
- 支持模拟账户测试
- 完整的错误处理和重连机制

## 🛡️ 风险提示

⚠️ **重要声明**
- **仅供学习研究使用** - 本工具仅用于技术研究和学习
- **交易有风险** - 股票交易存在亏损风险，请谨慎使用
- **模拟账户测试** - 强烈建议先在模拟账户中充分测试
- **遵守法规** - 请遵守当地金融监管法规和交易所规则
- **个人责任** - 使用本工具产生的盈亏由使用者自行承担

## 🚨 安全措施

- **本地运行** - 所有数据处理均在本地，无外部传输
- **API安全** - TWS连接仅限本地127.0.0.1地址
- **权限控制** - 仅监控有权限访问的Discord频道
- **紧急停止** - 提供紧急平仓和停止交易功能

## 🐛 故障排除

### 常见问题

**问题1: TWS连接失败**
- 确保TWS已启动并登录
- 检查API设置: 配置→API→启用Socket客户端
- 确认端口: 7497(实盘) 或 7498(模拟)
- 检查防火墙设置

**问题2: 交易信号无法识别**
- 检查消息格式是否包含"日内短线触发"
- 确认包含完整的Ticker、Type、Price信息
- 查看服务器日志获取详细错误信息

**问题3: 订单执行失败**
- 检查账户资金是否充足
- 确认股票代码正确且可交易
- 检查交易时间和市场状态

### 日志和监控

**查看实时状态:**
```bash
curl http://127.0.0.1:8888/status
```

**紧急平仓:**
```bash
curl -X POST http://127.0.0.1:8888/emergency_close
```

**查看日志文件:**
- `trading.log` - 详细交易日志
- 服务器终端输出 - 实时状态信息

## 🔄 系统扩展

### 支持的扩展功能
- ✅ 多种信号格式解析
- ✅ 自定义风险参数
- ✅ 多账户支持
- ✅ 实时通知推送
- ✅ 交易历史记录
- ✅ 性能统计分析

### 未来计划
- 📋 机器学习信号过滤
- 📋 多经纪商支持
- 📋 Web管理界面
- 📋 移动端监控App

---

**开发时间:** 2026年2月  
**版本:** v3.0 - Discord自动交易系统  
**状态:** ✅ 已测试，生产就绪