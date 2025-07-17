import argparse
import re
import subprocess
import time
import urllib.parse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml
import geoip2.database

# --- 全局配置 ---
DEFAULT_TEST_URL = "https://www.google.com/generate_204" # 默认延迟测试URL
DEFAULT_DELAY_LIMIT = 3000  # 默认延迟上限 (ms)
DEFAULT_TIMEOUT = 5000      # 默认API超时 (ms)
DEFAULT_MAX_WORKERS = 80    # 默认并发线程数

# --- 日志记录 ---
def log_info(message):
    print(f"[INFO] {message}")

def log_error(message):
    print(f"[ERROR] {message}")

# --- 核心功能函数 ---
def prepare_test_config(source_path, dest_path):
    """读取源配置文件，注入测试所需的核心配置。"""
    log_info(f"Preparing test config from {source_path}...")
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not config or 'proxies' not in config or not config['proxies']:
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
            log_info(f"Proxy '{proxy_name}' PASSED delay test with {delay}ms.")
            return proxy
    except Exception:
        pass
    return None

def get_exit_ip_via_proxy(proxy, retries=3, initial_timeout=10):
    """通过指定代理访问 https://api64.ipify.org 以获取真实出口IP，并支持重试。"""
    proxy_name = proxy.get("name")
    if not proxy_name:
        return None

    # 假设 mihomo/clash 内核支持通过 SOCKS5 的用户名来选择出站代理，这并非标准行为，但在此遵循原作者的实现逻辑
    proxy_url = f'socks5h://{urllib.parse.quote(proxy_name)}@127.0.0.1:7890'
    target_url = 'https://api64.ipify.org'

    for attempt in range(retries):
        try:
            timeout = initial_timeout * (1.5 ** attempt)  # 指数退避
            response = requests.get(
                target_url,
                proxies={'https': proxy_url, 'http': proxy_url},
                timeout=timeout
            )
            response.raise_for_status()
            ip_address = response.text.strip()
            
            # 验证返回的是一个有效的IPv4或IPv6地址
            if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip_address) or re.match(r'^[a-f0-9:]+$', ip_address, re.IGNORECASE):
                proxy['exit_ip'] = ip_address
                log_info(f"Proxy '{proxy_name}' exit IP: {proxy['exit_ip']} (Attempt {attempt + 1})")
                return proxy
            else:
                log_error(f"Proxy '{proxy_name}' received invalid IP response: '{ip_address}' (Attempt {attempt + 1})")
        except requests.exceptions.RequestException as e:
            log_error(f"Proxy '{proxy_name}' failed to get exit IP (RequestException, Attempt {attempt + 1}/{retries}): {e}")
        except Exception as e:
            log_error(f"Proxy '{proxy_name}' failed to get exit IP (Other Exception, Attempt {attempt + 1}/{retries}): {e}")
        time.sleep(1)  # 每次重试前等待1秒
    return None

def calibrate_and_rename_proxies(proxies_with_ip, geoip_db_path):
    """使用GeoIP数据库校准节点归属地，并根据结果重命名节点。"""
    log_info("Calibrating country codes...")
    reader = None
    try:
        reader = geoip2.database.Reader(geoip_db_path)
    except Exception as e:
        log_error(f"Failed to load GeoIP database: {e}")
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
            response = reader.country(exit_ip)
            country_code = response.country.iso_code
        except geoip2.errors.AddressNotFoundError:
            country_code = None
        except Exception:
            country_code = None

        if country_code and country_code != 'ZZ':
            proxy['name'] = f"[{country_code}] {clean_name(original_name)}"
        else:
            proxy['name'] = clean_name(original_name)
        final_proxies.append(proxy)
    
    if reader:
        reader.close()
    log_info("Finished calibrating and renaming proxies.")
    return final_proxies

def main(args):
    test_config_path = "config_for_test.yaml"
    proxies_to_test = prepare_test_config(args.input_file, test_config_path)
    if not proxies_to_test:
        return

    mihomo_process = start_mihomo(args.clash_path, test_config_path)
    if not mihomo_process:
        return

    healthy_proxies = []
    proxies_with_ip = []

    try:
        log_info(f"Testing delay for {len(proxies_to_test)} proxies...")
        api_url = "127.0.0.1:9090"
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_proxy = {executor.submit(check_proxy_delay, p, api_url, args.timeout, args.delay_limit, args.test_url): p for p in proxies_to_test}
            for future in as_completed(future_to_proxy):
                result = future.result()
                if result:
                    healthy_proxies.append(result)
        log_info(f"Found {len(healthy_proxies)} healthy proxies after delay test.")

        if healthy_proxies:
            log_info(f"Fetching exit IP for {len(healthy_proxies)} healthy proxies...")
            with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                future_to_ip = {executor.submit(get_exit_ip_via_proxy, p): p for p in healthy_proxies}
                for future in as_completed(future_to_ip):
                    result = future.result()
                    if result:
                        proxies_with_ip.append(result)
            log_info(f"Successfully fetched IP for {len(proxies_with_ip)} proxies.")
            final_proxies_to_save = calibrate_and_rename_proxies(proxies_with_ip, args.geoip_dat_path)
        else:
            final_proxies_to_save = healthy_proxies

    finally:
        stop_mihomo(mihomo_process)
        log_info("Cleaned up mihomo process.")

    with open(args.output_file, 'w', encoding='utf-8') as f:
        yaml.dump({'proxies': final_proxies_to_save}, f, allow_unicode=True)
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