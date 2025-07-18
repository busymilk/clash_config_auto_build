# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 节点测试器 (重构版)
使用 mihomo 核心测试代理节点的健康状况
"""

import argparse
import subprocess
import time
import urllib.parse
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import NodeTestConfig, PathConfig
from core.logger import setup_logger


class NodeTester:
    """节点测试器"""
    
    def __init__(self, args):
        self.logger = setup_logger("node_tester")
        self.args = args
        self.mihomo_process = None
    
    def prepare_test_config(self, source_path: str, dest_path: str, 
                          template_path: str = PathConfig.CONFIG_TEMPLATE) -> list:
        """读取源配置文件，注入测试所需的核心配置，并合并模板中的DNS配置"""
        self.logger.info(f"准备测试配置文件: {source_path} -> {dest_path}")
        
        try:
            # 加载基础模板配置
            with open(template_path, 'r', encoding='utf-8') as f:
                base_config = yaml.safe_load(f)

            # 加载代理节点数据
            with open(source_path, 'r', encoding='utf-8') as f:
                proxies_data = yaml.safe_load(f)

            if not proxies_data or 'proxies' not in proxies_data or not proxies_data['proxies']:
                self.logger.error(f"源文件 {source_path} 没有代理节点")
                return []

            # 创建测试配置，深拷贝避免修改原始模板
            config = yaml.safe_load(yaml.safe_dump(base_config))

            # 添加/覆盖测试必需的设置
            config.update({
                'external-controller': '127.0.0.1:9090',
                'log-level': 'info',
                'mixed-port': 7890,  # 必须开启mixed-port才能通过socks5选择出口节点
                'mode': 'Rule',
            })

            # 确保规则部分存在
            if 'rules' not in config:
                config['rules'] = []

            # 添加代理节点到测试配置
            config['proxies'] = proxies_data['proxies']

            # 保存测试配置文件
            with open(dest_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)

            self.logger.info(f'测试配置已准备完成并保存到 {dest_path}')
            return config.get("proxies", [])
            
        except Exception as e:
            self.logger.error(f'准备测试配置失败: {e}')
            return []

    def start_mihomo(self, mihomo_path: str, config_path: str) -> subprocess.Popen:
        """启动 mihomo 核心进程"""
        self.logger.info(f"启动 mihomo: {config_path}")
        
        try:
            process = subprocess.Popen(
                [mihomo_path, "-f", config_path],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                encoding='utf-8'
            )
            
            # 等待进程启动
            time.sleep(5)
            
            # 检查进程状态
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.logger.error(f"mihomo 进程提前退出，退出码: {process.returncode}")
                if stdout:
                    self.logger.error(f"stdout: {stdout.strip()}")
                if stderr:
                    self.logger.error(f"stderr: {stderr.strip()}")
                return None

            self.logger.info("mihomo 进程启动成功")
            return process
            
        except Exception as e:
            self.logger.error(f"启动 mihomo 失败: {e}")
            return None

    def stop_mihomo(self, process: subprocess.Popen) -> None:
        """停止 mihomo 核心进程"""
        if process:
            self.logger.info("正在停止 mihomo 进程...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.logger.warning("mihomo 进程未能正常终止，强制杀死")
                process.kill()
            self.logger.info("mihomo 进程已停止")

    def check_proxy_delay(self, proxy: dict, api_url: str, timeout: int, 
                         delay_limit: int, test_url: str) -> dict:
        """通过 mihomo API 测试单个代理的延迟"""
        proxy_name = proxy.get("name")
        if not proxy_name:
            self.logger.error("代理名称缺失")
            return None
            
        try:
            quoted_proxy_name = urllib.parse.quote(proxy_name)
            url = f"http://{api_url}/proxies/{quoted_proxy_name}/delay?timeout={timeout}&url={urllib.parse.quote(test_url)}"
            
            response = requests.get(url, timeout=(timeout / 1000) + 5)
            response.raise_for_status()
            
            data = response.json()
            delay = data.get("delay", -1)
            
            if 0 < delay <= delay_limit:
                self.logger.info(f"代理 '{proxy_name}' 延迟测试通过: {delay}ms")
                return proxy
            else:
                self.logger.debug(f"代理 '{proxy_name}' 延迟测试失败: {delay}ms (限制: {delay_limit}ms)")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"代理 '{proxy_name}' 请求异常: {e}")
            return None
        except ValueError as e:
            self.logger.debug(f"代理 '{proxy_name}' JSON解析错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"代理 '{proxy_name}' 测试异常: {e}")
            return None

    def test_all_proxies(self, proxies_to_test: list) -> list:
        """并发测试所有代理节点"""
        self.logger.info(f"开始测试 {len(proxies_to_test)} 个代理节点...")
        
        healthy_proxies = []
        api_url = "127.0.0.1:9090"
        
        with ThreadPoolExecutor(max_workers=self.args.max_workers) as executor:
            # 提交所有测试任务
            future_to_proxy = {
                executor.submit(
                    self.check_proxy_delay, 
                    proxy, 
                    api_url, 
                    self.args.timeout, 
                    self.args.delay_limit, 
                    self.args.test_url
                ): proxy 
                for proxy in proxies_to_test
            }
            
            # 收集测试结果
            completed = 0
            for future in as_completed(future_to_proxy):
                completed += 1
                result = future.result()
                if result:
                    healthy_proxies.append(result)
                
                # 每100个节点报告一次进度
                if completed % 100 == 0:
                    self.logger.info(f"已测试 {completed}/{len(proxies_to_test)} 个节点，健康节点: {len(healthy_proxies)}")
        
        self.logger.info(f"测试完成！健康节点: {len(healthy_proxies)}/{len(proxies_to_test)}")
        return healthy_proxies

    def save_healthy_nodes(self, healthy_proxies: list, output_file: str) -> None:
        """保存健康节点到文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump({'proxies': healthy_proxies}, f, allow_unicode=True)
            self.logger.info(f"健康节点列表已保存到 {output_file}")
        except Exception as e:
            self.logger.error(f"保存健康节点失败: {e}")
            raise

    def run(self) -> None:
        """主执行函数"""
        test_config_path = NodeTestConfig.TEST_CONFIG_FILE
        
        try:
            # 准备测试配置
            proxies_to_test = self.prepare_test_config(self.args.input_file, test_config_path)
            if not proxies_to_test:
                self.logger.error("没有可测试的代理节点")
                return

            # 启动 mihomo
            self.mihomo_process = self.start_mihomo(self.args.clash_path, test_config_path)
            if not self.mihomo_process:
                self.logger.error("mihomo 启动失败")
                return

            # 测试所有代理
            healthy_proxies = self.test_all_proxies(proxies_to_test)

            # 保存结果
            self.save_healthy_nodes(healthy_proxies, self.args.output_file)

        except Exception as e:
            self.logger.error(f"节点测试过程中发生错误: {e}", exc_info=True)
            raise
        finally:
            # 清理资源
            self.stop_mihomo(self.mihomo_process)
            self.logger.info("资源清理完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Clash/mihomo 代理节点测试器")
    
    parser.add_argument("-i", "--input-file", required=True, 
                       help="输入的 clash 配置文件路径")
    parser.add_argument("-o", "--output-file", required=True, 
                       help="保存健康代理列表的文件路径")
    parser.add_argument("-p", "--clash-path", required=True, 
                       help="mihomo 可执行文件路径")
    parser.add_argument("--test-url", default=NodeTestConfig.DEFAULT_TEST_URL, 
                       help="测试代理延迟的URL")
    parser.add_argument("--delay-limit", type=int, default=NodeTestConfig.DEFAULT_DELAY_LIMIT, 
                       help="最大可接受延迟(ms)")
    parser.add_argument("--timeout", type=int, default=NodeTestConfig.DEFAULT_TIMEOUT, 
                       help="延迟测试请求超时时间(ms)")
    parser.add_argument("--max-workers", type=int, default=NodeTestConfig.DEFAULT_MAX_WORKERS, 
                       help="并发测试线程数")

    args = parser.parse_args()
    
    tester = NodeTester(args)
    tester.run()


if __name__ == "__main__":
    main()