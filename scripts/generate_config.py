# -*- coding: utf-8 -*-
import yaml
import argparse
import logging

# --- 配置日志记录 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def generate_config(template_path, proxies_path, output_path):
    """
    根据配置模板和代理列表生成最终的 Clash 配置文件。

    :param template_path: Clash 配置模板文件的路径。
    :param proxies_path: 包含 'proxies' 列表的 YAML 文件路径。
    :param output_path: 生成的最终配置文件的保存路径。
    """
    try:
        # --- 读取基础配置模板 ---
        logging.info(f"正在从 {template_path} 读取基础配置模板...")
        with open(template_path, 'r', encoding="utf-8") as f:
            base_config = yaml.safe_load(f)
        if not base_config:
            logging.error(f"配置模板 {template_path} 为空或格式错误。")
            return

        # --- 读取合并后的代理 ---
        logging.info(f"正在从 {proxies_path} 读取代理列表...")
        with open(proxies_path, 'r', encoding="utf-8") as f:
            merged_proxies_data = yaml.safe_load(f)
        
        # 从读取的数据中提取 'proxies' 列表，如果不存在则使用空列表
        proxies_list = merged_proxies_data.get('proxies', [])
        logging.info(f"成功读取 {len(proxies_list)} 个代理。")

        # --- 合并配置 ---
        # 将代理列表添加到基础配置的 'proxies' 键下
        base_config['proxies'] = proxies_list
        logging.info("已将代理列表成功合并到基础配置中。")

        # --- 写入最终配置 ---
        logging.info(f"准备将最终配置写入到 {output_path}...")
        with open(output_path, 'w', encoding="utf-8") as f:
            yaml.dump(base_config, f, default_flow_style=False, allow_unicode=True)
        logging.info(f"成功生成配置文件: {output_path}")

    except FileNotFoundError as e:
        logging.error(f"文件未找到: {e}")
    except Exception as e:
        logging.error(f"生成配置文件时发生未知错误: {e}", exc_info=True)

if __name__ == "__main__":
    # --- 定义需要生成的配置组合 ---
    # 这是一个列表，每个元素是一个字典，定义了一套配置的生成规则。
    # 这样可以轻松地增删不同版本的配置文件。
    configs_to_generate = [
        {
            "template": "config-template.yaml",
            "proxies": "merged-proxies.yaml",
            "output": "config/config.yaml"
        },
        {
            "template": "config-template_hk.yaml",
            "proxies": "merged-proxies_hk.yaml",
            "output": "config/config_hk.yaml"
        },
        {
            "template": "config-template_us.yaml",
            "proxies": "merged-proxies_us.yaml",
            "output": "config/config_us.yaml"
        }
    ]

    # --- 循环生成所有配置文件 ---
    logging.info(f"总共需要生成 {len(configs_to_generate)} 个配置文件。")
    for i, config_info in enumerate(configs_to_generate, 1):
        logging.info(f"--- 开始生成第 {i} 个配置: {config_info['output']} ---")
        generate_config(
            template_path=config_info['template'],
            proxies_path=config_info['proxies'],
            output_path=config_info['output']
        )
    
    logging.info("所有配置文件生成任务已完成。")