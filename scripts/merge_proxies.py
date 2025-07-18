# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 节点合并器 (重构版)
合并指定目录下的所有代理配置文件，支持去重和地区过滤
"""

import yaml
import glob
import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.constants import FILTER_PATTERNS, BLACKLIST_KEYWORDS
from utils.logger import setup_logger


def merge_proxies(proxies_dir: str, output_file: str, name_filter: str = None) -> None:
    """
    合并指定目录下的所有代理配置文件。

    Args:
        proxies_dir: 存放代理配置文件的目录路径
        output_file: 合并后输出的文件路径
        name_filter: 代理名称过滤器, 可选值为 'hk', 'us' 等, 或 None (不过滤)
    """
    logger = setup_logger("merge_proxies")
    
    merged_proxies = []
    seen_identifiers = set()
    seen_names = set()

    proxy_files = glob.glob(f"{proxies_dir}/*.*")
    logger.info(f"发现 {len(proxy_files)} 个代理文件，准备开始处理...")

    for file_path in proxy_files:
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # 检查解析结果是否有效
            if not isinstance(data, dict) or 'proxies' not in data or not isinstance(data['proxies'], list):
                logger.warning(f"跳过无效或格式不正确的文件: {file_path}")
                continue

            for proxy in data['proxies']:
                if not _is_valid_proxy(proxy, logger):
                    continue
                
                # 处理端口格式
                if not _fix_port_format(proxy, logger):
                    continue
                
                # 生成唯一标识符
                identifier = _generate_identifier(proxy)
                
                # 检查重复节点
                if not identifier or identifier in seen_identifiers:
                    continue

                # 处理重复名称
                proxy_name = _handle_duplicate_name(proxy, seen_names, logger)
                
                # 应用过滤规则
                if not _apply_filters(proxy_name, name_filter, logger):
                    continue
                
                # 添加到结果集
                seen_identifiers.add(identifier)
                seen_names.add(proxy_name)
                merged_proxies.append(proxy)

        except yaml.YAMLError as e:
            logger.warning(f"跳过无法解析的YAML文件: {file_path} - 错误: {e}")
            continue
        except Exception as e:
            logger.error(f"处理文件 {file_path} 时发生未知错误: {e}", exc_info=True)
            continue

    logger.info(f"总共为 '{output_file}' 合并了 {len(merged_proxies)} 个唯一的代理。")

    # 写入结果文件
    _write_output_file(merged_proxies, output_file, logger)


def _is_valid_proxy(proxy: dict, logger) -> bool:
    """检查代理配置是否有效"""
    required_fields = ['name', 'server', 'port', 'type']
    for field in required_fields:
        if not proxy.get(field):
            logger.warning(f"代理缺少必要字段 '{field}': {proxy}")
            return False
    return True


def _fix_port_format(proxy: dict, logger) -> bool:
    """修复端口格式，确保为整数"""
    port_val = proxy.get('port')
    if not isinstance(port_val, int):
        try:
            proxy['port'] = int(port_val)
        except (ValueError, TypeError):
            logger.warning(f"代理 '{proxy.get('name')}' 端口格式无效: '{port_val}'，跳过此代理。")
            return False
    return True


def _generate_identifier(proxy: dict) -> tuple:
    """生成代理的唯一标识符"""
    return (proxy.get('server'), proxy.get('type'), proxy.get('port'))


def _handle_duplicate_name(proxy: dict, seen_names: set, logger) -> str:
    """处理重复的代理名称"""
    original_name = proxy.get('name')
    name = original_name
    counter = 2
    
    while name in seen_names:
        name = f"{original_name} #{counter}"
        counter += 1
    
    if original_name != name:
        logger.info(f"发现重复节点名称 '{original_name}'，重命名为 '{name}'")
        proxy['name'] = name
    
    return name


def _apply_filters(proxy_name: str, name_filter: str, logger) -> bool:
    """应用黑名单和地区过滤器"""
    # 黑名单检查
    if any(keyword in proxy_name for keyword in BLACKLIST_KEYWORDS):
        return False
    
    # 地区过滤器检查
    if name_filter and name_filter in FILTER_PATTERNS:
        if not FILTER_PATTERNS[name_filter].search(proxy_name):
            return False
    
    return True


def _write_output_file(merged_proxies: list, output_file: str, logger) -> None:
    """写入合并结果到文件"""
    try:
        with open(output_file, 'w', encoding="utf-8") as f:
            yaml.dump({'proxies': merged_proxies}, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"成功写入合并结果到 {output_file}")
    except IOError as e:
        logger.error(f"写入文件 {output_file} 失败: {e}")
        raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="合并 Clash 代理配置文件，支持按地区过滤和去重。"
    )
    parser.add_argument(
        '--proxies-dir',
        type=str,
        required=True,
        help='存放代理配置文件的目录路径'
    )
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='合并后输出的文件路径'
    )
    parser.add_argument(
        '--filter',
        type=str,
        choices=list(FILTER_PATTERNS.keys()),
        help="根据地区关键词过滤代理名称"
    )

    args = parser.parse_args()
    merge_proxies(args.proxies_dir, args.output, args.filter)


if __name__ == "__main__":
    main()