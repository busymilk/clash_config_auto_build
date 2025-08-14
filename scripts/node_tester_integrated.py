import yaml
import requests
import os
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import shutil

# --- 全局配置 ---
# 日志配置
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')

# 从环境变量获取配置，提供默认值
HEALTHY_PROXIES_FILE = os.environ.get("HEALTHY_PROXIES_FILE", "healthy_proxies.yaml")
ALL_PROXIES_FILE = os.environ.get("ALL_PROXIES_FILE", "all_proxies.yaml")
MIHOMO_PATH = os.environ.get("MIHOMO_PATH", "./mihomo")
BASE_CONFIG_PATH = os.environ.get("BASE_CONFIG_PATH", "config-template.yaml")

# 并发测试相关配置
MAX_CONCURRENT_PROCESSES = int(os.environ.get("MAX_WORKERS", 100))
BASE_HTTP_PORT = int(os.environ.get("BASE_HTTP_PORT", 9100))

# 阶段一：延迟测试配置
LATENCY_TEST_URL = os.environ.get("LATENCY_TEST_URL", "https://cp.cloudflare.com/generate_204")
DELAY_LIMIT = int(os.environ.get("DELAY_LIMIT", 5000))
LATENCY_TIMEOUT_SECONDS = int(os.environ.get("LATENCY_TIMEOUT", 5))

# 阶段二：握手测试配置
HANDSHAKE_TEST_HOST = os.environ.get("HANDSHAKE_TEST_HOST", "cloudcode-pa.googleapis.com")
HANDSHAKE_TEST_PORT = int(os.environ.get("HANDSHAKE_TEST_PORT", 443))
HANDSHAKE_TIMEOUT_SECONDS = int(os.environ.get("HANDSHAKE_TIMEOUT", 6))


# --- 核心测试逻辑 ---

def run_node_test_pipeline(proxy_name: str, port: int, temp_dir: str) -> tuple[str, bool]:
    """
    为单个节点启动独立的 mihomo 进程，并执行两阶段测试：
    1. 延迟测试 (快速筛选)
    2. TLS 握手测试 (严格筛选)
    """
    temp_config_path = os.path.join(temp_dir, f"config_{port}.yaml")
    temp_mihomo_data_dir = os.path.join(temp_dir, f"data_{port}")
    os.makedirs(temp_mihomo_data_dir, exist_ok=True)

    # 1. 为该节点动态生成配置文件
    try:
        with open(BASE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)
        with open(ALL_PROXIES_FILE, 'r', encoding='utf-8') as f:
            proxies_config = yaml.safe_load(f)

        base_config['proxies'] = proxies_config['proxies']
        
        # 强制所有流量走当前测试节点
        proxy_group_name = f"test_group_{port}"
        base_config['proxy-groups'].insert(0, {
            'name': proxy_group_name,
            'type': 'select',
            'proxies': [proxy_name]
        })
        base_config['rules'] = [f'MATCH,{proxy_group_name}']

        base_config['mixed-port'] = port
        if 'external-controller' in base_config:
            del base_config['external-controller']

        with open(temp_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f, allow_unicode=True)

    except Exception as e:
        logging.error(f"节点 {proxy_name}: 生成配置文件失败: {e}")
        return proxy_name, False

    # 2. 启动独立的 mihomo 进程
    mihomo_process = None
    try:
        cmd_mihomo = [MIHOMO_PATH, "-f", temp_config_path, "-d", temp_mihomo_data_dir]
        mihomo_process = subprocess.Popen(cmd_mihomo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) # 等待 mihomo 启动

        proxy_address = f"http://127.0.0.1:{port}"
        proxies = {"http": proxy_address, "https": proxy_address}

        # --- 阶段一：延迟测试 ---
        try:
            response = requests.get(LATENCY_TEST_URL, proxies=proxies, timeout=LATENCY_TIMEOUT_SECONDS)
            if response.status_code == 204 and response.elapsed.total_seconds() * 1000 < DELAY_LIMIT:
                logging.info(f"节点 {proxy_name}: ✅ 延迟测试通过 ({response.elapsed.total_seconds() * 1000:.0f}ms)")
            else:
                logging.warning(f"节点 {proxy_name}: ❌ 延迟测试失败 (状态码: {response.status_code}, 延迟: {response.elapsed.total_seconds() * 1000:.0f}ms)")
                return proxy_name, False
        except requests.exceptions.RequestException as e:
            logging.warning(f"节点 {proxy_name}: ❌ 延迟测试失败 (请求异常: {e})")
            return proxy_name, False

        # --- 阶段二：TLS 握手测试 ---
        cmd_openssl = [
            "openssl", "s_client",
            "-connect", f"{HANDSHAKE_TEST_HOST}:{HANDSHAKE_TEST_PORT}",
            "-servername", HANDSHAKE_TEST_HOST,
            "-proxy", f"127.0.0.1:{port}"
        ]
        result = subprocess.run(cmd_openssl, capture_output=True, text=True, timeout=HANDSHAKE_TIMEOUT_SECONDS, check=False)
        
        if result.returncode == 0 and "Protocol" in result.stdout and "Verify return code: 0 (ok)" in result.stdout:
            logging.info(f"节点 {proxy_name}: ✅ TLS握手测试通过")
            return proxy_name, True
        else:
            logging.warning(f"节点 {proxy_name}: ❌ TLS握手测试失败")
            return proxy_name, False

    except Exception as e:
        logging.error(f"测试节点 {proxy_name} 时发生未知错误: {e}")
        return proxy_name, False
    finally:
        if mihomo_process:
            mihomo_process.terminate()
            mihomo_process.wait()

