import argparse
import re
import subprocess
import time
import urllib.parse
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml
import geoip2.database

# --- 全局配置 ---
DEFAULT_TEST_URL = "https://www.google.com/generate_204" # 默认延迟测试URL
DEFAULT_DELAY_LIMIT = 3000  # 默认延迟上限 (ms)
DEFAULT_TIMEOUT = 5000      # 默认API超时 (ms)
DEFAULT_MAX_WORKERS = 80    # 默认并发线程数
IP_ECHO_PORT = 8080         # 本地IP回显服务器端口

# --- 日志记录 (简化版) ---
def log_info(message):
    print(f"[INFO] {message}")

def log_error(message):
    print(f"[ERROR] {message}")

# --- 本地IP回显服务器 ---
class IPEchoHandler(BaseHTTPRequestHandler):
    """一个简单的HTTP请求处理器，它会将来访者的IP地址作为响应返回。"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(self.client_address[0].encode('utf-8'))
    def log_message(self, format, *args):
        # 重写此方法以禁止在控制台打印每个HTTP请求的日志
        return

def run_ip_echo_server(port=IP_ECHO_PORT):
    """在一个独立的守护线程中运行IP回显服务器。"""
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, IPEchoHandler)
    log_info(f"Starting local IP echo server on port {port}...")
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()
    return httpd

# --- 核心功能函数 ---

def prepare_test_config(source_path, dest_path):
    """读取源配置文件，注入测试所需的核心配置，并增加IP回显服务器的直连规则。"""
    log_info(f"Preparing test config from {source_path}...")
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if 'proxies' not in config or not config['proxies']:
            log_error(f"Source file {source_path} has no proxies.")
            return []

        config.update({
            'external-controller': '127.0.0.1:9090',
            'log-level': 'info',
            'mixed-port': 7890, # 必须开启mixed-port才能通过socks5选择出口节点
            'mode': 'Rule',
        })

        if 'rules' not in config:
            config['rules'] = []
        # 插入规则，确保对本地回显服务器的请求不会被代理
        config['rules'].insert(0, f'IP-CIDR,127.0.0.1/32,DIRECT')

        with open(dest_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)

        log_info(f'Test config prepared and saved to {dest_path}')
        return config.get("proxies", [])
    except Exception as e:
        log_error(f'Failed to prepare test config: {e}')
        return []

def start_mihomo(mihomo_path, config_path):
    """启动 mihomo 核心进程。"""
    log_info(f"Starting mihomo with config: {config_path}...")
    try:
        process = subprocess.Popen(
            [mihomo_path, "-f", config_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8'
        )
        time.sleep(5)
        log_info("mihomo process started.")
        return process
    except Exception as e:
        log_error(f"Failed to start mihomo: {e}")
        return None

def stop_mihomo(process):
    """停止 mihomo 核心进程。"""
    if process:
        log_info("Stopping mihomo process...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        log_info("mihomo process stopped.")

def check_proxy_delay(proxy, api_url, timeout, delay_limit, test_url):
    """通过 mihomo API 测试单个代理的延迟。"""
    proxy_name = proxy.get("name")
    if not proxy_name: return None
    try:
        quoted_proxy_name = urllib.parse.quote(proxy_name)
        url = f"http://{api_url}/proxies/{quoted_proxy_name}/delay?timeout={timeout}&url={urllib.parse.quote(test_url)}"
        response = requests.get(url, timeout=(timeout / 1000) + 5)
        response.raise_for_status()
        data = response.json()
        delay = data.get("delay", -1)
        if 0 < delay <= delay_limit:
            log_info(f"Proxy \'{proxy_name}\' PASSED delay test with {delay}ms.")
            return proxy
    except Exception:
        pass
    return None

def get_exit_ip_via_proxy(proxy, echo_port):
    """通过指定代理的SOCKS5出口，访问本地回显服务器以获取真实出口IP。"""
    proxy_name_encoded = urllib.parse.quote(proxy['name'])
    # 通过mihomo的mixed-port的SOCKS5协议，并用查询参数指定出口节点
    proxy_url = f'socks5://127.0.0.1:7890?proxy={proxy_name_encoded}'
    try:
        response = requests.get(f'http://127.0.0.1:{echo_port}', proxies={'http': proxy_url, 'https': proxy_url}, timeout=20)
        response.raise_for_status()
        # 附加出口IP到proxy字典中，方便后续处理
        proxy['exit_ip'] = response.text.strip()
        return proxy
    except Exception:
        return None # 查询失败的节点将被丢弃

def calibrate_and_rename_proxies(proxies_with_ip, geoip_dat_path):
    """使用GeoIP数据库校准节点归属地，并根据结果重命名节点。"""
    log_info("Calibrating country codes for proxies with resolved IP...")
    reader = None
    try:
        # 使用 with geoip2.database.Reader 打开数据库文件
        reader = geoip2.database.Reader(geoip_dat_path)
    except Exception as e:
        log_error(f"Failed to load GeoIP database from {geoip_dat_path}: {e}")
        # 如果数据库加载失败，则直接返回未重命名的节点
        return proxies_with_ip

    # 清理旧的地区标识，例如 [US], (HK), |SG| 等
    def clean_name(name):
        return re.sub(r'[\(\[【].*?[\)\]】]', '', name).strip()

    final_proxies = []
    for proxy in proxies_with_ip:
        exit_ip = proxy.get('exit_ip')
        original_name = proxy.get('name', '')
        
        if not exit_ip:
            continue

        try:
            # 使用 geoip2 进行查询
            response = reader.country(exit_ip)
            country_code = response.country.iso_code
        except geoip2.errors.AddressNotFoundError:
            # 如果是私有地址或数据库中不存在的地址，则无法找到国家
            country_code = None
        except Exception:
            # 其他查询错误
            country_code = None

        if country_code:
            proxy['name'] = f"[{country_code}] {clean_name(original_name)}"
        else:
            proxy['name'] = clean_name(original_name)
        final_proxies.append(proxy)
    
    if reader:
        reader.close()
            
    log_info("Finished calibrating and renaming proxies.")
    return final_proxies

def main(args):
    """主执行函数。"""
    ip_echo_server = run_ip_echo_server()

    test_config_path = "config_for_test.yaml"
    proxies_to_test = prepare_test_config(args.input_file, test_config_path)
    if not proxies_to_test:
        ip_echo_server.shutdown()
        return

    mihomo_process = start_mihomo(args.clash_path, test_config_path)
    if not mihomo_process:
        ip_echo_server.shutdown()
        return

    healthy_proxies = []
    proxies_with_ip = []

    try:
        # --- 步骤 4: 并发测试所有节点的延迟 ---
        log_info(f"Testing delay for {len(proxies_to_test)} proxies...")
        api_url = "127.0.0.1:9090"
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_proxy = {executor.submit(check_proxy_delay, p, api_url, args.timeout, args.delay_limit, args.test_url): p for p in proxies_to_test}
            for future in as_completed(future_to_proxy):
                result = future.result()
                if result:
                    healthy_proxies.append(result)
        log_info(f"Found {len(healthy_proxies)} healthy proxies after delay test.")

        # --- 步骤 5: 为通过延迟测试的节点并发获取出口IP ---
        if healthy_proxies:
            log_info(f"Fetching exit IP for {len(healthy_proxies)} healthy proxies...")
            with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                future_to_ip = {executor.submit(get_exit_ip_via_proxy, p, IP_ECHO_PORT): p for p in healthy_proxies}
                for future in as_completed(future_to_ip):
                    result = future.result()
                    if result:
                        proxies_with_ip.append(result)
            log_info(f"Successfully fetched IP for {len(proxies_with_ip)} proxies.")

    finally:
        # --- 步骤 6: 所有操作完成，停止mihomo和IP回显服务器 ---
        stop_mihomo(mihomo_process)
        ip_echo_server.shutdown()
        log_info("Cleaned up all background processes.")

    # --- 步骤 7: 校准国家并重命名 ---
    final_proxies = calibrate_and_rename_proxies(proxies_with_ip, args.geoip_dat_path)

    # --- 步骤 8: 保存最终的纯净节点列表 ---
    with open(args.output_file, 'w', encoding='utf-8') as f:
        yaml.dump({'proxies': final_proxies}, f, allow_unicode=True)
    log_info(f"Final healthy proxy list saved to {args.output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clash/mihomo Proxy Tester, Calibrator, and Filter.")
    parser.add_argument("-i", "--input-file", required=True, help="Path to the input clash config file.")
    parser.add_argument("-o", "--output-file", required=True, help="Path to save the final list of healthy proxies.")
    parser.add_argument("-p", "--clash-path", required=True, help="Path to the mihomo executable file.")
    parser.add_argument("-g", "--geoip-dat-path", required=True, help="Path to the geoip.dat file.")
    parser.add_argument("--test-url", default=DEFAULT_TEST_URL, help="URL for testing proxy delay.")
    parser.add_argument("--delay-limit", type=int, default=DEFAULT_DELAY_LIMIT, help="Maximum acceptable delay in ms.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout for delay test in ms.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Number of concurrent workers for testing.")

    args = parser.parse_args()
    main(args)
