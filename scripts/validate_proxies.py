# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 代理节点格式验证与过滤器
使用 mihomo -t 命令逐个验证代理节点的格式，并过滤掉无效节点。
"""

import yaml
import subprocess
import sys
import os
import argparse
import tempfile

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import setup_logger

class ProxyValidator:
    """
    代理节点格式验证与过滤器
    """

    def __init__(self, mihomo_path: str):
        self.logger = setup_logger("proxy_validator")
        self.mihomo_path = mihomo_path
        self.invalid_proxies = []
        self.valid_proxies = []

    def _create_temp_config(self, proxy: dict) -> str:
        """
        为单个代理节点创建一个临时的最小化配置文件。
        """
        minimal_config = {
            'port': 7890,
            'socks-port': 7891,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'proxies': [proxy]
        }
        
        fd, temp_path = tempfile.mkstemp(suffix=".yaml", text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            yaml.dump(minimal_config, f, allow_unicode=True)
            
        return temp_path

    def validate_single_proxy(self, proxy: dict) -> bool:
        """
        使用 mihomo -t 验证单个代理节点的配置。
        如果有效，则将其添加到 self.valid_proxies 列表中。
        """
        temp_config_path = None
        try:
            temp_config_path = self._create_temp_config(proxy)
            
            command = [self.mihomo_path, '-t', '-f', temp_config_path]
            
            result = subprocess.run(
                command, 
                check=False,
                capture_output=True, 
                text=True,
                encoding='utf-8'
            )

            if result.returncode == 0:
                self.logger.debug(f"节点 '{proxy.get('name')}' 格式正确。")
                self.valid_proxies.append(proxy)
                return True
            else:
                error_message = result.stderr.strip() or result.stdout.strip()
                self.logger.error(f"节点 '{proxy.get('name')}' 格式错误: {error_message}")
                self.invalid_proxies.append({
                    'proxy_name': proxy.get('name'),
                    'error': error_message,
                    'proxy_config': proxy
                })
                return False
        
        except Exception as e:
            self.logger.critical(f"验证节点 '{proxy.get('name')}' 时发生意外错误: {e}", exc_info=True)
            return False
        
        finally:
            if temp_config_path and os.path.exists(temp_config_path):
                os.remove(temp_config_path)

    def run(self, input_file: str, output_valid_file: str = None):
        """
        执行验证和过滤流程
        """
        self.logger.info(f"开始验证和过滤配置文件: {input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                all_proxies_data = yaml.safe_load(f)
            
            if not isinstance(all_proxies_data, dict) or 'proxies' not in all_proxies_data:
                self.logger.error(f"文件 {input_file} 格式不正确，应包含 'proxies' 列表。")
                sys.exit(1)

            all_proxies = all_proxies_data.get('proxies', [])
            total_proxies = len(all_proxies)
            self.logger.info(f"共发现 {total_proxies} 个代理节点，开始逐一验证...")

            for i, proxy in enumerate(all_proxies):
                proxy_identifier = proxy.get('name', str(proxy))
                self.logger.info(f"[{i+1}/{total_proxies}] 正在验证: {proxy_identifier}")
                self.validate_single_proxy(proxy)

            self.logger.info("--- 验证完成 ---")
            self.logger.info(f"有效节点: {len(self.valid_proxies)}")
            self.logger.info(f"无效节点: {len(self.invalid_proxies)}")

            if self.invalid_proxies:
                self.logger.warning("以下被剔除的节点存在格式问题:")
                for item in self.invalid_proxies:
                    self.logger.warning(f"  - 节点: {item['proxy_name']} | 错误: {item['error']}")

            if output_valid_file:
                self.logger.info(f"将 {len(self.valid_proxies)} 个有效节点写入到: {output_valid_file}")
                try:
                    with open(output_valid_file, 'w', encoding='utf-8') as f:
                        yaml.dump({'proxies': self.valid_proxies}, f, allow_unicode=True, default_flow_style=False)
                    self.logger.info("成功写入有效节点文件。")
                except IOError as e:
                    self.logger.error(f"写入有效节点文件失败: {e}")
                    sys.exit(1)
            
            if not self.valid_proxies:
                self.logger.error("没有发现任何有效的代理节点，流程可能无法继续。")
                if os.getenv('CI'):
                    sys.exit(1)

        except FileNotFoundError:
            self.logger.error(f"输入文件不存在: {input_file}")
            sys.exit(1)
        except yaml.YAMLError as e:
            self.logger.error(f"解析 YAML 文件失败: {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.critical(f"发生未知错误: {e}", exc_info=True)
            sys.exit(1)


def find_mihomo_executable():
    """
    在常见路径或 PATH 中查找 mihomo 可执行文件。
    """
    if 'MIHOMO_PATH' in os.environ:
        path = os.environ['MIHOMO_PATH']
        if os.path.exists(path):
            return path

    common_paths = [
        './mihomo',
        '/usr/local/bin/mihomo',
        '/usr/bin/mihomo',
        os.path.expanduser('~/bin/mihomo')
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    from shutil import which
    path = which('mihomo')
    if path:
        return path
        
    return None


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(
        description="使用 mihomo -t 逐个验证代理节点的格式，并过滤掉无效节点。"
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        required=True,
        help='包含 "proxies" 列表的输入 YAML 配置文件路径。'
    )
    parser.add_argument(
        '-o', '--output-valid',
        type=str,
        help='用于保存格式正确的代理节点的输出文件路径。'
    )
    parser.add_argument(
        '--mihomo-path',
        type=str,
        default=None,
        help='mihomo 可执行文件的路径。如果未提供，脚本将尝试自动查找。'
    )
    
    args = parser.parse_args()
    
    mihomo_executable = args.mihomo_path or find_mihomo_executable()
    
    if not mihomo_executable:
        print("错误: 未找到 'mihomo' 可执行文件。", file=sys.stderr)
        print("请使用 --mihomo-path 参数指定路径，或将其添加到系统的 PATH 环境变量中。", file=sys.stderr)
        sys.exit(1)
        
    print(f"使用 mihomo 可执行文件: {mihomo_executable}")

    validator = ProxyValidator(mihomo_path=mihomo_executable)
    validator.run(args.file, args.output_valid)


if __name__ == "__main__":
    main()