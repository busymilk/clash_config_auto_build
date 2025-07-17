# -*- coding: utf-8 -*-
import yaml
import glob
import logging
import re
import argparse

# --- 配置日志记录 ---
# 设置日志的格式和级别，方便调试和追踪脚本执行情况
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # 输出到控制台
    ]
)

# --- 常量定义 ---
# 定义不同地区的正则表达式过滤器，用于根据节点名称筛选特定地区的代理
# 使用更严格的单词边界 \b 来避免部分匹配造成的错误
FILTER_PATTERNS = {
    'hk': re.compile(
        r'\b(HK|Hong[\s_-]?Kong|HKG|HGC)\b|香港|🇭🇰',
        flags=re.IGNORECASE
    ),
    'us': re.compile(
        r'\b(us|usa|america|united[\s-]?states)\b|美国|🇺🇸',
        flags=re.IGNORECASE
    ),
    'jp': re.compile(
        r'\b(jp|japan|tokyo|tyo|osaka|nippon)\b|日本|🇯🇵',
        flags=re.IGNORECASE
    ),
    'uk': re.compile(
        r'\b(uk|england|britain|united[\s-]?kingdom)\b|英国|🇬🇧',
        flags=re.IGNORECASE
    ),
    'sg': re.compile(
        r'\b(sg|singapore|sin)\b|新加坡|🇸🇬',
        flags=re.IGNORECASE
    ),
}

# 定义不希望包含的代理名称关键词（黑名单），此规则对所有合并任务生效
BLACKLIST_KEYWORDS = [
    '日期', '免费', '关注'
]

def merge_proxies(proxies_dir, output_file, name_filter=None):
    """
    合并指定目录下的所有代理配置文件。

    :param proxies_dir: 存放代理配置文件的目录路径 (例如: "external_proxies")
    :param output_file: 合并后输出的文件路径 (例如: "merged-proxies.yaml")
    :param name_filter: 代理名称过滤器, 可选值为 'hk', 'us' 等, 或 None (不过滤)
    """
    merged_proxies = []
    seen_identifiers = set()

    proxy_files = glob.glob(f"{proxies_dir}/*.*")
    # logging.info(f"发现 {len(proxy_files)} 个代理文件，准备开始处理...")

    for file_path in proxy_files:
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                # 使用 yaml.safe_load 尝试解析
                data = yaml.safe_load(f)

                # 检查解析结果是否有效
                if not isinstance(data, dict) or 'proxies' not in data or not isinstance(data['proxies'], list):
                    logging.warning(f"跳过无效或格式不正确的文件: {file_path}")
                    continue

                for proxy in data['proxies']:
                    name = proxy.get('name')
                    server = proxy.get('server')
                    port_val = proxy.get('port')
                    proxy_type = proxy.get('type')

                    # --- 检查端口是否为整数 ---
                    if not isinstance(port_val, int):
                        try:
                            proxy['port'] = int(port_val)
                        except (ValueError, TypeError):
                            logging.warning(f"Proxy '{name}' has invalid port format: '{port_val}'. Skipping this proxy.")
                            continue # Skip this proxy if port is not an int

                    identifier = (server, proxy_type, proxy.get('port'))

                    if not all(identifier):
                        continue
                    if identifier in seen_identifiers:
                        continue
                    if any(keyword in name for keyword in BLACKLIST_KEYWORDS):
                        continue
                    if proxy_type == 'ss' and proxy.get('cipher', '').lower() == 'ss':
                        continue
                    if name_filter and name_filter in FILTER_PATTERNS:
                        if not FILTER_PATTERNS[name_filter].search(name):
                            continue
                    
                    seen_identifiers.add(identifier)
                    merged_proxies.append(proxy)

        except yaml.YAMLError as e:
            # 如果文件不是有效的YAML格式，则捕获错误，打印警告并跳过
            logging.warning(f"跳过无法解析的YAML文件: {file_path} - 错误: {e}")
            continue
        except Exception as e:
            # 捕获其他可能的IO错误等
            logging.error(f"处理文件 {file_path} 时发生未知错误: {e}", exc_info=True)
            continue

    logging.info(f"总共为 '{output_file}' 合并了 {len(merged_proxies)} 个唯一的代理。")

    try:
        with open(output_file, 'w', encoding="utf-8") as f:
            yaml.dump({'proxies': merged_proxies}, f, default_flow_style=False, allow_unicode=True)
    except IOError as e:
        logging.error(f"写入文件 {output_file} 失败: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="合并 Clash 代理配置文件，支持按地区过滤和去重。"
    )
    parser.add_argument(
        '--proxies-dir',
        type=str,
        required=True, # 由总指挥脚本提供，因此设为必填
        help='存放代理配置文件的目录路径'
    )
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='合并后输出的文件路径 (例如: merged-proxies.yaml)'
    )
    parser.add_argument(
        '--filter',
        type=str,
        choices=list(FILTER_PATTERNS.keys()),
        help="根据地区关键词过滤代理名称"
    )

    args = parser.parse_args()

    merge_proxies(args.proxies_dir, args.output, args.filter)