# --- 主函数 ---
def main():
    logging.info("开始执行两阶段节点健康度测试...")

    try:
        with open(ALL_PROXIES_FILE, 'r', encoding='utf-8') as f:
            all_proxies_data = yaml.safe_load(f)
        proxy_names = [p['name'] for p in all_proxies_data['proxies']]
        logging.info(f"共找到 {len(proxy_names)} 个待测试节点")
    except Exception as e:
        logging.fatal(f"读取节点文件 {ALL_PROXIES_FILE} 失败: {e}")
        return

    port_queue = Queue()
    for i in range(MAX_CONCURRENT_PROCESSES):
        port_queue.put(BASE_HTTP_PORT + i)

    healthy_proxies = []
    temp_base_dir = f"./temp_test_data_{int(time.time())}"
    os.makedirs(temp_base_dir, exist_ok=True)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PROCESSES) as executor:
        futures = {}
        for proxy_name in proxy_names:
            try:
                port = port_queue.get_nowait()
                future = executor.submit(run_node_test_pipeline, proxy_name, port, temp_base_dir)
                futures[future] = (proxy_name, port)
            except Exception as e:
                logging.error(f"为 {proxy_name} 提交任务失败: {e}")

        for future in as_completed(futures):
            p_name, p_port = futures[future]
            try:
                _, is_healthy = future.result()
                if is_healthy:
                    healthy_proxies.append({"name": p_name})
            except Exception as e:
                logging.error(f"节点 {p_name} 的测试任务执行时出现异常: {e}")
            finally:
                port_queue.put(p_port)

    if os.path.exists(temp_base_dir):
        shutil.rmtree(temp_base_dir)
        logging.info(f"已清理临时目录: {temp_base_dir}")

    if healthy_proxies:
        original_proxies_map = {p['name']: p for p in all_proxies_data['proxies']}
        final_healthy_proxies_data = [original_proxies_map[p['name']] for p in healthy_proxies if p['name'] in original_proxies_map]
        
        output_data = {'proxies': final_healthy_proxies_data}
        with open(HEALTHY_PROXIES_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, allow_unicode=True)
        logging.info(f"测试完成！共找到 {len(final_healthy_proxies_data)} 个通过两阶段测试的健康节点，已写入 {HEALTHY_PROXIES_FILE}")
    else:
        logging.warning("测试完成，没有找到任何健康节点。")

if __name__ == "__main__":
    main()
