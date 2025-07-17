

import argparse
import itertools
import json
import string
import subprocess
import time
import urllib
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml

# --- 全局配置 ---
# 这些值可以通过命令行参数覆盖
DEFAULT_TEST_URL = "http://www.gstatic.com/generate_204"
DEFAULT_DELAY_LIMIT = 2500  # ms
DEFAULT_TIMEOUT = 5000      # ms
DEFAULT_MAX_WORKERS = 80

# --- 日志记录 (简化版) ---
def log_info(message):
    print(f"[INFO] {message}")

def log_error(message):
    print(f"[ERROR] {message}")

# --- 核心功能函数 ---

def download_config(url, dest_path):
    """从订阅链接下载原始配置文件。"""
    log_info(f"Downloading config from {url}...")
    try:
        response = requests.get(url, verify=False, timeout=30)
        response.raise_for_status()
        with open(dest_path, 'wb') as file:
            file.write(response.content)
        log_info(f"Config downloaded to {dest_path}")
        return True
    except Exception as e:
        log_error(f"Failed to download config: {e}")
        return False

def prepare_test_config(source_path, dest_path):
    """
    读取源配置文件，注入测试所需的核心配置，并进行基础的按名去重。
    """
    log_info(f"Preparing test config from {source_path}...")
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        proxies = config.get("proxies", [])
        unique_proxies = []
        unique_names = set()

        for proxy in proxies:
            name = proxy.get("name")
            if name and name not in unique_names:
                unique_proxies.append(proxy)
                unique_names.add(name)

        config.update({
            'external-controller': '127.0.0.1:9090',
            'log-level': 'info',
            'mixed-port': 7890,
            'mode': 'Rule',
            'proxies': unique_proxies
        })

        with open(dest_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)

        log_info(f'Test config prepared and saved to {dest_path}')
        return config.get("proxies", [])
    except Exception as e:
        log_error(f'Failed to prepare test config: {e}')
        return []

def start_clash(clash_executable_path, config_path):
    """启动 Clash 核心进程。"""
    log_info(f"Starting Clash with config: {config_path}...")
    try:
        process = subprocess.Popen(
            [clash_executable_path, "-f", config_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        time.sleep(5)  # 等待 Clash 完全启动
        log_info("Clash process started.")
        return process
    except Exception as e:
        log_error(f"Failed to start Clash: {e}")
        return None

def stop_clash(process):
    """停止 Clash 核心进程。"""
    if process:
        log_info("Stopping Clash process...")
        process.terminate()
        try:
            process.wait(timeout=5)
            log_info("Clash process stopped.")
        except subprocess.TimeoutExpired:
            log_error("Clash process did not terminate in time, killing.")
            process.kill()

def check_proxy(proxy, api_url, timeout, delay_limit, test_url):
    """通过 Clash API 测试单个代理的延迟。"""
    proxy_name = proxy.get("name")
    if not proxy_name:
        return None
        
    try:
        quoted_proxy_name = urllib.parse.quote(proxy_name)
        url = f"http://{api_url}/proxies/{quoted_proxy_name}/delay?timeout={timeout}&url={urllib.parse.quote(test_url)}"
        
        response = requests.get(url, timeout=(timeout / 1000) + 2)
        response.raise_for_status()
        
        data = response.json()
        delay = data.get("delay", -1)

        if 0 < delay <= delay_limit:
            log_info(f"Proxy '{proxy_name}' PASSED with delay {delay}ms.")
            return proxy
    except requests.exceptions.RequestException:
        # 各种网络请求错误，视为节点不可用，不打印错误以保持日志整洁
        pass
    except Exception:
        # 其他意外错误，同样视为节点不可用
        pass
        
    # log_info(f"Proxy '{proxy_name}' FAILED check.")
    return None



def main(args):
    """主执行函数。"""
    
    # --- 步骤 1: 准备原始配置文件 ---
    # 如果提供了订阅URL，则下载；否则，直接使用输入文件。
    initial_config_path = "initial_config.yaml"
    if args.sub_url:
        if not download_config(args.sub_url, initial_config_path):
            return
    else:
        initial_config_path = args.input_file

    # --- 步骤 2: 准备用于测试的配置文件 ---
    test_config_path = "config_for_test.yaml"
    proxies_to_test = prepare_test_config(initial_config_path, test_config_path)
    if not proxies_to_test:
        log_error("No proxies found to test.")
        return

    # --- 步骤 3: 启动 Clash 核心 ---
    clash_process = start_clash(args.clash_path, test_config_path)
    if not clash_process:
        return

    # --- 步骤 4: 并发测试所有节点 ---
    log_info(f"Testing {len(proxies_to_test)} proxies with {args.max_workers} workers...")
    available_proxies = []
    api_url = "127.0.0.1:9090"
    
    try:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_proxy = {
                executor.submit(check_proxy, proxy, api_url, args.timeout, args.delay_limit, args.test_url): proxy
                for proxy in proxies_to_test
            }
            for future in as_completed(future_to_proxy):
                result = future.result()
                if result:
                    available_proxies.append(result)
    finally:
        # --- 步骤 5: 停止 Clash 核心 ---
        stop_clash(clash_process)

    log_info(f"Found {len(available_proxies)} available proxies.")

    # --- 步骤 6: 保存最终的纯净节点列表 ---
    with open(args.output_file, 'w', encoding='utf-8') as f:
        yaml.dump({'proxies': available_proxies}, f, allow_unicode=True)
    log_info(f"Final healthy proxy list saved to {args.output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clash Proxy Tester and Filter.")
    
    # 输入源参数 (二选一)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input-file", help="Path to the input clash config file.")
    input_group.add_argument("-s", "--sub-url", help="URL of the clash subscription.")

    # 必要参数
    parser.add_argument("-o", "--output-file", required=True, help="Path to save the final list of healthy proxies.")
    parser.add_argument("-p", "--clash-path", required=True, help="Path to the Clash executable file.")

    # 可选参数
    parser.add_argument("--test-url", default=DEFAULT_TEST_URL, help="URL for testing proxy delay.")
    parser.add_argument("--delay-limit", type=int, default=DEFAULT_DELAY_LIMIT, help="Maximum acceptable delay in ms.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout for delay test in ms.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Number of concurrent workers for testing.")

    args = parser.parse_args()
    main(args)

