# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - IP检测服务器
在 GitHub Actions 中启动临时服务器，用于检测代理节点的出口IP
"""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import setup_logger


class IPDetectionHandler(BaseHTTPRequestHandler):
    """IP检测请求处理器"""
    
    def __init__(self, *args, **kwargs):
        self.logger = setup_logger("ip_server")
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        try:
            # 获取客户端真实IP
            client_ip = self.get_client_ip()
            
            # 获取请求信息
            user_agent = self.headers.get('User-Agent', '')
            x_forwarded_for = self.headers.get('X-Forwarded-For', '')
            x_real_ip = self.headers.get('X-Real-IP', '')
            
            # 构建响应数据
            response_data = {
                'ip': client_ip,
                'timestamp': int(time.time()),
                'user_agent': user_agent,
                'x_forwarded_for': x_forwarded_for,
                'x_real_ip': x_real_ip,
                'path': self.path,
                'method': 'GET'
            }
            
            # 根据请求路径返回不同格式
            if self.path == '/ip':
                # 纯文本格式，兼容现有代码
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(client_ip.encode('utf-8'))
                
            elif self.path == '/json':
                # JSON格式，包含详细信息
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            elif self.path == '/health':
                # 健康检查端点
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                health_data = {
                    'status': 'healthy',
                    'timestamp': int(time.time()),
                    'server': 'ip-detection-server'
                }
                self.wfile.write(json.dumps(health_data).encode('utf-8'))
                
            else:
                # 默认返回JSON格式
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
            # 记录访问日志
            self.logger.info(f"IP检测请求: {client_ip} -> {self.path}")
            
        except Exception as e:
            self.logger.error(f"处理请求时发生错误: {e}")
            self.send_error(500, f"Internal Server Error: {e}")
    
    def do_POST(self):
        """处理POST请求"""
        self.do_GET()  # POST请求也返回相同信息
    
    def get_client_ip(self):
        """获取客户端真实IP地址"""
        # 优先级：X-Real-IP > X-Forwarded-For > 直连IP
        
        # 检查 X-Real-IP 头
        x_real_ip = self.headers.get('X-Real-IP')
        if x_real_ip:
            return x_real_ip.strip()
        
        # 检查 X-Forwarded-For 头
        x_forwarded_for = self.headers.get('X-Forwarded-For')
        if x_forwarded_for:
            # X-Forwarded-For 可能包含多个IP，取第一个
            ips = [ip.strip() for ip in x_forwarded_for.split(',')]
            if ips and ips[0]:
                return ips[0]
        
        # 使用直连IP
        return self.client_address[0]
    
    def log_message(self, format, *args):
        """重写日志方法，使用我们的logger"""
        self.logger.debug(f"{self.address_string()} - {format % args}")


class IPDetectionServer:
    """IP检测服务器"""
    
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.logger = setup_logger("ip_detection_server")
        self.running = False
    
    def start(self):
        """启动服务器"""
        try:
            self.server = HTTPServer((self.host, self.port), IPDetectionHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            self.running = True
            
            self.logger.info(f"IP检测服务器已启动: http://{self.host}:{self.port}")
            self.logger.info("可用端点:")
            self.logger.info(f"  - http://{self.host}:{self.port}/ip (纯文本)")
            self.logger.info(f"  - http://{self.host}:{self.port}/json (JSON格式)")
            self.logger.info(f"  - http://{self.host}:{self.port}/health (健康检查)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"启动服务器失败: {e}")
            return False
    
    def stop(self):
        """停止服务器"""
        if self.server:
            self.logger.info("正在停止IP检测服务器...")
            self.server.shutdown()
            self.server.server_close()
            if self.server_thread:
                self.server_thread.join(timeout=5)
            self.running = False
            self.logger.info("IP检测服务器已停止")
    
    def wait_for_ready(self, timeout=10):
        """等待服务器就绪"""
        import requests
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://localhost:{self.port}/health", timeout=2)
                if response.status_code == 200:
                    self.logger.info("服务器就绪")
                    return True
            except:
                pass
            time.sleep(0.5)
        
        self.logger.warning(f"服务器在 {timeout} 秒内未就绪")
        return False
    
    def get_server_url(self):
        """获取服务器URL"""
        if self.running:
            return f"http://localhost:{self.port}"
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="IP检测服务器")
    parser.add_argument("--host", default="0.0.0.0", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=8080, help="服务器监听端口")
    parser.add_argument("--duration", type=int, default=0, help="运行时长(秒)，0表示持续运行")
    
    args = parser.parse_args()
    
    # 创建并启动服务器
    server = IPDetectionServer(args.host, args.port)
    
    if not server.start():
        sys.exit(1)
    
    try:
        if args.duration > 0:
            # 运行指定时长
            server.logger.info(f"服务器将运行 {args.duration} 秒")
            time.sleep(args.duration)
        else:
            # 持续运行直到中断
            server.logger.info("服务器持续运行中，按 Ctrl+C 停止")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        server.logger.info("收到中断信号")
    finally:
        server.stop()


if __name__ == "__main__":
    main()