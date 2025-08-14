import yaml
import requests
import os
import logging
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import shutil

# --- 日志配置 ---
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

# --- 核心测试逻辑 ---
def run_node_test_pipeline(proxy_name: str, port: int, temp_dir: str, args: argparse.Namespace) -> tuple[str, bool]:
    """
    为单个节点启动独立的 mihomo 进程，并执行两阶段测试。
    """
    temp_config_path = os.path.join(temp_dir, f"config_{port}.yaml")
    temp_mihomo_data_dir = os.path.join(temp_dir, f"data_{port}")
    os.makedirs(temp_mihomo_data_dir, exist_ok=True)

    # 1. 为该节点动态生成配置文件
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            proxies_config = yaml.safe_load(f)
        
        # 创建一个极简的、干净的配置
        http_port = port
        base_config = {
            'mixed-port': http_port,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'silent',
            'dns': {
                'enable': True,
                'listen': '0.0.0.0:53',
                'nameserver': ['8.8.8.8', '1.1.1.1'],
                'fallback': [],
            },
            'proxies': proxies_config['proxies'],
            'proxy-groups': [{'name': 'GLOBAL', 'type': 'select', 'proxies': [proxy_name]}],
            'rules': ['MATCH,GLOBAL']
        }

        with open(temp_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f, allow_unicode=True)

    except Exception as e:
        logging.error(f"节点 {proxy_name}: 生成配置文件失败: {e}")
        return proxy_name, False

    # 2. 启动独立的 mihomo 进程
    mihomo_process = None
    try:
        cmd_mihomo = [args.clash_path, "-f", temp_config_path, "-d", temp_mihomo_data_dir]
        mihomo_process = subprocess.Popen(cmd_mihomo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) # 等待 mihomo 启动

        proxy_address = f"http://127.0.0.1:{port}"
        proxies = {"http": proxy_address, "https": proxy_address}

        # --- 阶段一：延迟测试 ---
        try:
            response = requests.get(args.latency_test_url, proxies=proxies, timeout=args.latency_timeout)
            latency = response.elapsed.total_seconds() * 1000
            if response.status_code == 204 and latency < args.delay_limit:
                logging.info(f"节点 {proxy_name} (端口 {port}): ✅ 延迟测试通过 ({latency:.0f}ms)")
            else:
                logging.warning(f"节点 {proxy_name} (端口 {port}): ❌ 延迟测试失败 (URL: {args.latency_test_url}, 状态码: {response.status_code}, 延迟: {latency:.0f}ms)")
                return proxy_name, False
        except requests.exceptions.RequestException as e:
            logging.warning(f"节点 {proxy_name} (端口 {port}): ❌ 延迟测试失败 (URL: {args.latency_test_url}, 请求异常: {e})")
            return proxy_name, False

        # --- 阶段二：TLS 握手测试 ---
        cmd_openssl = [
            "openssl", "s_client",
            "-connect", f"{args.handshake_host}:{args.handshake_port}",
            "-servername", args.handshake_host,
            "-proxy", f"127.0.0.1:{port}"
        ]
        result = subprocess.run(cmd_openssl, capture_output=True, text=True, timeout=args.handshake_timeout, check=False, encoding='utf-8', errors='ignore')
        
        if result.returncode == 0 and "Verify return code: 0 (ok)" in result.stdout:
            logging.info(f"节点 {proxy_name} (端口 {port}): ✅ TLS握手测试通过")
            return proxy_name, True
        else:
            logging.warning(f"节点 {proxy_name} (端口 {port}): ❌ TLS握手测试失败")
            logging.debug(f"节点 {proxy_name} OpenSSL 失败详情 - 返回码: {result.returncode}")
            logging.debug(f"节点 {proxy_name} OpenSSL 失败详情 - STDOUT:\n{result.stdout}")
            logging.debug(f"节点 {proxy_name} OpenSSL 失败详情 - STDERR:\n{result.stderr}")
            return proxy_name, False

    except Exception as e:
        logging.error(f"测试节点 {proxy_name} (端口 {port}) 时发生未知错误: {e}")
        return proxy_name, False
    finally:
        if mihomo_process:
            mihomo_process.terminate()
            mihomo_process.wait()

def worker(proxy_name: str, port_queue: Queue, temp_dir: str, args: argparse.Namespace) -> tuple[str, bool]:
    """
    工作线程的包装器，负责从队列获取端口并执行测试管道。
    """
    port = None
    try:
        port = port_queue.get()
        return run_node_test_pipeline(proxy_name, port, temp_dir, args)
    finally:
        if port:
            port_queue.put(port)

