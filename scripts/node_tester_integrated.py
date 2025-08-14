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
def test_node_pipeline(proxy_name: str, worker_info: dict, args: argparse.Namespace) -> tuple[str, bool]:
    """
    在一个复用的、独立的 Clash 进程上，通过 API 切换到指定节点，并执行两阶段测试。
    """
    api_url = worker_info['api_url']
    proxy_url = worker_info['proxy_url']
    logging.debug(f"节点 {proxy_name}: 使用工人 {api_url} 开始测试")

    # 1. 通过 API 切换全局代理到当前节点
    try:
        switch_payload = {'name': proxy_name}
        switch_url = f"{api_url}/proxies/GLOBAL"
        response = requests.put(switch_url, json=switch_payload, timeout=3)
        if response.status_code != 204:
            logging.warning(f"节点 {proxy_name}: ❌ API 切换失败 (工人: {api_url}, 状态码: {response.status_code}) - {response.text}")
            return proxy_name, False
    except requests.exceptions.RequestException as e:
        logging.error(f"节点 {proxy_name}: ❌ API 切换失败 (工人: {api_url}, 请求异常: {e})")
        return proxy_name, False

    time.sleep(0.1)

    # --- 阶段一：延迟测试 ---
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        response = requests.get(args.latency_test_url, proxies=proxies, timeout=args.latency_timeout)
        latency = response.elapsed.total_seconds() * 1000
        if response.status_code == 204 and latency < args.delay_limit:
            logging.info(f"节点 {proxy_name}: ✅ 延迟测试通过 ({latency:.0f}ms)")
        else:
            logging.warning(f"节点 {proxy_name}: ❌ 延迟测试失败 (URL: {args.latency_test_url}, 状态码: {response.status_code}, 延迟: {latency:.0f}ms)")
            return proxy_name, False
    except requests.exceptions.RequestException as e:
        logging.warning(f"节点 {proxy_name}: ❌ 延迟测试失败 (URL: {args.latency_test_url}, 请求异常: {e})")
        return proxy_name, False

    # --- 阶段二：TLS 握手测试 ---
    try:
        proxy_host_port = proxy_url.replace("http://", "")
        cmd_openssl = [
            "openssl", "s_client",
            "-connect", f"{args.handshake_host}:{args.handshake_port}",
            "-servername", args.handshake_host,
            "-proxy", proxy_host_port
        ]
        result = subprocess.run(cmd_openssl, capture_output=True, text=True, timeout=args.handshake_timeout, check=False, encoding='utf-8', errors='ignore')
        
        if result.returncode == 0 and "Verify return code: 0 (ok)" in result.stdout:
            logging.info(f"节点 {proxy_name}: ✅ TLS握手测试通过")
            return proxy_name, True
        else:
            logging.warning(f"节点 {proxy_name}: ❌ TLS握手测试失败")
            logging.debug(f"节点 {proxy_name} OpenSSL 失败详情 - 返回码: {result.returncode}")
            logging.debug(f"节点 {proxy_name} OpenSSL 失败详情 - STDOUT:\n{result.stdout}")
            logging.debug(f"节点 {proxy_name} OpenSSL 失败详情 - STDERR:\n{result.stderr}")
            return proxy_name, False

    except Exception as e:
        logging.error(f"测试节点 {proxy_name} 时发生未知错误: {e}")
        return proxy_name, False

def worker(proxy_name: str, worker_queue: Queue, args: argparse.Namespace) -> tuple[str, bool]:
    """
    工作线程的包装器，负责从队列获取一个 Clash 进程工人并执行测试。
    """
    worker_info = None
    try:
        worker_info = worker_queue.get()
        return test_node_pipeline(proxy_name, worker_info, args)
    finally:
        if worker_info:
            worker_queue.put(worker_info)

