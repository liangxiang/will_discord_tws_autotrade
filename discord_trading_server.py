#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
from datetime import datetime
import sys
import threading
import time

try:
    from tws_final_simple import FinalSimpleTWSTrader, IB_AVAILABLE
    TRADING_ENABLED = IB_AVAILABLE
except ImportError:
    TRADING_ENABLED = False
    print("[WARNING] TWS Final Simple Trader not available")

class TradingWebhookHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, trader=None, **kwargs):
        self.trader = trader
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        if self.path == '/webhook':
            try:
                # 读取请求体
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                
                # 解析JSON数据
                message_data = json.loads(post_data.decode('utf-8'))
                
                # 记录访问日志
                print(f"{self.client_address[0]} - - [{datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] \"POST /webhook HTTP/1.1\" 200")
                
                # 显示接收的消息
                self.print_discord_message(message_data)
                
                # 如果启用了交易功能，处理交易信号
                if TRADING_ENABLED and self.trader:
                    self.trader.process_discord_message(message_data)
                
                # 返回成功响应
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
                
                response_data = {"status": "success"}
                if TRADING_ENABLED and self.trader:
                    response_data["trading_status"] = self.trader.get_status()
                
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except Exception as e:
                print(f"错误处理消息: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "error"}')
        
        elif self.path == '/status':
            # 获取交易状态
            self.handle_status_request()
            
        elif self.path == '/emergency_close':
            # 紧急平仓
            self.handle_emergency_close()
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/status':
            self.handle_status_request()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        # 处理CORS预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def handle_status_request(self):
        """处理状态查询请求"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            if TRADING_ENABLED and self.trader:
                status = self.trader.get_status()
                response = {
                    "trading_enabled": True,
                    "server_time": datetime.now().isoformat(),
                    **status
                }
            else:
                response = {
                    "trading_enabled": False,
                    "server_time": datetime.now().isoformat(),
                    "message": "Trading module not available"
                }
            
            self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            print(f"状态查询失败: {e}")
    
    def handle_emergency_close(self):
        """处理紧急平仓请求"""
        try:
            if TRADING_ENABLED and self.trader:
                self.trader.emergency_close_all()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "emergency_close_initiated"}')
                
                print("[紧急] 紧急平仓请求已执行")
            else:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "trading_not_available"}')
                
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            print(f"紧急平仓失败: {e}")
    
    def print_discord_message(self, data):
        """格式化并打印Discord消息"""
        try:
            # 解析时间戳
            timestamp_str = data.get('timestamp', '')
            if timestamp_str:
                try:
                    if 'T' in timestamp_str:
                        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        formatted_time = timestamp_str
                except:
                    formatted_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                formatted_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            author = data.get('author', 'Unknown')
            content = data.get('content', '')
            channel_url = data.get('channel_url', '')
            
            # 检查是否包含交易信号
            is_trading_signal = "日内短线触发" in content
            signal_indicator = "🎯 [交易信号]" if is_trading_signal else "📨 [普通消息]"
            
            # 打印格式化的消息
            print(f"{signal_indicator}")
            print(f"时间: {formatted_time}")
            print(f"用户: {author}")
            print(f"内容: {content}")
            if channel_url:
                print(f"频道: {channel_url}")
            
            if is_trading_signal:
                print("🔄 正在分析交易信号...")
            
            print("-" * 80)
            
            # 刷新输出缓冲区
            sys.stdout.flush()
            
        except Exception as e:
            print(f"错误格式化消息: {e}")
    
    def log_message(self, format, *args):
        # 禁用默认的HTTP日志输出，我们自己处理
        pass

class DiscordTradingServer:
    def __init__(self, host='127.0.0.1', port=8888, enable_trading=True):
        self.host = host
        self.port = port
        self.enable_trading = enable_trading
        self.trader = None
        self.server = None
        
    def setup_trader(self):
        """设置自动交易器"""
        if TRADING_ENABLED and self.enable_trading:
            try:
                self.trader = FinalSimpleTWSTrader()
                
                # 在单独线程中连接TWS，不阻塞HTTP服务器启动
                def connect_tws():
                    print("[连接] 正在连接TWS...")
                    try:
                        if self.trader.connect_tws():
                            print("[成功] TWS连接成功!")
                        else:
                            print("[失败] TWS连接失败，将继续运行但不进行自动交易")
                            self.trader = None
                    except Exception as e:
                        print(f"[错误] TWS连接异常: {e}")
                        self.trader = None
                
                # 延迟启动TWS连接，确保HTTP服务器先启动
                def delayed_tws_connect():
                    time.sleep(1)  # 延迟1秒
                    connect_tws()
                
                connect_thread = threading.Thread(target=delayed_tws_connect, daemon=True)
                connect_thread.start()
                
                print("[信息] TWS连接已在后台启动")
                
            except Exception as e:
                print(f"设置交易器失败: {e}")
                self.trader = None
        else:
            print("[警告] 自动交易功能未启用")
    
    def create_handler(self):
        """创建带有trader引用的处理器"""
        def handler(*args, **kwargs):
            return TradingWebhookHandler(*args, trader=self.trader, **kwargs)
        return handler
    
    def start_server(self):
        """启动服务器"""
        try:
            # 设置交易器
            self.setup_trader()
            
            # 创建服务器
            handler_class = self.create_handler()
            self.server = HTTPServer((self.host, self.port), handler_class)
            
            print("[启动] Discord交易服务器启动!")
            print(f"[监听] 监听地址: http://{self.host}:{self.port}")
            print(f"[交易] 交易功能: {'启用' if TRADING_ENABLED and self.enable_trading else '禁用'}")
            print()
            print("[端点] 可用端点:")
            print(f"  POST {self.host}:{self.port}/webhook - 接收Discord消息")
            print(f"  GET  {self.host}:{self.port}/status - 查看交易状态")
            print(f"  POST {self.host}:{self.port}/emergency_close - 紧急平仓")
            print()
            print("[提示] 重要提示:")
            print("  - 请确保TWS已启动并启用API连接")
            print("  - 建议先在模拟账户中测试")
            print("  - 随时可以通过emergency_close紧急平仓")
            print()
            print("[停止] 按 Ctrl+C 停止服务器")
            print("=" * 80)
            
            self.server.serve_forever()
            
        except KeyboardInterrupt:
            print("\\n[停止] 停止服务器...")
            if self.trader:
                print("[断开] 断开TWS连接...")
                self.trader.disconnect()
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            print("[完成] 服务器已停止!")
        except Exception as e:
            print(f"启动服务器失败: {e}")

def main():
    print("Discord自动交易系统")
    print("=" * 50)
    
    if not TRADING_ENABLED:
        print("[警告] 交易功能不可用!")
        print("请安装IB API: pip install ibapi")
        print("或者设置 enable_trading=False 仅运行消息监控")
        print()
    
    # 配置选项 - 启用交易功能
    enable_trading = True
    print("启用交易功能...")
    
    if enable_trading and not TRADING_ENABLED:
        print("[失败] 无法启用交易功能，缺少依赖")
        enable_trading = False
    
    # 创建并启动服务器
    server = DiscordTradingServer(enable_trading=enable_trading)
    server.start_server()

if __name__ == "__main__":
    main()