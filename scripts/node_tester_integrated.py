import yaml
import requests
import os
import logging
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# --- 日志配置 ---
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')

# --- 全局锁 ---
clash_api_lock = Lock()

# --- 核心测试逻辑 ---
def test_node_pipeline(proxy_name: str, args: argparse.Namespace) -> tuple[str, bool]:
    """
    通过 Clash API 切换到指定节点，并执行两阶段测试。
    """
    with clash_api_lock:
        logging.debug(f"节点 {proxy_name}: 已获取 API 锁，开始测试")
        
        # 1. 通过 API 切换全局代理到当前节点
        try:
            switch_payload = {'name': proxy_name}
            switch_url = f"{args.clash_api_url}/proxies/GLOBAL"
            response = requests.put(switch_url, json=switch_payload, timeout=3)
            if response.status_code != 204:
                logging.warning(f"节点 {proxy_name}: ❌ API 切换失败 (状态码: {response.status_code}) - {response.text}")
                return proxy_name, False
        except requests.exceptions.RequestException as e:
            logging.error(f"节点 {proxy_name}: ❌ API 切换失败 (请求异常: {e})")
            return proxy_name, False

        time.sleep(0.1)

        # --- 阶段一：延迟测试 ---
        try:
            proxies = {"http": args.clash_proxy_url, "https": args.clash_proxy_url}
            response = requests.get(args.latency_test_url, proxies=proxies, timeout=args.latency_timeout)
            latency = response.elapsed.total_seconds() * 1000
            if response.status_code == 204 and latency < args.delay_limit:
                logging.info(f"节点 {proxy_name}: ✅ 延迟测试通过 ({latency:.0f}ms)")
            else:
                logging.warning(f"节点 {proxy_name}: ❌ 延迟测试失败 (状态码: {response.status_code}, 延迟: {latency:.0f}ms)")
                return proxy_name, False
        except requests.exceptions.RequestException as e:
            logging.warning(f"节点 {proxy_name}: ❌ 延迟测试失败 (请求异常: {e})")
            return proxy_name, False

        # --- 阶段二：TLS 握手测试 ---
        try:
            cmd_openssl = [
                "openssl", "s_client",
                "-connect", f"{args.handshake_host}:{args.handshake_port}",
                "-servername", args.handshake_host,
                "-proxy", args.clash_proxy_url.replace("http://", "")
            ]
            result = subprocess.run(cmd_openssl, capture_output=True, text=True, timeout=args.handshake_timeout, check=False)
            
            if result.returncode == 0 and "Protocol" in result.stdout and "Verify return code: 0 (ok)" in result.stdout:
                logging.info(f"节点 {proxy_name}: ✅ TLS握手测试通过")
                return proxy_name, True
            else:
                logging.warning(f"节点 {proxy_name}: ❌ TLS握手测试失败")
                return proxy_name, False
        except subprocess.TimeoutExpired:
            logging.warning(f"节点 {proxy_name}: ❌ TLS握手测试超时")
            return proxy_name, False
        except Exception as e:
            logging.error(f"测试节点 {proxy_name} 时发生未知错误: {e}")
            return proxy_name, False
        finally:
            logging.debug(f"节点 {proxy_name}: 释放 API 锁")

# --- 主函数 ---
def main():
    # --- 参数解析 ---
    parser = argparse.ArgumentParser(description="对 Clash/Mihomo 节点进行两阶段健康度测试。")
    parser.add_argument('--input-file', type=str, default=os.environ.get("ALL_PROXIES_FILE", "all_proxies.yaml"), help='包含所有节点的输入 YAML 文件路径')
    parser.add_argument('--output-file', type=str, default=os.environ.get("HEALTHY_PROXIES_FILE", "healthy_proxies.yaml"), help='用于保存健康节点的输出 YAML 文件路径')
    parser.add_argument('--clash-path', type=str, default=os.environ.get("MIHOMO_PATH", "./mihomo"), help='mihomo (Clash核心) 可执行文件的路径')
    parser.add_argument('--base-config', type=str, default=os.environ.get("BASE_CONFIG_PATH", "config-template.yaml"), help='用于生成临时配置的基础模板文件路径')
    parser.add_argument('--clash-api-url', type=str, default=os.environ.get("CLASH_API_URL", "http://127.0.0.1:9090"), help='Clash RESTful API 的地址')
    parser.add_argument('--clash-proxy-url', type=str, default=f"http://127.0.0.1:{os.environ.get('CLASH_HTTP_PORT', 7890)}", help='Clash HTTP 代理的地址')
    parser.add_argument('--max-workers', type=int, default=int(os.environ.get("MAX_WORKERS", 100)), help='并发测试的最大线程数')
    parser.add_argument('--delay-limit', type=int, default=int(os.environ.get("DELAY_LIMIT", 5000)), help='延迟测试的上限 (毫秒)')
    parser.add_argument('--latency-test-url', type=str, default=os.environ.get("LATENCY_TEST_URL", "http://www.gstatic.com/generate_204"), help='延迟测试的目标 URL')
    parser.add_argument('--latency-timeout', type=int, default=5, help='延迟测试的单次请求超时时间 (秒)')
    parser.add_argument('--handshake-host', type=str, default=os.environ.get("HANDSHAKE_TEST_HOST", "cloudcode-pa.googleapis.com"), help='TLS 握手测试的目标主机')
    parser.add_argument('--handshake-port', type=int, default=443, help='TLS 握手测试的目标端口')
    parser.add_argument('--handshake-timeout', type=int, default=8, help='TLS 握手测试的超时时间 (秒)')
    args = parser.parse_args()

    logging.info(f"开始执行两阶段节点健康度测试... 输入: {args.input_file}, 输出: {args.output_file}")

    # --- 启动主 Clash 进程 ---
    main_clash_process = None
    try:
        # 使用基础配置和所有节点来启动一个主 Clash 实例
        with open(args.base_config, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)
        with open(args.input_file, 'r', encoding='utf-8') as f:
            proxies_config = yaml.safe_load(f)
        base_config['proxies'] = proxies_config['proxies']
        
        main_config_path = "./temp_main_config.yaml"
        with open(main_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f, allow_unicode=True)

        logging.info("正在启动主 Clash 进程用于测试...")
        cmd_main_clash = [args.clash_path, "-f", main_config_path]
        main_clash_process = subprocess.Popen(cmd_main_clash, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3) # 等待主进程完全启动并开放 API 端口
        logging.info("主 Clash 进程已启动，API 服务应该已就绪。")

    except Exception as e:
        logging.fatal(f"启动主 Clash 进程失败: {e}")
        return

    # --- 执行并行测试 ---
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            all_proxies_data = yaml.safe_load(f)
        proxy_names = [p['name'] for p in all_proxies_data['proxies']]
        logging.info(f"共找到 {len(proxy_names)} 个待测试节点")
        logging.info(f"测试将以 {args.max_workers} 个并行工作线程运行，但对 Clash API 的调用将通过锁进行串行化。")

        healthy_proxies = []
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [executor.submit(test_node_pipeline, name, args) for name in proxy_names]

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
        # --- 确保清理主 Clash 进程 ---
        if main_clash_process:
            logging.info("正在关闭主 Clash 进程...")
            main_clash_process.terminate()
            main_clash_process.wait()
            logging.info("主 Clash 进程已关闭。")
        if os.path.exists("./temp_main_config.yaml"):
            os.remove("./temp_main_config.yaml")

if __name__ == "__main__":
    main()