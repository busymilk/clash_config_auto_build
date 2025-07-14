
# -*- coding: utf-8 -*-
import yaml
import logging
from copy import deepcopy

# --- 配置日志记录 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# --- 全局常量定义 ---
# 定义在地区版本中需要保留的通用代理组名称
# 其他所有包含地区性关键词（如“香港-”、“美国-”等）的代理组将被移除
GENERIC_PROXY_GROUP_NAMES = {
    "选择代理",
    "自动优选",
    "负载均衡",
    "手动选择",
    "DIRECT",       # DIRECT 本身不是一个组，但可能会被引用
    "REJECT",       # REJECT 同上
    "Apple",        # 示例：其他你希望保留的通用策略组
    "Telegram",
    "YouTube",
    "Netflix",
    "Disney+",
    "Bilibili",
    "OpenAI",
}

def is_region_specific_group(group_name):
    """判断一个代理组名称是否是地区特有的。"""
    # 这里可以根据你的命名习惯进行调整
    region_keywords = ["香港", "日本", "美国", "新加坡", "英国", "台湾", "韩国"]
    return any(keyword in group_name for keyword in region_keywords)

def generate_config(base_config, proxies_path, output_path, is_region_specific=False):
    """
    根据基础配置、代理列表和版本类型生成最终的 Clash 配置文件。

    :param base_config: 已加载的基础配置模板 (Python 字典对象)。
    :param proxies_path: 包含 'proxies' 列表的 YAML 文件路径。
    :param output_path: 生成的最终配置文件的保存路径。
    :param is_region_specific: 布尔值，标记是否为地区特定版本。
    """
    try:
        # --- 深拷贝基础配置，避免修改影响其他版本 ---
        config = deepcopy(base_config)

        # --- 如果是地区特定版本，则执行裁剪逻辑 ---
        if is_region_specific:
            logging.info(f"为地区版本 {output_path} 执行代理组裁剪...")
            original_groups = config.get('proxy-groups', [])
            
            # 1. 筛选出要保留的代理组
            kept_groups = []
            for group in original_groups:
                group_name = group.get('name')
                if group_name in GENERIC_PROXY_GROUP_NAMES or not is_region_specific_group(group_name):
                    kept_groups.append(group)
                else:
                    logging.info(f"  -> 裁剪地区特定组: {group_name}")
            
            # 2. 清理被保留组内部对已删除组的引用
            kept_group_names = {group.get('name') for group in kept_groups}
            for group in kept_groups:
                if 'proxies' in group:
                    original_proxies = group['proxies']
                    # 过滤掉所有不存在于保留组名集合中的引用
                    group['proxies'] = [p for p in original_proxies if p in kept_group_names or p in GENERIC_PROXY_GROUP_NAMES]
                    if len(original_proxies) != len(group['proxies']):
                        logging.info(f"  -> 清理组 '{group['name']}' 的内部引用: {original_proxies} -> {group['proxies']}")

            config['proxy-groups'] = kept_groups
            logging.info("代理组裁剪完成。")

        # --- 读取并合并代理节点列表 ---
        logging.info(f"正在从 {proxies_path} 读取代理节点...")
        with open(proxies_path, 'r', encoding="utf-8") as f:
            proxies_data = yaml.safe_load(f)
        
        proxies_list = proxies_data.get('proxies', [])
        logging.info(f"成功读取 {len(proxies_list)} 个代理节点。")

        config['proxies'] = proxies_list
        logging.info("已将代理节点成功合并到配置中。")

        # --- 写入最终配置 ---
        logging.info(f"准备将最终配置写入到 {output_path}...")
        with open(output_path, 'w', encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        logging.info(f"成功生成配置文件: {output_path}")

    except FileNotFoundError as e:
        logging.error(f"文件未找到: {e}")
    except Exception as e:
        logging.error(f"生成配置文件 '{output_path}' 时发生未知错误: {e}", exc_info=True)

if __name__ == "__main__":
    # --- 定义需要生成的配置组合 ---
    configs_to_generate = [
        {
            "proxies": "merged-proxies.yaml",
            "output": "config/config.yaml",
            "is_region_specific": False # 全局版本
        },
        {
            "proxies": "merged-proxies_hk.yaml",
            "output": "config/config_hk.yaml",
            "is_region_specific": True
        },
        {
            "proxies": "merged-proxies_us.yaml",
            "output": "config/config_us.yaml",
            "is_region_specific": True
        },
        {
            "proxies": "merged-proxies_jp.yaml",
            "output": "config/config_jp.yaml",
            "is_region_specific": True
        },
        {
            "proxies": "merged-proxies_uk.yaml",
            "output": "config/config_uk.yaml",
            "is_region_specific": True
        }
    ]

    # --- 首先加载一次唯一的“母版”模板 ---
    base_template_path = "config-template.yaml"
    logging.info(f"正在从唯一的源模板 {base_template_path} 加载基础配置...")
    try:
        with open(base_template_path, 'r', encoding="utf-8") as f:
            base_config_data = yaml.safe_load(f)
        if not base_config_data:
            raise ValueError("基础配置文件为空或格式错误。")
    except (FileNotFoundError, ValueError) as e:
        logging.critical(f"无法加载基础模板: {e}", exc_info=True)
        exit(1)

    # --- 循环生成所有配置文件 ---
    logging.info(f"总共需要生成 {len(configs_to_generate)} 个配置文件。")
    for i, config_info in enumerate(configs_to_generate, 1):
        logging.info(f"--- 开始生成第 {i} 个配置: {config_info['output']} ---")
        generate_config(
            base_config=base_config_data,
            proxies_path=config_info['proxies'],
            output_path=config_info['output'],
            is_region_specific=config_info['is_region_specific']
        )
    
    logging.info("所有配置文件生成任务已完成。")