# --- 主函数 ---
def main():
    # --- 参数解析 ---
    parser = argparse.ArgumentParser(description="对 Clash/Mihomo 节点进行两阶段健康度测试。")
    parser.add_argument('--input-file', type=str, default=os.environ.get("ALL_PROXIES_FILE", "all_proxies.yaml"), help='包含所有节点的输入 YAML 文件路径')
    parser.add_argument('--output-file', type=str, default=os.environ.get("HEALTHY_PROXIES_FILE", "healthy_proxies.yaml"), help='用于保存健康节点的输出 YAML 文件路径')
    parser.add_argument('--clash-path', type=str, default=os.environ.get("MIHOMO_PATH", "./mihomo"), help='mihomo (Clash核心) 可执行文件的路径')
    parser.add_argument('--max-workers', type=int, default=int(os.environ.get("MAX_WORKERS", 100)), help='并发测试的最大进程数')
    parser.add_argument('--delay-limit', type=int, default=int(os.environ.get("DELAY_LIMIT", 5000)), help='延迟测试的上限 (毫秒)')
    parser.add_argument('--latency-test-url', type=str, default=os.environ.get("LATENCY_TEST_URL", "http://www.gstatic.com/generate_204"), help='延迟测试的目标 URL')
    parser.add_argument('--latency-timeout', type=int, default=5, help='延迟测试的单次请求超时时间 (秒)')
    parser.add_argument('--handshake-host', type=str, default=os.environ.get("HANDSHAKE_TEST_HOST", "cloudcode-pa.googleapis.com"), help='TLS 握手测试的目标主机')
    parser.add_argument('--handshake-port', type=int, default=443, help='TLS 握手测试的目标端口')
    parser.add_argument('--handshake-timeout', type=int, default=8, help='TLS 握手测试的超时时间 (秒)')
    parser.add_argument('--base-port', type=int, default=int(os.environ.get("BASE_HTTP_PORT", 9100)), help='用于并行测试的起始端口号')
    args = parser.parse_args()

    logging.info(f"开始执行两阶段并行测试 (多进程模型)... 输入: {args.input_file}, 输出: {args.output_file}")
    logging.info(f"测试将以 {args.max_workers} 个并行工作进程运行。")

    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            all_proxies_data = yaml.safe_load(f)
        proxy_names = [p['name'] for p in all_proxies_data['proxies']]
        logging.info(f"共找到 {len(proxy_names)} 个待测试节点")
    except FileNotFoundError:
        logging.fatal(f"错误: 输入文件未找到于 '{args.input_file}'。")
        return
    except Exception as e:
        logging.fatal(f"读取节点文件 {args.input_file} 失败: {e}")
        return

    port_queue = Queue()
    for i in range(args.max_workers):
        port_queue.put(args.base_port + i)

    healthy_proxies = []
    temp_base_dir = f"./temp_test_data_{int(time.time())}"
    os.makedirs(temp_base_dir, exist_ok=True)

    try:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # 为每个节点创建一个包装了端口获取逻辑的 future
            futures = [executor.submit(worker, name, port_queue, temp_base_dir, args) for name in proxy_names]

            for future in as_completed(futures):
                try:
                    p_name, is_healthy = future.result()
                    if is_healthy:
                        healthy_proxies.append({"name": p_name})
                except Exception as e:
                    logging.error(f"一个测试任务执行时出现异常: {e}")

        if healthy_proxies:
            original_proxies_map = {p['name']: p for p in all_proxies_data['proxies']}
            final_healthy_proxies_data = [original_proxies_map[p['name']] for p in healthy_proxies if p['name'] in original_proxies_map]
            
            output_data = {'proxies': final_healthy_proxies_data}
            with open(args.output_file, 'w', encoding='utf-8') as f:
                yaml.dump(output_data, f, allow_unicode=True)
            logging.info(f"测试完成！共找到 {len(final_healthy_proxies_data)} 个健康节点，已写入 {args.output_file}")
        else:
            logging.warning("测试完成，没有找到任何健康节点。")

    finally:
        if os.path.exists(temp_base_dir):
            shutil.rmtree(temp_base_dir)
            logging.info(f"已清理临时目录: {temp_base_dir}")

if __name__ == "__main__":
    main()
