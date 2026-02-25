// ==UserScript==
// @name         Discord Channel Monitor
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Monitor Discord channel messages
// @author       You
// @match        https://discord.com/channels/*
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_listValues
// @grant        GM_download
// @grant        GM_setClipboard
// @grant        GM_notification
// @grant        unsafeWindow
// ==/UserScript==

(function() {
    'use strict';

    let lastMessageId = '';
    let isMonitoring = false;
    let monitorInterval;
    let websocket = null;
    let wsConnected = false;
    
    // 创建控制面板
    function createControlPanel() {
        const panel = document.createElement('div');
        panel.id = 'discord-monitor-panel';
        panel.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            z-index: 10000;
            background: #2f3136;
            border: 1px solid #555;
            border-radius: 5px;
            padding: 10px;
            font-family: monospace;
            color: white;
            min-width: 200px;
        `;
        
        const title = document.createElement('div');
        title.textContent = 'Discord Channel Monitor';
        title.style.fontWeight = 'bold';
        title.style.marginBottom = '10px';
        
        const status = document.createElement('div');
        status.id = 'monitor-status';
        status.textContent = 'Status: Stopped';
        status.style.marginBottom = '10px';
        
        const startBtn = document.createElement('button');
        startBtn.textContent = 'Start Monitoring';
        startBtn.style.cssText = `
            margin-right: 5px;
            padding: 5px 10px;
            background: #7289da;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
        `;
        startBtn.onclick = startMonitoring;
        
        const stopBtn = document.createElement('button');
        stopBtn.textContent = 'Stop';
        stopBtn.style.cssText = `
            padding: 5px 10px;
            background: #f04747;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
        `;
        stopBtn.onclick = stopMonitoring;
        
        panel.appendChild(title);
        panel.appendChild(status);
        panel.appendChild(startBtn);
        panel.appendChild(stopBtn);
        
        document.body.appendChild(panel);
    }
    
    // 获取消息元素
    function getMessages() {
        // Discord消息的多种选择器，按优先级排序
        const selectors = [
            'li[id^="chat-messages"]',  // 主要的消息容器
            '[id^="message-"]',         // 旧版消息ID
            '[class*="messageListItem"]', // 消息列表项
            '[data-list-item-id^="chat-messages"]', // 数据属性
            'div[class*="message"][class*="cozy"]', // cozy模式消息
            'article[class*="message"]' // 语义化消息元素
        ];
        
        let messages = [];
        for (const selector of selectors) {
            messages = document.querySelectorAll(selector);
            if (messages.length > 0) {
                console.log(`[DEBUG] Found ${messages.length} messages with selector: ${selector}`);
                break;
            }
        }
        
        return messages;
    }
    
    // 提取消息信息
    function extractMessageInfo(messageElement) {
        try {
            console.log('[DEBUG] Processing message element:', messageElement);
            console.log('[DEBUG] Element HTML:', messageElement.outerHTML.substring(0, 500));
            
            // 更准确的选择器，基于Discord的实际DOM结构
            const selectors = {
                timestamp: [
                    'time',
                    '[class*="timestamp"]',
                    '[aria-label*="time"]'
                ],
                author: [
                    '[class*="username"]',
                    '[class*="author"]',
                    'h3 span[class*="username"]',
                    '[role="button"] span[class*="username"]',
                    'span[class*="displayName"]'
                ],
                content: [
                    '[class*="messageContent"]',
                    '[class*="markup"]',
                    'div[class*="content"]:not([class*="compact"])',
                    '[data-slate-editor="true"]'
                ]
            };
            
            // 查找时间戳
            let timestamp = null;
            for (const sel of selectors.timestamp) {
                timestamp = messageElement.querySelector(sel);
                if (timestamp) break;
            }
            
            // 查找作者
            let author = null;
            for (const sel of selectors.author) {
                author = messageElement.querySelector(sel);
                if (author && author.textContent.trim()) break;
            }
            
            // 查找内容
            let content = null;
            for (const sel of selectors.content) {
                content = messageElement.querySelector(sel);
                if (content && content.textContent.trim()) break;
            }
            
            // 备用方法：如果没找到内容，尝试查找所有文本
            if (!content || !content.textContent.trim()) {
                const allText = messageElement.textContent;
                const lines = allText.split('\n').filter(line => line.trim());
                if (lines.length > 1) {
                    // 通常第一行是用户名，后面是内容
                    content = { textContent: lines.slice(1).join(' ').trim() };
                }
            }
            
            const messageInfo = {
                id: messageElement.id || messageElement.getAttribute('data-list-item-id') || `msg-${Date.now()}`,
                timestamp: timestamp ? (timestamp.getAttribute('datetime') || timestamp.textContent) : new Date().toISOString(),
                author: author ? author.textContent.trim() : 'Unknown',
                content: content ? content.textContent.trim() : '',
                element: messageElement
            };
            
            console.log('[DEBUG] Extracted message info:', messageInfo);
            return messageInfo;
        } catch (e) {
            console.error('[DEBUG] Error extracting message info:', e);
            return null;
        }
    }
    
    // 文件写入计数器
    let messageCounter = 0;
    
    // 自动传输数据到外部 (多种方式)
    function autoTransferData(messageInfo) {
        try {
            const messageData = {
                id: messageInfo.id,
                timestamp: messageInfo.timestamp,
                author: messageInfo.author,
                content: messageInfo.content,
                channel_url: window.location.href,
                counter: ++messageCounter
            };
            
            // 方法1: 自动下载JSON文件到Downloads文件夹
            if (typeof GM_download !== 'undefined') {
                const jsonData = JSON.stringify([messageData], null, 2);
                const blob = new Blob([jsonData], {type: 'application/json'});
                const url = URL.createObjectURL(blob);
                
                // 文件名包含时间戳避免覆盖
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                const filename = `discord_message_${messageCounter}_${timestamp}.json`;
                
                GM_download(url, filename, url);
                console.log(`[DEBUG] ✅ Message auto-downloaded as ${filename}`);
            }
            
            // 方法2: 自动复制到剪贴板
            if (typeof GM_setClipboard !== 'undefined') {
                const clipboardData = `[${new Date(messageInfo.timestamp).toLocaleString()}] ${messageInfo.author}: ${messageInfo.content}`;
                GM_setClipboard(clipboardData, 'text');
                console.log('[DEBUG] ✅ Message copied to clipboard');
            }
            
            // 方法3: 系统通知
            if (typeof GM_notification !== 'undefined') {
                GM_notification({
                    title: 'Discord Message',
                    text: `${messageInfo.author}: ${messageInfo.content}`,
                    timeout: 5000,
                    onclick: function() {
                        window.focus();
                    }
                });
                console.log('[DEBUG] ✅ System notification sent');
            }
            
            // 方法4: 修改页面标题 (Python可以监控)
            const originalTitle = document.title;
            document.title = `[${messageCounter}] ${messageInfo.author}: ${messageInfo.content.substring(0, 50)}...`;
            setTimeout(() => {
                document.title = originalTitle;
            }, 2000);
            
            return true;
            
        } catch (error) {
            console.error('[DEBUG] Auto transfer failed:', error.message);
            return false;
        }
    }
    
    // 发送消息到webhook服务器
    async function sendMessageToServer(messageInfo) {
        try {
            console.log('[DEBUG] 发送消息到webhook服务器...');
            
            const messageData = {
                id: messageInfo.id,
                timestamp: messageInfo.timestamp,
                author: messageInfo.author,
                content: messageInfo.content,
                channel_url: window.location.href,
                counter: ++messageCounter
            };
            
            // 方法1: 尝试POST请求到webhook
            try {
                const response = await fetch('http://127.0.0.1:8888/webhook', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(messageData),
                    mode: 'cors'
                });
                
                if (response.ok) {
                    console.log('[DEBUG] ✅ 消息成功发送到webhook服务器!');
                    return true;
                }
                
                console.log('[DEBUG] ❌ Webhook服务器响应错误:', response.status);
                
            } catch (fetchError) {
                console.log('[DEBUG] ❌ POST请求失败:', fetchError.message);
                console.log('[DEBUG] 尝试备用方案...');
            }
            
            // 方法2: 备用 - 自动传输数据
            const transferSuccess = autoTransferData(messageInfo);
            
            // 方法3: 备用 - GM存储
            if (typeof GM_setValue !== 'undefined') {
                const messageWithId = {
                    id: messageInfo.id,
                    timestamp: messageInfo.timestamp,
                    author: messageInfo.author,
                    content: messageInfo.content,
                    processed: false,
                    stored_at: Date.now(),
                    counter: messageCounter
                };
                
                GM_setValue('latest_message', JSON.stringify(messageWithId));
                console.log('[DEBUG] 消息已存储到GM备用存储');
            }
            
            return transferSuccess;
            
        } catch (error) {
            console.error('[DEBUG] 发送消息时出错:', error.message);
            return false;
        }
    }
    
    // 检查新消息
    function checkForNewMessages() {
        console.log('[DEBUG] Checking for new messages...');
        const messages = getMessages();
        if (messages.length === 0) {
            console.log('[DEBUG] No messages found');
            return;
        }
        
        const latestMessage = messages[messages.length - 1];
        const messageInfo = extractMessageInfo(latestMessage);
        
        if (messageInfo) {
            console.log('[DEBUG] Latest message ID:', messageInfo.id, 'Last ID:', lastMessageId);
            
            if (messageInfo.id !== lastMessageId) {
                console.log('[DEBUG] New message detected!');
                
                // 只有当消息有实际内容时才显示
                if (messageInfo.content && messageInfo.content.trim()) {
                    // 直接在控制台输出格式化的消息 (主要输出)
                    const timestamp = new Date(messageInfo.timestamp).toLocaleString();
                    console.log(`%c📢 DISCORD MESSAGE`, 'color: #7289da; font-weight: bold');
                    console.log(`%c[${timestamp}] ${messageInfo.author}: ${messageInfo.content}`, 'color: #ffffff; background: #36393f; padding: 4px 8px; border-radius: 4px;');
                    console.log('─'.repeat(80));
                    
                    // 发送消息到本地存储 (备用)
                    sendMessageToServer(messageInfo);
                } else {
                    console.log('[DEBUG] Message has no content, skipping display');
                }
                
                // 更新状态
                lastMessageId = messageInfo.id;
                updateStatus(`Monitoring... Last: ${messageInfo.author || 'System'}`);
                
                // 自动滚动到底部
                latestMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
            } else {
                console.log('[DEBUG] No new messages');
            }
        } else {
            console.log('[DEBUG] Failed to extract message info');
        }
    }
    
    // 更新状态显示
    function updateStatus(text) {
        const statusElement = document.getElementById('monitor-status');
        if (statusElement) {
            statusElement.textContent = `Status: ${text}`;
        }
    }
    
    // 开始监控
    function startMonitoring() {
        if (isMonitoring) return;
        
        isMonitoring = true;
        updateStatus('Starting...');
        
        // 重置计数器
        messageCounter = 0;
        
        // 获取当前最后一条消息作为起点
        const messages = getMessages();
        if (messages.length > 0) {
            const lastMessage = extractMessageInfo(messages[messages.length - 1]);
            if (lastMessage) {
                lastMessageId = lastMessage.id;
            }
        }
        
        // 开始定期检查
        monitorInterval = setInterval(checkForNewMessages, 2000);
        
        updateStatus('Monitoring...');
        console.log('🚀 Discord channel monitoring started!');
        console.log('📡 Using DOM events and GM storage for data export');
        console.log('💡 Python script can monitor GM storage or page title changes');
    }
    
    // 停止监控
    function stopMonitoring() {
        if (!isMonitoring) return;
        
        isMonitoring = false;
        if (monitorInterval) {
            clearInterval(monitorInterval);
            monitorInterval = null;
        }
        
        updateStatus('Stopped');
        console.log('⏹️ Discord channel monitoring stopped!');
        console.log(`📊 Total messages processed: ${messageCounter}`);
    }
    
    // 等待页面加载完成后初始化
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }
        
        // 等待Discord界面加载
        setTimeout(() => {
            createControlPanel();
            console.log('Discord Channel Monitor loaded! Check the control panel in the top-right corner.');
        }, 3000);
    }
    
    // 初始化
    init();
    
})();