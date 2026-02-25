# Discord频道消息监控系统

🎯 **实时抓取Discord频道消息的完整解决方案**

绕过Discord严格的CSP限制，实现Tampermonkey脚本自动抓取消息并实时传输到Python程序。

## 🚀 系统特点

- ✅ **完全自动化** - 无需手动操作
- ✅ **实时传输** - 消息即时显示
- ✅ **绕过CSP限制** - 使用127.0.0.1地址
- ✅ **稳定可靠** - HTTP POST直接传输
- ✅ **简单易用** - 仅需3个文件

## 📁 文件说明

1. **`discord-channel-monitor.user.js`** - Tampermonkey用户脚本
   - 监控Discord频道新消息
   - 自动POST数据到Python服务器
   
2. **`discord_webhook_server.py`** - Python HTTP服务器
   - 接收Discord消息数据
   - 格式化显示在终端

3. **`README.md`** - 本说明文档

## 🛠️ 安装使用

### 步骤1: 安装Tampermonkey脚本

1. 安装Tampermonkey浏览器扩展
2. 打开Tampermonkey控制面板
3. 点击"创建新脚本"
4. 复制粘贴 `discord-channel-monitor.user.js` 的内容
5. 保存脚本 (Ctrl+S)

### 步骤2: 启动Python服务器

```bash
python discord_webhook_server.py
```

服务器启动后会显示：
```
Discord Webhook服务器启动!
监听地址: http://127.0.0.1:8888/webhook
等待Tampermonkey脚本连接...
```

### 步骤3: 开始监控

1. 打开目标Discord频道 (例如: `https://discord.com/channels/xxx/xxx`)
2. 等待3秒让脚本加载
3. 点击页面右上角的"Start Monitoring"按钮
4. 控制台显示连接成功信息

## 📊 效果展示

**Python终端实时输出：**
```
127.0.0.1 - - [25/Feb/2026 12:30:56] "POST /webhook HTTP/1.1" 200
恭喜!成功接收到Discord数据:
时间: 2026-02-25 12:30:56
用户: Discord用户名
内容: 消息内容
频道: https://discord.com/channels/xxx/xxx
--------------------------------------------------------------------------------
```

## 🔧 技术原理

### 核心突破
Discord的CSP策略阻止大部分外部连接，但允许 `http://127.0.0.1:*`

### 工作流程
1. **Tampermonkey脚本** 监控DOM变化，检测新消息
2. **自动抓取** 消息ID、时间戳、用户名、内容
3. **HTTP POST** 发送JSON数据到 `http://127.0.0.1:8888/webhook`
4. **Python服务器** 接收数据并格式化显示

### CSP绕过策略
- ❌ `localhost` 被阻止
- ✅ `127.0.0.1` 被允许
- ❌ WebSocket连接被阻止  
- ✅ HTTP POST请求成功

## 🛡️ 安全说明

- 本工具仅用于监控**有权限访问**的Discord频道
- 请遵守Discord服务条款和相关法律法规
- 数据仅在本地处理，不上传到任何外部服务器

## 🐛 故障排除

**问题1: 脚本无法连接服务器**
- 确保Python服务器已启动
- 检查防火墙是否阻止8888端口
- 确认使用127.0.0.1而不是localhost

**问题2: 无法检测到新消息**
- 刷新Discord页面重新加载脚本
- 检查浏览器控制台是否有错误信息
- 确认频道有新消息产生

**问题3: 消息格式异常**
- 检查Discord页面DOM结构是否变化
- 查看控制台调试信息定位问题

## 📝 更新日志

- **v1.0** - 初始版本，基本消息监控功能
- **v2.0** - 修复CSP限制，使用127.0.0.1地址
- **v3.0** - 优化消息解析，提高稳定性

---

**开发完成时间:** 2026年2月  
**状态:** ✅ 已测试通过，正常工作