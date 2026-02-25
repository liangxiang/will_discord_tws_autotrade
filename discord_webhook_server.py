#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
from datetime import datetime
import sys
import threading

class WebhookHandler(BaseHTTPRequestHandler):
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
                
                # 显示成功消息
                print("恭喜!成功接收到Discord数据:")
                
                # 格式化并打印消息
                self.print_discord_message(message_data)
                
                # 返回成功响应
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
                
            except Exception as e:
                print(f"错误处理消息: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "error"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        # 处理CORS预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
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
            
            # 打印格式化的消息
            print(f"时间: {formatted_time}")
            print(f"用户: {author}")
            print(f"内容: {content}")
            if channel_url:
                print(f"频道: {channel_url}")
            print("-" * 80)
            
            # 刷新输出缓冲区
            sys.stdout.flush()
            
        except Exception as e:
            print(f"错误格式化消息: {e}")
    
    def log_message(self, format, *args):
        # 禁用默认的HTTP日志输出，我们自己处理
        pass

def start_webhook_server(host='127.0.0.1', port=8888):
    """启动Webhook服务器"""
    try:
        server = HTTPServer((host, port), WebhookHandler)
        
        print("Discord Webhook服务器启动!")
        print(f"监听地址: http://{host}:{port}/webhook")
        print("等待Tampermonkey脚本连接...")
        print("按 Ctrl+C 停止服务器")
        print("=" * 80)
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n停止Webhook服务器...")
        server.shutdown()
        server.server_close()
        print("服务器已停止!")
    except Exception as e:
        print(f"启动服务器失败: {e}")

if __name__ == "__main__":
    start_webhook_server()