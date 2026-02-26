#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class SimpleWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/webhook':
            try:
                # 读取请求体
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                
                # 解析JSON数据
                message_data = json.loads(post_data.decode('utf-8'))
                
                # 打印接收的消息
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 收到消息:")
                print(f"  作者: {message_data.get('author', 'Unknown')}")
                print(f"  内容: {message_data.get('content', '')}")
                print("-" * 50)
                
                # 返回成功响应
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
                
            except Exception as e:
                print(f"[错误] 处理消息失败: {e}")
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "error"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 8888), SimpleWebhookHandler)
    print("[启动] 简单Webhook服务器启动!")
    print("[监听] 监听地址: http://127.0.0.1:8888")
    print("[停止] 按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\n[停止] 停止服务器...")
        server.shutdown()
        server.server_close()
        print("[完成] 服务器已停止!")