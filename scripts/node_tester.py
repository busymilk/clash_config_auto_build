import argparse
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml

# --- 全局配置 ---
DEFAULT_TEST_URL = "https://www.google.com/generate_204" # 默认延迟测试URL
DEFAULT_DELAY_LIMIT = 4000  # 默认延迟上限 (ms)
DEFAULT_TIMEOUT = 6000      # 默认API超时 (ms)
DEFAULT_MAX_WORKERS = 100    # 默认并发线程数

# --- 日志记录 ---
def log_info(message):
    print(f"[INFO] {message}")

def log_error(message):
    print(f"[ERROR] {message}")

# --- 核心功能函数 ---
def prepare_test_config(source_path, dest_path, template_path="config-template.yaml"):
    """读取源配置文件，注入测试所需的核心配置，并合并模板中的DNS配置。"""
    log_info(f"Preparing test config from {source_path} using template {template_path}...")
    try:
        # Load the base template config
        with open(template_path, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)

        # Load the proxies from the source_path
        with open(source_path, 'r', encoding='utf-8') as f:
            proxies_data = yaml.safe_load(f)

        if not proxies_data or 'proxies' not in proxies_data or not proxies_data['proxies']:
            log_error(f"Source file {source_path} has no proxies.")
            return []

        # Create the test config by merging base_config and proxies_data
        # Start with a deep copy of the base config to avoid modifying the original template
        config = yaml.safe_load(yaml.safe_dump(base_config))

        # Add/overwrite essential test settings
        config.update({
            'external-controller': '127.0.0.1:9090',
            'log-level': 'info',
            'mixed-port': 7890, # 必须开启mixed-port才能通过socks5选择出口节点
            'mode': 'Rule',
        })

        # Ensure rules section exists
        if 'rules' not in config:
            config['rules'] = []

        # Add the proxies to the test config
        config['proxies'] = proxies_data['proxies']

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
        # 尝试读取mihomo的输出，以便诊断启动问题
        stdout, stderr = process.communicate(timeout=1) # 使用communicate来获取输出，但设置短超时以避免阻塞
        if stdout:
            log_info(f"mihomo stdout: {stdout.strip()}")
        if stderr:
            log_error(f"mihomo stderr: {stderr.strip()}")

        if process.poll() is not None: # 检查进程是否已经退出
            log_error(f"mihomo process exited prematurely with code {process.returncode}.")
            return None

        log_info("mihomo process started.")
        return process
    except subprocess.TimeoutExpired:
        log_info("mihomo process started and is running in background (timeout on communicate)...")
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
    if not proxy_name:
        log_error("Proxy name is missing.")
        return None
    try:
        quoted_proxy_name = urllib.parse.quote(proxy_name)
        url = f"http://{api_url}/proxies/{quoted_proxy_name}/delay?timeout={timeout}&url={urllib.parse.quote(test_url)}"
        response = requests.get(url, timeout=(timeout / 1000) + 5)
        response.raise_for_status() # This will raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        delay = data.get("delay", -1)
        if 0 < delay <= delay_limit:
            log_info(f"Proxy '{proxy_name}' PASSED delay test with {delay}ms.")
            return proxy
        else:
            log_error(f"Proxy '{proxy_name}' FAILED delay test: Delay {delay}ms not within 0-{delay_limit}ms.")
            return None
    except requests.exceptions.RequestException as e:
        log_error(f"Proxy '{proxy_name}' FAILED delay test (RequestException): {e}")
        return None
    except ValueError as e: # Catches JSON decoding errors
        log_error(f"Proxy '{proxy_name}' FAILED delay test (JSON Decode Error): {e}. Response content: {response.text[:200]}...")
        return None
    except Exception as e:
        log_error(f"Proxy '{proxy_name}' FAILED delay test (Other Exception): {e}")
        return None

def main(args):
    test_config_path = "config_for_test.yaml"
    proxies_to_test = prepare_test_config(args.input_file, test_config_path)
    if not proxies_to_test:
        return

    mihomo_process = start_mihomo(args.clash_path, test_config_path)
    if not mihomo_process:
        return

    healthy_proxies = []

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
    parser.add_argument("--test-url", default=DEFAULT_TEST_URL, help="URL for testing proxy delay.")
    parser.add_argument("--delay-limit", type=int, default=DEFAULT_DELAY_LIMIT, help="Maximum acceptable delay in ms.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout for delay test in ms.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Number of concurrent workers for testing.")

    args = parser.parse_args()
    main(args)
