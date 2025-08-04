# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 节点健康检查器 (国内可达性 + 延迟)
"""

import argparse
import subprocess
import time
import urllib.parse
import sys
import os
import signal
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import NodeTestConfig, PathConfig
from core.logger import setup_logger

class NodeHealthChecker:
    """节点健康检查器，包含国内可达性测试和延迟测试"""
    
    def __init__(self, args):
        self.logger = setup_logger("node_health_checker")
        self.args = args
        self.mihomo_process = None
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self.logger.info(f"收到信号 {signum}，开始清理资源...")
        self.cleanup()
        sys.exit(0)

    def _check_china_connectivity(self, proxy: dict) -> bool:
        """使用代理自身，通过在线网站测试其国内可达性。"""
        proxy_name = proxy.get('name')
        server_ip = proxy.get('server')
        port = proxy.get('port')
        proxy_type = proxy.get('type')

        # 仅支持常见的可被 requests 使用的代理类型
        if proxy_type not in ['ss', 'ssr', 'vmess', 'trojan']:
            self.logger.debug(f"节点 '{proxy_name}' 类型 '{proxy_type}' 不支持进行国内可达性测试，默认通过。")
            return True

        # 为 requests 设置代理
        # 注意：这需要一个socks5的本地端口，mihomo启动时会提供
        proxies = {
            'http': f'socks5://127.0.0.1:{self.args.mixed_port}',
            'https': f'socks5://127.0.0.1:{self.args.mixed_port}'
        }

        # 切换 mihomo 核心的代理
        try:
            switch_url = f"http://127.0.0.1:9090/proxies/GLOBAL"
            req_body = {"name": proxy_name}
            requests.put(switch_url, json=req_body, timeout=5)
            self.logger.info(f"[国内可达性] 核心已切换至代理: '{proxy_name}'")
        except Exception as e:
            self.logger.warning(f"[国内可达性] 切换代理 '{proxy_name}' 失败: {e}")
            return False

        # 使用站长工具进行TCPing测试
        # 为避免被封，我们只随机选择一个国内探测点
        test_url = f"http://tool.chinaz.com/port?host={server_ip}&port={port}&protocol=tcp"
        self.logger.info(f"[国内可达性] 正在通过 '{proxy_name}' 请求: {test_url}")

        try:
            with requests.Session() as s:
                s.proxies = proxies
                response = s.get(test_url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
                response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            result_div = soup.find('div', class_='port-result')
            if not result_div:
                self.logger.warning(f"[国内可达性] 节点 '{proxy_name}' 未能在页面中找到结果。默认失败。")
                return False

            # 检查结果是否包含“开放”
            if 'class="Open"' in str(result_div) or '开启' in result_div.text:
                self.logger.info(f"[国内可达性] 节点 '{proxy_name}' 测试通过！")
                return True
            else:
                self.logger.warning(f"[国内可达性] 节点 '{proxy_name}' 测试失败，端口可能关闭或被墙。")
                return False

        except Exception as e:
            self.logger.error(f"[国内可达性] 节点 '{proxy_name}' 在测试过程中发生错误: {e}")
            return False

    def _check_delay(self, proxy: dict) -> tuple:
        """测试单个代理的延迟"""
        proxy_name = proxy.get("name")
        try:
            api_url = "127.0.0.1:9090"
            test_url = self.args.test_url
            timeout = self.args.timeout
            delay_limit = self.args.delay_limit

            quoted_proxy_name = urllib.parse.quote(proxy_name)
            url = f"http://{api_url}/proxies/{quoted_proxy_name}/delay?timeout={timeout}&url={urllib.parse.quote(test_url)}"
            
            response = requests.get(url, timeout=(timeout / 1000) + 5)
            response.raise_for_status()
            data = response.json()
            delay = data.get("delay", -1)
            
            if 0 < delay <= delay_limit:
                self.logger.info(f"[延迟测试] 节点 '{proxy_name}' 通过: {delay}ms")
                return proxy, delay
            else:
                self.logger.debug(f"[延迟测试] 节点 '{proxy_name}' 失败: {delay}ms")
                return None
        except Exception as e:
            self.logger.debug(f"[延迟测试] 节点 '{proxy_name}' 异常: {e}")
            return None

    def run(self) -> None:
        """主执行函数"""
        self.logger.info("节点健康检查器启动...")
        test_config_path = "config_for_test.yaml"
        
        try:
            # 1. 准备配置文件并启动mihomo
            with open(self.args.input_file, 'r', encoding='utf-8') as f:
                proxies_data = yaml.safe_load(f)
            
            if not proxies_data or 'proxies' not in proxies_data:
                self.logger.error("输入文件无效或不包含代理节点")
                return

            proxies_to_test = proxies_data['proxies']
            self.logger.info(f"共加载 {len(proxies_to_test)} 个节点准备进行健康检查。")

            # 创建一个包含所有节点的测试配置
            test_config = {
                'mixed-port': self.args.mixed_port,
                'external-controller': '127.0.0.1:9090',
                'proxies': proxies_to_test,
                'proxy-groups': [{'name': 'GLOBAL', 'type': 'select', 'proxies': [p['name'] for p in proxies_to_test]}],
                'rules': ['MATCH,GLOBAL']
            }
            with open(test_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(test_config, f, allow_unicode=True)

            self.mihomo_process = subprocess.Popen([self.args.clash_path, "-f", test_config_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(5) # 等待mihomo启动
            if self.mihomo_process.poll() is not None:
                self.logger.error(f"Mihomo 进程启动失败!\n{self.mihomo_process.stderr.read()}")
                return
            self.logger.info("Mihomo 核心已成功启动。")

            # 2. 并发执行国内可达性测试
            self.logger.info(f"开始并发执行国内可达性测试，共 {len(proxies_to_test)} 个节点...")
            accessible_proxies = []
            with ThreadPoolExecutor(max_workers=self.args.max_workers) as executor:
                future_to_proxy = {executor.submit(self._check_china_connectivity, proxy): proxy for proxy in proxies_to_test}
                for future in as_completed(future_to_proxy):
                    if future.result():
                        accessible_proxies.append(future_to_proxy[future])
            self.logger.info(f"国内可达性测试完成，共 {len(accessible_proxies)} 个节点通过。")

            # 3. 对通过的节点进行延迟测试
            self.logger.info(f"开始对通过可达性测试的 {len(accessible_proxies)} 个节点进行延迟测试...")
            # 需要重新生成一个只包含可达节点的配置文件给mihomo
            test_config['proxies'] = accessible_proxies
            test_config['proxy-groups'][0]['proxies'] = [p['name'] for p in accessible_proxies]
            with open(test_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(test_config, f, allow_unicode=True)
            # 通过API重载配置
            requests.put('http://127.0.0.1:9090/configs?force=true', json={"path": os.path.abspath(test_config_path)}, timeout=5)
            self.logger.info("Mihomo 已重载配置，仅包含可达节点。")
            time.sleep(3)

            healthy_proxies_with_delay = []
            with ThreadPoolExecutor(max_workers=self.args.max_workers) as executor:
                future_to_proxy = {executor.submit(self._check_delay, proxy): proxy for proxy in accessible_proxies}
                for future in as_completed(future_to_proxy):
                    result = future.result()
                    if result:
                        healthy_proxies_with_delay.append(result)
            self.logger.info(f"延迟测试完成，最终健康节点: {len(healthy_proxies_with_delay)} 个。")

            # 4. 保存最终结果
            proxies_to_save = []
            for proxy, delay in healthy_proxies_with_delay:
                proxy['_delay'] = delay
                proxies_to_save.append(proxy)
            with open(self.args.output_file, 'w', encoding='utf-8') as f:
                yaml.dump({'proxies': proxies_to_save}, f, allow_unicode=True)
            self.logger.info(f"健康节点列表已保存到 {self.args.output_file}")

        except Exception as e:
            self.logger.error(f"节点健康检查过程中发生严重错误: {e}", exc_info=True)
        finally:
            self.cleanup()

    def cleanup(self):
        if self.mihomo_process:
            self.logger.info("正在停止 mihomo 进程...")
            self.mihomo_process.terminate()
            self.mihomo_process.wait(timeout=5)
            self.mihomo_process = None
            self.logger.info("Mihomo 进程已停止。")

def main():
    parser = argparse.ArgumentParser(description="Clash/mihomo 节点健康检查器")
    parser.add_argument("-i", "--input-file", required=True, help="输入的 clash 配置文件路径")
    parser.add_argument("-o", "--output-file", required=True, help="保存健康代理列表的文件路径")
    parser.add_argument("-p", "--clash-path", required=True, help="mihomo 可执行文件路径")
    parser.add_argument("--mixed-port", type=int, default=7890, help="mihomo 的 mixed-port")
    parser.add_argument("--test-url", default=NodeTestConfig.DEFAULT_TEST_URL, help="测试代理延迟的URL")
    parser.add_argument("--delay-limit", type=int, default=NodeTestConfig.DEFAULT_DELAY_LIMIT, help="最大可接受延迟(ms)")
    parser.add_argument("--timeout", type=int, default=NodeTestConfig.DEFAULT_TIMEOUT, help="延迟测试请求超时时间(ms)")
    parser.add_argument("--max-workers", type=int, default=NodeTestConfig.DEFAULT_MAX_WORKERS, help="并发测试线程数")
    args = parser.parse_args()
    
    # 安装必要的Python库
    try:
        import bs4
    except ImportError:
        print("检测到缺少 beautifulsoup4 库，正在尝试自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"])
        print("安装完成，请重新运行脚本。")
        sys.exit(0)

    checker = NodeHealthChecker(args)
    checker.run()

if __name__ == "__main__":
    main()