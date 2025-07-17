# -*- coding: utf-8 -*-
import yaml
import logging
import subprocess
import sys
import os
import argparse
import re

# --- 配置日志记录 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# --- 从 merge_proxies.py 导入过滤器，确保逻辑统一 ---
# (在单一脚本模式下，直接在这里定义)
FILTER_PATTERNS = {
    'hk': re.compile(r'\b(HK|Hong[\s_-]?Kong|HKG|HGC)\b|香港|🇭🇰', re.IGNORECASE),
    'us': re.compile(r'\b(us|usa|america|united[\s-]?states)\b|美国|🇺🇸', re.IGNORECASE),
    'jp': re.compile(r'\b(jp|japan|tokyo|tyo|osaka|nippon)\b|日本|🇯🇵', re.IGNORECASE),
    'uk': re.compile(r'\b(uk|england|britain|united[\s-]?kingdom)\b|英国|🇬🇧', re.IGNORECASE),
    'sg': re.compile(r'\b(sg|singapore|sin)\b|新加坡|🇸🇬', re.IGNORECASE),
}

def run_merge_command(proxies_dir, output_file):
    """调用 merge_proxies.py 脚本来合并所有节点并去重。"""
    command = [
        sys.executable,
        "scripts/merge_proxies.py",
        "--proxies-dir", proxies_dir,
        "--output", output_file
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"成功合并所有节点到 {output_file}")
    except subprocess.CalledProcessError as e:
        logging.error(f"合并所有节点失败:\n{e.stderr}")
        raise

def generate_config_from_template(base_config, proxies_list, output_path):
    """根据基础配置和传入的代理列表生成最终的 Clash 配置文件。"""
    try:
        # 直接使用基础配置的深拷贝，避免互相影响
        config = yaml.safe_load(yaml.safe_dump(base_config))
        config['proxies'] = proxies_list
        
        # 确保代理组中的代理存在于列表中
        

        logging.info(f"为 {output_path} 分配了 {len(proxies_list)} 个节点。")
        with open(output_path, 'w', encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        logging.error(f"生成配置文件 '{output_path}' 时发生未知错误: {e}", exc_info=True)
        raise

def main(pre_tested_nodes_file=None):
    """主执行函数"""
    PROXIES_DOWNLOAD_DIR = os.getenv('PROXY_DIR', 'external_proxies')

    configs_to_generate = [
        # ... (这里的定义保持不变)
        {"filter": None, "output": "config/config.yaml", "template": "config-template.yaml"},
        {"filter": "hk", "output": "config/config_hk.yaml", "template": "config-template.yaml"},
        {"filter": "us", "output": "config/config_us.yaml", "template": "config-template.yaml"},
        {"filter": "jp", "output": "config/config_jp.yaml", "template": "config-template.yaml"},
        {"filter": "uk", "output": "config/config_uk.yaml", "template": "config-template.yaml"},
        {"filter": "sg", "output": "config/config_sg.yaml", "template": "config-template.yaml"},
        {"filter": None, "output": "config/stash.yaml", "template": "stash-template.yaml"},
        {"filter": "hk", "output": "config/stash_hk.yaml", "template": "stash-template.yaml"},
        {"filter": "us", "output": "config/stash_us.yaml", "template": "stash-template.yaml"},
        {"filter": "jp", "output": "config/stash_jp.yaml", "template": "stash-template.yaml"},
        {"filter": "uk", "output": "config/stash_uk.yaml", "template": "stash-template.yaml"},
        {"filter": "sg", "output": "config/stash_sg.yaml", "template": "stash-template.yaml"}
    ]

    # --- 加载所有需要的模板文件 ---
    template_names = {cfg['template'] for cfg in configs_to_generate}
    templates = {}
    for tpl_name in template_names:
        try:
            with open(tpl_name, 'r', encoding="utf-8") as f:
                templates[tpl_name] = yaml.safe_load(f)
        except Exception as e:
            logging.critical(f"无法加载模板 {tpl_name}: {e}", exc_info=True)
            sys.exit(1)

    # --- 核心逻辑：判断是使用预处理模式还是旧模式 ---
    if pre_tested_nodes_file:
        logging.info(f"--- 预处理模式：使用已测试的节点文件 '{pre_tested_nodes_file}' ---")
        with open(pre_tested_nodes_file, 'r', encoding='utf-8') as f:
            healthy_nodes = yaml.safe_load(f).get('proxies', [])
        logging.info(f"已加载 {len(healthy_nodes)} 个健康的节点。")
        
        # 直接使用健康节点进行分发生成
        all_nodes = healthy_nodes
    else:
        # 这是旧的、未经优化的流程，保留以备本地测试
        logging.warning("--- 未提供预处理节点文件，将执行旧的合并流程 (效率较低) ---")
        temp_merged_file = "all_merged_nodes.yaml"
        run_merge_command(PROXIES_DOWNLOAD_DIR, temp_merged_file)
        with open(temp_merged_file, 'r', encoding='utf-8') as f:
            all_nodes = yaml.safe_load(f).get('proxies', [])
        os.remove(temp_merged_file)

    # --- 统一的生成逻辑 ---
    generated_files = []
    for config_info in configs_to_generate:
        filter_key = config_info.get("filter")
        
        if filter_key:
            # 根据地区过滤器筛选节点
            pattern = FILTER_PATTERNS.get(filter_key)
            if not pattern:
                logging.warning(f"未知的过滤器 '{filter_key}'，跳过。")
                continue
            filtered_proxies = [p for p in all_nodes if pattern.search(p.get('name', ''))]
        else:
            # 如果没有过滤器，则使用所有节点
            filtered_proxies = all_nodes
            
        generate_config_from_template(
            base_config=templates[config_info['template']],
            proxies_list=filtered_proxies,
            output_path=config_info['output']
        )
        generated_files.append(config_info['output'])

    # --- 输出产物清单到 GitHub Actions ---
    if 'GITHUB_OUTPUT' in os.environ:
        logging.info("正在将产物清单输出到 GitHub Actions...")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            print(f"generated_files={' '.join(generated_files)}", file=f)

    logging.info("🎉 所有任务已成功完成！")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 Clash 配置文件。")
    parser.add_argument(
        '--use-pre-tested-nodes',
        type=str,
        help='指定一个包含预先测试好的节点的YAML文件，脚本将直接使用这些节点进行分发生成。'
    )
    args = parser.parse_args()
    main(args.use_pre_tested_nodes)
