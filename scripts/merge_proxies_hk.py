import yaml
import os
import glob
import logging
import re

# 配置日志格式和级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 预编译正则表达式（香港关键词白名单）
name_pattern = re.compile(
    r'\b(HK|Hong[\s_-]?Kong|HKG|HGC)\b(?!-?(check|fail))|香港|港|🇭🇰',  # 优化后的香港关键词正则（含Emoji）
    flags=re.IGNORECASE  # 忽略大小写
)

proxies = []
# 使用一个集合来存储已见过的代理标识符，以实现去重
# 标识符是一个包含 (server, type, port) 的元组
seen = set()

# 处理所有下载的代理文件
for file in glob.glob("external_proxies/*.*"):
    try:
        logging.info(f"开始处理文件: {file}")
        with open(file, 'r', encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
            if not data:
                logging.warning(f"文件内容为空: {file}")
                continue
                
            if 'proxies' not in data:
                logging.warning(f"文件缺少proxies字段: {file}")
                continue

            file_proxies = data['proxies']
            logging.info(f"从文件 {file} 中发现 {len(file_proxies)} 个代理")
            
            for proxy in file_proxies:
                # 获取用于去重和筛选的关键信息
                name = proxy.get('name')
                server = proxy.get('server')
                port = proxy.get('port')
                proxy_type = proxy.get('type')

                # 定义节点的唯一标识符
                identifier = (server, proxy_type, port)
                
                # 排除SS类型且加密为ss的代理
                if proxy.get('type') == 'ss' and proxy.get('cipher', '').lower() == 'ss':
                    logging.info(f"排除代理 {name}：类型和加密方式均为SS")
                    continue
                
                # 只保留名称匹配香港关键词的代理
                if not name or not name_pattern.search(name):
                    logging.info(f"排除代理 {name}：名称不含香港关键词")
                    continue
                
                # 检查标识符的所有部分是否存在，并且该标识符尚未被记录
                if all(identifier) and identifier not in seen:
                    seen.add(identifier)
                    proxies.append(proxy)
                    logging.info(f"添加香港代理: {name} | 类型: {proxy_type} | 服务器: {server}:{port}")
                else:
                    # 如果节点是重复的或关键信息不完整，则记录并跳过
                    if all(identifier):
                        logging.info(f"排除重复的香港代理: {name} | 类型: {proxy_type} | 服务器: {server}:{port}")
                    else:
                        logging.warning(f"排除信息不完整的香港代理: {name}")
            
            logging.info(f"文件处理完成: {file}")
    except Exception as e:
        logging.error(f"处理文件 {file} 时发生错误", exc_info=True)

# 保存合并后的代理列表
with open("merged-proxies_hk.yaml", 'w', encoding="utf-8") as f:
    yaml.dump({'proxies': proxies}, f, default_flow_style=False, allow_unicode=True)
