# -*- coding: utf-8 -*-
import yaml
import logging
import subprocess
import sys
import os

# --- 配置日志记录 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

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

def generate_config(base_config, proxies_path, output_path):
    """根据基础配置和代理列表生成最终的 Clash 配置文件。"""
    try:
        # 直接使用基础配置，不做任何修改
        config = base_config

        # 读取并合并代理节点列表
        with open(proxies_path, 'r', encoding="utf-8") as f:
            proxies_data = yaml.safe_load(f)
        config['proxies'] = proxies_data.get('proxies', [])
        logging.info(f"成功读取并合并 {len(config['proxies'])} 个代理节点到 {output_path}。")

        # 写入最终配置
        with open(output_path, 'w', encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        logging.info(f"成功生成配置文件: {output_path}")

    except Exception as e:
        logging.error(f"生成配置文件 '{output_path}' 时发生未知错误: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    # --- 唯一的真相来源 (Single Source of Truth) ---
    configs_to_generate = [
        {"filter": None, "proxies_file": "merged-proxies.yaml", "output": "config/config.yaml"},
        {"filter": "hk", "proxies_file": "merged-proxies_hk.yaml", "output": "config/config_hk.yaml"},
        {"filter": "us", "proxies_file": "merged-proxies_us.yaml", "output": "config/config_us.yaml"},
        {"filter": "jp", "proxies_file": "merged-proxies_jp.yaml", "output": "config/config_jp.yaml"},
        {"filter": "uk", "proxies_file": "merged-proxies_uk.yaml", "output": "config/config_uk.yaml"},
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
            output_path=config_info['output']
        )
        generated_files.append(config_info['output'])
    
    # --- 步骤4: 将生成的文件列表输出到 GitHub Actions ---
    if 'GITHUB_OUTPUT' in os.environ:
        logging.info("正在将产物清单输出到 GitHub Actions...")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            file_list_str = ' '.join(generated_files)
            print(f"generated_files={file_list_str}", file=f)
            logging.info(f"输出的清单: {file_list_str}")

    logging.info("🎉 所有任务已成功完成！")