# --- 主函数 ---
def main():
    # --- 参数解析 ---
    parser = argparse.ArgumentParser(description="对 Clash/Mihomo 节点进行两阶段健康度测试。")
    parser.add_argument('--input-file', type=str, default=os.environ.get("ALL_PROXIES_FILE", "all_proxies.yaml"), help='包含所有节点的输入 YAML 文件路径')
    parser.add_argument('--output-file', type=str, default=os.environ.get("HEALTHY_PROXIES_FILE", "healthy_proxies.yaml"), help='用于保存健康节点的输出 YAML 文件路径')
    parser.add_argument('--clash-path', type=str, default=os.environ.get("MIHOMO_PATH", "./mihomo"), help='mihomo (Clash核心) 可执行文件的路径')
    parser.add_argument('--max-workers', type=int, default=int(os.environ.get("MAX_WORKERS", 50)), help='并发测试的最大进程数 (推荐 50-100)')
    parser.add_argument('--delay-limit', type=int, default=int(os.environ.get("DELAY_LIMIT", 5000)), help='延迟测试的上限 (毫秒)')
    parser.add_argument('--latency-test-url', type=str, default=os.environ.get("LATENCY_TEST_URL", "http://www.gstatic.com/generate_204"), help='延迟测试的目标 URL')
    parser.add_argument('--latency-timeout', type=int, default=5, help='延迟测试的单次请求超时时间 (秒)')
    parser.add_argument('--handshake-host', type=str, default=os.environ.get("HANDSHAKE_TEST_HOST", "cloudcode-pa.googleapis.com"), help='TLS 握手测试的目标主机')
    parser.add_argument('--handshake-port', type=int, default=443, help='TLS 握手测试的目标端口')
    parser.add_argument('--handshake-timeout', type=int, default=8, help='TLS 握手测试的超时时间 (秒)')
    parser.add_argument('--base-port', type=int, default=int(os.environ.get("BASE_HTTP_PORT", 9100)), help='用于并行测试的起始端口号')
    args = parser.parse_args()

    logging.info(f"开始执行两阶段并行测试 (多进程复用模型)... 输入: {args.input_file}, 输出: {args.output_file}")
    logging.info(f"将启动 {args.max_workers} 个常驻 mihomo 工作进程进行测试。")

    # --- 准备工作 ---
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

    # --- 启动常驻的 mihomo 进程池 ---
    worker_processes = []
    worker_queue = Queue()
    temp_base_dir = f"./temp_test_data_{int(time.time())}"
    os.makedirs(temp_base_dir, exist_ok=True)

    try:
        for i in range(args.max_workers):
            http_port = args.base_port + i * 2
            api_port = args.base_port + i * 2 + 1
            
            worker_info = {
                'proxy_url': f'http://127.0.0.1:{http_port}',
                'api_url': f'http://127.0.0.1:{api_port}'
            }

            temp_config_path = os.path.join(temp_base_dir, f"config_worker_{i}.yaml")
            temp_mihomo_data_dir = os.path.join(temp_base_dir, f"data_worker_{i}")
            os.makedirs(temp_mihomo_data_dir, exist_ok=True)

            base_config = {
                'mixed-port': http_port,
                'allow-lan': False, 'mode': 'rule', 'log-level': 'silent',
                'external-controller': f'127.0.0.1:{api_port}',
                'dns': {'enable': True, 'listen': '0.0.0.0:53', 'nameserver': ['8.8.8.8', '1.1.1.1'], 'fallback': []},
                'proxies': all_proxies_data['proxies'],
                'proxy-groups': [{'name': 'GLOBAL', 'type': 'select', 'proxies': [p['name'] for p in all_proxies_data['proxies']] if all_proxies_data.get('proxies') else []}],
                'rules': ['MATCH,GLOBAL']
            }
            with open(temp_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(base_config, f, allow_unicode=True)

            cmd_mihomo = [args.clash_path, "-f", temp_config_path, "-d", temp_mihomo_data_dir]
            process = subprocess.Popen(cmd_mihomo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            worker_processes.append(process)
            worker_queue.put(worker_info)

        logging.info(f"已成功启动 {len(worker_processes)} 个 mihomo 工作进程。等待 3 秒以确保服务就绪...")
        time.sleep(3)

        # --- 执行并行测试 ---
        healthy_proxies = []
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [executor.submit(worker, name, worker_queue, args) for name in proxy_names]
            for future in as_completed(futures):
                try:
                    p_name, is_healthy = future.result()
                    if is_healthy:
                        healthy_proxies.append({"name": p_name})
                except Exception as e:
                    logging.error(f"一个测试任务在主线程中出现异常: {e}")

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
        # --- 确保清理所有常驻进程和临时文件 ---
        logging.info("开始清理和关闭所有 mihomo 工作进程...")
        for p in worker_processes:
            p.terminate()
            p.wait()
        logging.info(f"{len(worker_processes)} 个工作进程已关闭。")
        if os.path.exists(temp_base_dir):
            shutil.rmtree(temp_base_dir)
            logging.info(f"已清理临时目录: {temp_base_dir}")

if __name__ == "__main__":
    main()
