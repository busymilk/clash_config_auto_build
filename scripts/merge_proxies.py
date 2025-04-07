import yaml
import os
import glob
import logging

# 配置日志格式和级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)


proxies = []
seen = set()

# 处理所有下载的代理文件
for file in glob.glob("external_proxies/*.*"):
    try:
        logging.info(f"开始处理文件: {file}")
        with open(file, 'r',encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
            if not data:
                logging.warning(f"文件内容为空: {file}")
                continue
                
            if 'proxies' not in data:
                logging.warning(f"文件缺少proxies字段: {file}")
                continue

            file_proxies = data['proxies']
            logging.info(f"从文件 {file} 中发现 {len(file_proxies)} 个代理")
            
            if data and 'proxies' in data:
                for proxy in data['proxies']:
                    # 使用name作为唯一标识
                    name = proxy.get('name')

                    # 新增过滤条件：排除 type 和 cipher 均为 ss 的代理，防止报错
                    if proxy.get('type') == 'ss' and proxy.get('cipher', '').lower() == 'ss':
                        logging.info(f"排除代理 {name}：类型和加密方式均为 SS")
                        continue  # 直接跳过，不添加到列表
                    
                    if name and name not in seen:
                        seen.add(name)
                        proxies.append(proxy)
                        logging.info(f"添加新代理: {name} | 类型: {proxy.get('type')} | 服务器: {proxy.get('server')}")
            logging.info(f"文件处理完成: {file}")
            print(f"文件处理完成: {file}")
    except Exception as e:
        logging.error(f"处理文件 {file} 时发生错误", exc_info=True)

# 保存合并后的proxies
with open("merged-proxies.yaml", 'w',encoding="utf-8") as f:
    yaml.dump({'proxies': proxies}, f, default_flow_style=False, allow_unicode=True)
