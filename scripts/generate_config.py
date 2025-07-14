
# -*- coding: utf-8 -*-
import yaml
import logging
import subprocess
import sys
import os
from copy import deepcopy

# --- 配置日志记录 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# --- 全局常量定义 ---
GENERIC_PROXY_GROUP_NAMES = {
    "选择代理", "自动优选", "负载均衡", "手动选择", "DIRECT", "REJECT",
    "Apple", "Telegram", "YouTube", "Netflix", "Disney+", "Bilibili", "OpenAI",
}

def is_region_specific_group(group_name):
    """判断一个代理组名称是否是地区特有的。"""
    region_keywords = ["香港", "日本", "美国", "新加坡", "英国", "台湾", "韩国"]
    return any(keyword in group_name for keyword in region_keywords)

def run_merge_command(filter_code, output_file):
    """调用 merge_proxies.py 脚本来生成临时的节点数据文件。"""
    command = [
        sys.executable, # 使用当前 Python 解释器
        "scripts/merge_proxies.py",
        "--output", output_file
    ]
    if filter_code:
        command.extend(["--filter", filter_code])
    
    logging.info(f"执行合并命令: {' '.join(command)}")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"成功生成数据文件: {output_file}")
    except subprocess.CalledProcessError as e:
        logging.error(f"合并节点失败 (filter: {filter_code}):\n{e.stderr}")
        raise

def generate_config(base_config, proxies_path, output_path, is_region_specific=False):
    """根据基础配置、代理列表和版本类型生成最终的 Clash 配置文件。"""
    try:
        config = deepcopy(base_config)
        if is_region_specific:
            logging.info(f"为地区版本 {output_path} 执行代理组裁剪...")
            original_groups = config.get('proxy-groups', [])
            kept_groups = []
            for group in original_groups:
                group_name = group.get('name')
                if group_name in GENERIC_PROXY_GROUP_NAMES or not is_region_specific_group(group_name):
                    kept_groups.append(group)
                else:
                    logging.info(f"  -> 裁剪地区特定组: {group_name}")
            kept_group_names = {group.get('name') for group in kept_groups}
            for group in kept_groups:
                if 'proxies' in group:
                    original_proxies = group['proxies']
                    group['proxies'] = [p for p in original_proxies if p in kept_group_names or p in GENERIC_PROXY_GROUP_NAMES]
                    if len(original_proxies) != len(group['proxies']):
                        logging.info(f"  -> 清理组 '{group['name']}' 的内部引用: {original_proxies} -> {group['proxies']}")
            config['proxy-groups'] = kept_groups
            logging.info("代理组裁剪完成。")

        with open(proxies_path, 'r', encoding="utf-8") as f:
            proxies_data = yaml.safe_load(f)
        config['proxies'] = proxies_data.get('proxies', [])
        logging.info(f"成功读取并合并 {len(config['proxies'])} 个代理节点。")

        with open(output_path, 'w', encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        logging.info(f"成功生成配置文件: {output_path}")

    except Exception as e:
        logging.error(f"生成配置文件 '{output_path}' 时发生未知错误: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    # --- 唯一的真相来源 (Single Source of Truth) ---
    configs_to_generate = [
        {"filter": None, "proxies_file": "merged-proxies.yaml", "output": "config/config.yaml", "is_region_specific": False},
        {"filter": "hk", "proxies_file": "merged-proxies_hk.yaml", "output": "config/config_hk.yaml", "is_region_specific": True},
        {"filter": "us", "proxies_file": "merged-proxies_us.yaml", "output": "config/config_us.yaml", "is_region_specific": True},
        {"filter": "jp", "proxies_file": "merged-proxies_jp.yaml", "output": "config/config_jp.yaml", "is_region_specific": True},
        {"filter": "uk", "proxies_file": "merged-proxies_uk.yaml", "output": "config/config_uk.yaml", "is_region_specific": True},
    ]

    # --- 步骤1: 准备所有需要的节点数据文件 ---
    logging.info("--- 开始准备所有需要的节点数据文件 ---")
    for config_info in configs_to_generate:
        run_merge_command(config_info['filter'], config_info['proxies_file'])
    logging.info("--- 所有节点数据文件准备就绪 ---")

    # --- 步骤2: 加载唯一的“母版”模板 ---
    base_template_path = "config-template.yaml"
    logging.info(f"正在从唯一的源模板 {base_template_path} 加载基础配置...")
    try:
        with open(base_template_path, 'r', encoding="utf-8") as f:
            base_config_data = yaml.safe_load(f)
        if not base_config_data:
            raise ValueError("基础配置文件为空或格式错误。")
    except (FileNotFoundError, ValueError) as e:
        logging.critical(f"无法加载基础模板: {e}", exc_info=True)
        sys.exit(1)

    # --- 步骤3: 循环生成所有最终的配置文件 ---
    logging.info("--- 开始生成所有最终配置文件 ---")
    generated_files = []
    for i, config_info in enumerate(configs_to_generate, 1):
        logging.info(f"--- ({i}/{len(configs_to_generate)}) 开始生成: {config_info['output']} ---")
        generate_config(
            base_config=base_config_data,
            proxies_path=config_info['proxies_file'],
            output_path=config_info['output'],
            is_region_specific=config_info['is_region_specific']
        )
        generated_files.append(config_info['output'])
    
    # --- 步骤4: 将生成的文件列表输出到 GitHub Actions ---
    # 这是一个关键步骤，用于后续工作流的自动化
    if 'GITHUB_OUTPUT' in os.environ:
        logging.info("正在将产物清单输出到 GitHub Actions...")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            # 将文件列表转换成一个空格分隔的字符串
            file_list_str = ' '.join(generated_files)
            print(f"generated_files={file_list_str}", file=f)
            logging.info(f"输出的清单: {file_list_str}")

    logging.info("🎉 所有任务已成功完成！")
