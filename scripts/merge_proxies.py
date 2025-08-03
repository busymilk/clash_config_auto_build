# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 节点合并与解析器
合并、解析、去重并过滤指定目录下的所有代理配置文件
"""

import yaml
import glob
import argparse
import sys
import os
import re
import ipaddress
import dns.resolver

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import FILTER_PATTERNS, BLACKLIST_KEYWORDS
from core.logger import setup_logger

# 用于匹配和移除类似于 [ 123ms] 或 [1234ms] 的前缀
DELAY_PREFIX_RE = re.compile(r'^\[\s*\d+ms\]\s*')

# 配置DNS解析器
DNS_RESOLVER = dns.resolver.Resolver()
DNS_RESOLVER.nameservers = ['8.8.8.8', '1.1.1.1'] # 使用公共DNS
DNS_RESOLVER.timeout = 3.0
DNS_RESOLVER.lifetime = 3.0

def _resolve_domain_to_ip(domain: str, logger) -> str | None:
    """使用指定的DNS服务器将域名解析为IP地址，优先返回IPv6。"""
    try:
        # 优先解析 AAAA (IPv6)
        answers = DNS_RESOLVER.resolve(domain, 'AAAA')
        return str(answers[0])
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        try:
            # 如果没有IPv6记录，则尝试解析 A (IPv4)
            answers = DNS_RESOLVER.resolve(domain, 'A')
            return str(answers[0])
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout) as e:
            logger.warning(f"无法将域名 '{domain}' 解析为 IPv4 或 IPv6: {e}")
            return None
    except Exception as e:
        logger.error(f"解析域名 '{domain}' 时发生未知错误: {e}")
        return None

def merge_proxies(proxies_dir: str, output_file: str, name_filter: str = None) -> None:
    """合并、解析并过滤指定目录下的所有代理配置文件。"""
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

            if not isinstance(data, dict) or 'proxies' not in data or not isinstance(data['proxies'], list):
                logger.warning(f"跳过无效或格式不正确的文件: {file_path}")
                continue

            for proxy in data['proxies']:
                if not _is_valid_proxy(proxy, logger):
                    continue

                # 1. 清理节点名称中的旧延迟信息
                original_name = proxy.get('name', '')
                cleaned_name = DELAY_PREFIX_RE.sub('', original_name).strip()
                if original_name != cleaned_name:
                    proxy['name'] = cleaned_name
                
                # 2. 修复端口格式
                if not _fix_port_format(proxy, logger):
                    continue

                # 3. 解析域名 (如果 server 字段是域名)
                server_address = proxy.get('server', '')
                try:
                    ipaddress.ip_address(server_address)
                except ValueError:
                    # 不是IP地址，是域名
                    if 'server_url' not in proxy:
                        proxy['server_url'] = server_address # 标记原始域名
                    
                    resolved_ip = _resolve_domain_to_ip(server_address, logger)
                    if resolved_ip:
                        proxy['server'] = resolved_ip
                    else:
                        logger.warning(f"因域名解析失败，跳过节点: {proxy.get('name')}")
                        continue # 解析失败，抛弃此节点

                # 4. 生成唯一标识符 (核心去重逻辑)
                identifier = _generate_identifier(proxy)
                if not identifier or identifier in seen_identifiers:
                    continue

                # 5. 处理重名并应用过滤器
                proxy_name = _handle_duplicate_name(proxy, seen_names, logger)
                if not _apply_filters(proxy_name, name_filter, logger):
                    continue
                
                # 6. 添加到结果集
                seen_identifiers.add(identifier)
                seen_names.add(proxy_name)
                merged_proxies.append(proxy)

        except Exception as e:
            logger.error(f"处理文件 {file_path} 时发生严重错误: {e}", exc_info=True)
            continue

    logger.info(f"总共为 '{output_file}' 合并了 {len(merged_proxies)} 个唯一的代理。")
    _write_output_file(merged_proxies, output_file, logger)

def _is_valid_proxy(proxy: dict, logger) -> bool:
    """检查代理配置是否有效"""
    required_fields = ['name', 'server', 'port', 'type']
    return all(proxy.get(field) for field in required_fields)

def _fix_port_format(proxy: dict, logger) -> bool:
    """修复端口格式，确保为整数"""
    try:
        proxy['port'] = int(proxy.get('port'))
        return True
    except (ValueError, TypeError):
        logger.warning(f"代理 '{proxy.get('name')}' 端口格式无效，跳过。")
        return False

def _generate_identifier(proxy: dict) -> tuple:
    """根据 server_url (如果存在) 或 server 生成唯一标识符"""
    # 您的核心思想：优先使用原始域名作为唯一标识的一部分
    server_key = proxy.get('server_url', proxy.get('server'))
    return (server_key, proxy.get('type'), proxy.get('port'))

def _handle_duplicate_name(proxy: dict, seen_names: set, logger) -> str:
    """处理重复的代理名称"""
    original_name = proxy.get('name')
    name = original_name
    counter = 2
    while name in seen_names:
        name = f"{original_name} #{counter}"
        counter += 1
    if original_name != name:
        proxy['name'] = name
    return name

def _apply_filters(proxy_name: str, name_filter: str, logger) -> bool:
    """应用黑名单和地区过滤器"""
    if any(keyword in proxy_name for keyword in BLACKLIST_KEYWORDS):
        return False
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
    parser = argparse.ArgumentParser(description="合并、解析并过滤Clash代理配置文件。")
    parser.add_argument('--proxies-dir', type=str, required=True, help='存放代理配置文件的目录路径')
    parser.add_argument('--output', type=str, required=True, help='合并后输出的文件路径')
    parser.add_argument('--filter', type=str, choices=list(FILTER_PATTERNS.keys()), help="根据地区关键词过滤代理名称")
    args = parser.parse_args()
    merge_proxies(args.proxies_dir, args.output, args.filter)

if __name__ == "__main__":
    main()
