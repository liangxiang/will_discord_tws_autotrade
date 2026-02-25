# Discord Channel Monitor - 完全自动化系统

🎯 **零手动操作的Discord消息监控系统**

绕过Discord严格的CSP限制，实现Tampermonkey脚本自动抓取消息并传输给Python程序的完全自动化解决方案。

## 🚀 系统架构 (完全自动化)

```
Discord频道 → Tampermonkey脚本 → 自动文件下载/剪贴板 → Python自动检测 → 终端显示
```

**特点:** 无需任何手动导出操作！

## 安装步骤

### 1. 安装Python程序
```bash
# 直接运行Python接收器
python discord_receiver.py
```

### 2. 安装Tampermonkey脚本
1. **安装Tampermonkey扩展**
   - Chrome: 在Chrome Web Store搜索"Tampermonkey"并安装
   - Firefox: 在Firefox Add-ons搜索"Tampermonkey"并安装

2. **安装脚本**
   - 打开Tampermonkey控制面板
   - 点击"创建新脚本"
   - 删除默认内容，复制粘贴`discord-channel-monitor.user.js`的所有内容
   - 保存脚本 (Ctrl+S)

## 🎯 使用方法 (完全自动化)

### ⚡ 全自动方案 (推荐)

**步骤1: 启动Python自动监控器**
```bash
python discord_full_auto_monitor.py
```

**步骤2: 启动Tampermonkey脚本**
1. 打开Discord频道: `https://discord.com/channels/1121213949736656966/1375495804109979698`
2. 点击右上角"Start Monitoring"

**就这样！完全自动化！** 🎉

### 🔄 自动化工作流程

1. **Tampermonkey自动执行:**
   - ✅ 抓取Discord新消息
   - ✅ 自动下载JSON文件到Downloads文件夹
   - ✅ 自动复制消息到剪贴板
   - ✅ 发送系统通知
   - ✅ 修改页面标题

2. **Python自动监控:**
   - ✅ 监控Downloads文件夹新文件
   - ✅ 监控剪贴板变化
   - ✅ 自动清理临时文件
   - ✅ 实时显示新消息

### 🛡️ CSP限制解决方案

Discord的严格CSP策略阻止：
- ❌ HTTP请求 (fetch/XMLHttpRequest)  
- ❌ WebSocket连接
- ❌ 动态script标签

我们的创新解决方案：
- ✅ GM_download API自动下载文件
- ✅ GM_setClipboard API自动复制数据
- ✅ GM_notification API系统通知
- ✅ Python多源自动检测

## 功能特性

- ✅ 实时监控Discord频道新消息
- ✅ 消息数据发送到本地Python程序
- ✅ 终端实时显示消息内容、作者和时间
- ✅ 自动滚动到最新消息
- ✅ 可视化控制面板
- ✅ CORS支持，跨域请求处理

## 文件说明

- `discord-channel-monitor.user.js`: Tampermonkey用户脚本
- `discord_receiver.py`: Python HTTP服务器，接收并处理Discord消息
- `README.md`: 使用说明文档

## 技术细节

- **通信端口**: localhost:8888
- **数据格式**: JSON
- **检查频率**: 每2秒检查一次新消息
- **超时处理**: 包含错误处理和重连机制

## 注意事项

- 必须先启动Python程序，再启动Tampermonkey脚本
- 需要保持Discord标签页打开
- Python程序和浏览器需要在同一台机器上运行
- 按Ctrl+C可以停止Python程序