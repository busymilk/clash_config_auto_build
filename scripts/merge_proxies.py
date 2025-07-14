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
FILTER_PATTERNS = {
    'hk': re.compile(
        r'\b(HK|Hong[\s_-]?Kong|HKG|HGC)\b(?!-?(check|fail))|香港|港|🇭🇰',
        flags=re.IGNORECASE
    ),
    'us': re.compile(
        r'\b(us|usa|america|united[\s-]?states)\b(?!-?(check|fail))|美|🇺🇸',
        flags=re.IGNORECASE
    ),
    'jp': re.compile(
        r'\b(jp|japan|tokyo|tyo|osaka|nippon)\b(?!-?(check|fail))|日本|日|🇯🇵',
        flags=re.IGNORECASE
    ),
    'uk': re.compile(
        r'\b(uk|england|britain|united[\s-]?kingdom)\b(?!-?(check|fail))|英国|英|🇬🇧',
        flags=re.IGNORECASE
    ),
    'sg': re.compile(
        r'\b(sg|singapore|sin)\b(?!-?(check|fail))|新加坡|新|🇸🇬',
        flags=re.IGNORECASE
    ),
}

# 定义不希望包含的代理名称关键词（黑名单），此规则对所有合并任务生效
BLACKLIST_KEYWORDS = [
    '电报', '日期', '免费', '关注'
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
    logging.info(f"发现 {len(proxy_files)} 个代理文件，准备开始处理...")

    for file_path in proxy_files:
        try:
            logging.info(f"--- 开始处理文件: {file_path} ---")
            with open(file_path, 'r', encoding="utf-8") as f:
                data = yaml.safe_load(f)

                if not data or 'proxies' not in data:
                    logging.warning(f"文件内容为空或缺少 'proxies' 字段: {file_path}")
                    continue

                for proxy in data['proxies']:
                    name = proxy.get('name')
                    server = proxy.get('server')
                    port = proxy.get('port')
                    proxy_type = proxy.get('type')
                    identifier = (server, proxy_type, port)

                    # --- 过滤逻辑 ---
                    # 1. 检查关键信息是否完整
                    if not all(identifier):
                        logging.warning(f"排除信息不完整的代理: {name}")
                        continue

                    # 2. 检查是否为重复节点
                    if identifier in seen_identifiers:
                        # logging.info(f"排除重复代理: {name} | {server}:{port}")
                        continue
                    
                    # 3. (最高优先级) 检查是否包含黑名单关键词
                    if any(keyword in name for keyword in BLACKLIST_KEYWORDS):
                        logging.info(f"排除含黑名单关键词的代理: {name}")
                        continue

                    # 4. 排除特定类型的不安全代理
                    if proxy_type == 'ss' and proxy.get('cipher', '').lower() == 'ss':
                        logging.info(f"排除不安全的 SS 代理: {name}")
                        continue

                    # 5. (仅地区版本) 根据名称白名单进行过滤
                    if name_filter:
                        if name_filter in FILTER_PATTERNS:
                            if not FILTER_PATTERNS[name_filter].search(name):
                                continue # 静默排除不匹配地区的节点
                        else:
                            logging.error(f"未知的过滤器: {name_filter}")
                            return
                    
                    # --- 添加代理 ---
                    seen_identifiers.add(identifier)
                    merged_proxies.append(proxy)
                    # filter_msg = f"({name_filter}) " if name_filter else ""
                    # logging.info(f"添加新代理 {filter_msg}: {name} | 类型: {proxy_type} | 服务器: {server}:{port}")

        except Exception as e:
            logging.error(f"处理文件 {file_path} 时发生严重错误: {e}", exc_info=True)

    logging.info(f"--- 所有文件处理完成 ---")
    logging.info(f"总共合并了 {len(merged_proxies)} 个唯一的代理。")

    try:
        with open(output_file, 'w', encoding="utf-8") as f:
            yaml.dump({'proxies': merged_proxies}, f, default_flow_style=False, allow_unicode=True)
        logging.info(f"成功将合并后的代理写入到: {output_file}")
    except IOError as e:
        logging.error(f"写入文件 {output_file} 失败: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="合并 Clash 代理配置文件，支持按地区过滤和去重。"
    )
    parser.add_argument(
        '--proxies-dir',
        type=str,
        default='external_proxies',
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

    logging.info(f"开始执行合并任务: filter='{args.filter}', output='{args.output}'")
    merge_proxies(args.proxies_dir, args.output, args.filter)
    logging.info("任务执行完毕。")