# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 节点合并与解析器 (并发版)
"""

import yaml
import glob
import argparse
import sys
import os
import re
import ipaddress
from dns import resolver, edns
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import FILTER_PATTERNS, BLACKLIST_KEYWORDS, DnsConfig
from core.logger import setup_logger

DELAY_PREFIX_RE = re.compile(r'^\[\s*\d+ms\]\s*')

def _init_resolver(logger):
    """初始化DNS解析器"""
    res = resolver.Resolver()
    if DnsConfig.CUSTOM_DNS_SERVERS:
        res.nameservers = DnsConfig.CUSTOM_DNS_SERVERS
        logger.info(f"使用自定义DNS服务器: {res.nameservers}")
    res.timeout = 3.0
    res.lifetime = 3.0
    return res

def _resolve_domain(domain_info: tuple, resolver_instance, logger):
    """使用高级解析器解析域名，自动处理CNAME。"""
    domain, proxy = domain_info
    ecs_option = None
    if DnsConfig.ECS_IP:
        try:
            ecs_ip_obj = ipaddress.ip_address(DnsConfig.ECS_IP)
            prefix = 24 if ecs_ip_obj.version == 4 else 56
            ecs_option = edns.ECSOption(ecs_ip_obj.exploded, prefix)
        except ValueError:
            pass # 日志在主函数中只记录一次

    try:
        # 优先解析 AAAA (IPv6)
        answers = resolver_instance.resolve(domain, 'AAAA', ednsoptions=[ecs_option] if ecs_option else None)
        ip = str(answers[0])
        logger.info(f"成功将域名 '{domain}' 解析为 IPv6: {ip}")
        proxy['server'] = ip
        return proxy
    except (resolver.NoAnswer, resolver.NXDOMAIN, resolver.Timeout):
        try:
            # 如果没有IPv6记录，则尝试解析 A (IPv4)
            answers = resolver_instance.resolve(domain, 'A', ednsoptions=[ecs_option] if ecs_option else None)
            ip = str(answers[0])
            logger.info(f"成功将域名 '{domain}' 解析为 IPv4: {ip}")
            proxy['server'] = ip
            return proxy
        except (resolver.NoAnswer, resolver.NXDOMAIN, resolver.Timeout):
            logger.warning(f"无法将域名 '{domain}' 解析为 IPv4 或 IPv6，节点 '{proxy.get('name')}' 将被丢弃。")
            return None
    except Exception as e:
        logger.error(f"解析域名 '{domain}' 时发生未知错误: {e}")
        return None

def merge_proxies(proxies_dir: str, output_file: str, name_filter: str = None) -> None:
    logger = setup_logger("merge_proxies")
    resolver_instance = _init_resolver(logger)
    
    all_proxies, ip_proxies, domain_proxies = [], [], []
    seen_identifiers = set()

    for file_path in glob.glob(f"{proxies_dir}/*.*"):
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or 'proxies' not in data:
                continue
            all_proxies.extend(data['proxies'])
        except Exception as e:
            logger.error(f"处理文件 {file_path} 时发生错误: {e}")

    logger.info(f"从所有文件中共加载了 {len(all_proxies)} 个节点，开始处理...")

    for proxy in all_proxies:
        if not all(proxy.get(k) for k in ['name', 'server', 'port', 'type']):
            continue
        
        proxy['name'] = DELAY_PREFIX_RE.sub('', proxy['name']).strip()
        try:
            proxy['port'] = int(proxy['port'])
        except (ValueError, TypeError):
            continue

        server_address = proxy.get('server', '')
        try:
            ipaddress.ip_address(server_address)
            ip_proxies.append(proxy)
        except ValueError:
            proxy['server_url'] = server_address
            domain_proxies.append(proxy)

    logger.info(f"待解析域名共 {len(domain_proxies)} 个，开始并发解析...")
    if DnsConfig.ECS_IP:
        try: ipaddress.ip_address(DnsConfig.ECS_IP)
        except ValueError: logger.warning(f"无效的ECS IP地址: '{DnsConfig.ECS_IP}'，已禁用ECS功能。")

    resolved_proxies = []
    with ThreadPoolExecutor(max_workers=100) as executor:
        future_to_domain = {executor.submit(_resolve_domain, (p.get('server_url'), p), resolver_instance, logger): p for p in domain_proxies}
        for future in as_completed(future_to_domain):
            result = future.result()
            if result:
                resolved_proxies.append(result)

    logger.info(f"成功解析 {len(resolved_proxies)} 个域名。")

    final_proxies, seen_names = [], set()
    for proxy in ip_proxies + resolved_proxies:
        identifier = proxy.get('server_url', proxy.get('server')), proxy['type'], proxy['port']
        if identifier in seen_identifiers:
            continue
        seen_identifiers.add(identifier)

        original_name = proxy.get('name')
        name, counter = original_name, 2
        while name in seen_names:
            name = f"{original_name} #{counter}"
            counter += 1
        proxy['name'] = name
        seen_names.add(name)

        if not (any(keyword in name for keyword in BLACKLIST_KEYWORDS) or (name_filter and name_filter in FILTER_PATTERNS and not FILTER_PATTERNS[name_filter].search(name))):
            final_proxies.append(proxy)

    logger.info(f"总共为 '{output_file}' 合并了 {len(final_proxies)} 个唯一的代理。")
    try:
        with open(output_file, 'w', encoding="utf-8") as f:
            yaml.dump({'proxies': final_proxies}, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"成功写入合并结果到 {output_file}")
    except IOError as e:
        logger.error(f"写入文件 {output_file} 失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="并发合并、解析并过滤Clash代理配置文件。")
    parser.add_argument('--proxies-dir', type=str, required=True, help='存放代理配置文件的目录路径')
    parser.add_argument('--output', type=str, required=True, help='合并后输出的文件路径')
    parser.add_argument('--filter', type=str, choices=list(FILTER_PATTERNS.keys()), help="根据地区关键词过滤代理名称")
    args = parser.parse_args()
    merge_proxies(args.proxies_dir, args.output, args.filter)

if __name__ == "__main__":
    main()