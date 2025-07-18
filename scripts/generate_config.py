# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 配置生成器 (重构版)
根据健康节点生成各地区的 Clash 配置文件
"""

import yaml
import subprocess
import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.constants import FILTER_PATTERNS, CONFIGS_TO_GENERATE, PathConfig
from utils.logger import setup_logger


class ConfigGenerator:
    """配置文件生成器"""
    
    def __init__(self):
        self.logger = setup_logger("config_generator")
        self.templates = {}
    
    def run_merge_command(self, proxies_dir: str, output_file: str) -> None:
        """调用 merge_proxies.py 脚本来合并所有节点并去重"""
        command = [
            sys.executable,
            "scripts/merge_proxies_refactored.py",
            "--proxies-dir", proxies_dir,
            "--output", output_file
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.logger.info(f"成功合并所有节点到 {output_file}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"合并所有节点失败:\n{e.stderr}")
            raise
    
    def load_templates(self) -> None:
        """加载所有需要的模板文件"""
        template_names = {cfg['template'] for cfg in CONFIGS_TO_GENERATE}
        
        for tpl_name in template_names:
            try:
                with open(tpl_name, 'r', encoding="utf-8") as f:
                    self.templates[tpl_name] = yaml.safe_load(f)
                self.logger.info(f"成功加载模板: {tpl_name}")
            except Exception as e:
                self.logger.critical(f"无法加载模板 {tpl_name}: {e}", exc_info=True)
                sys.exit(1)
    
    def load_healthy_nodes(self, pre_tested_nodes_file: str = None) -> list:
        """加载健康节点列表"""
        if pre_tested_nodes_file:
            self.logger.info(f"--- 预处理模式：使用已测试的节点文件 '{pre_tested_nodes_file}' ---")
            try:
                with open(pre_tested_nodes_file, 'r', encoding='utf-8') as f:
                    healthy_nodes = yaml.safe_load(f).get('proxies', [])
                self.logger.info(f"已加载 {len(healthy_nodes)} 个健康的节点。")
                return healthy_nodes
            except Exception as e:
                self.logger.error(f"加载预测试节点文件失败: {e}")
                raise
        else:
            # 旧的合并流程，保留以备本地测试
            self.logger.warning("--- 未提供预处理节点文件，将执行旧的合并流程 (效率较低) ---")
            temp_merged_file = PathConfig.TEMP_MERGED_FILE
            self.run_merge_command(PathConfig.PROXY_DIR, temp_merged_file)
            
            try:
                with open(temp_merged_file, 'r', encoding='utf-8') as f:
                    all_nodes = yaml.safe_load(f).get('proxies', [])
                os.remove(temp_merged_file)
                return all_nodes
            except Exception as e:
                self.logger.error(f"加载合并节点文件失败: {e}")
                raise
    
    def filter_nodes_by_region(self, nodes: list, filter_key: str) -> list:
        """根据地区过滤器筛选节点"""
        if not filter_key:
            return nodes
        
        pattern = FILTER_PATTERNS.get(filter_key)
        if not pattern:
            self.logger.warning(f"未知的过滤器 '{filter_key}'，跳过。")
            return []
        
        filtered_nodes = [node for node in nodes if pattern.search(node.get('name', ''))]
        self.logger.info(f"地区过滤器 '{filter_key}' 筛选出 {len(filtered_nodes)} 个节点")
        return filtered_nodes
    
    def generate_config_from_template(self, base_config: dict, proxies_list: list, output_path: str) -> None:
        """根据基础配置和传入的代理列表生成最终的 Clash 配置文件"""
        try:
            # 直接使用基础配置的深拷贝，避免互相影响
            config = yaml.safe_load(yaml.safe_dump(base_config))
            config['proxies'] = proxies_list
            
            self.logger.info(f"为 {output_path} 分配了 {len(proxies_list)} 个节点。")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                
            self.logger.info(f"成功生成配置文件: {output_path}")
            
        except Exception as e:
            self.logger.error(f"生成配置文件 '{output_path}' 时发生未知错误: {e}", exc_info=True)
            raise
    
    def generate_all_configs(self, all_nodes: list) -> list:
        """生成所有配置文件"""
        generated_files = []
        
        for config_info in CONFIGS_TO_GENERATE:
            filter_key = config_info.get("filter")
            output_path = config_info.get("output")
            template_name = config_info.get("template")
            
            # 根据地区过滤器筛选节点
            filtered_proxies = self.filter_nodes_by_region(all_nodes, filter_key)
            
            if not filtered_proxies and filter_key:
                self.logger.warning(f"地区 '{filter_key}' 没有可用节点，跳过生成 {output_path}")
                continue
            
            # 生成配置文件
            self.generate_config_from_template(
                base_config=self.templates[template_name],
                proxies_list=filtered_proxies,
                output_path=output_path
            )
            generated_files.append(output_path)
        
        return generated_files
    
    def output_to_github_actions(self, generated_files: list) -> None:
        """输出产物清单到 GitHub Actions"""
        if 'GITHUB_OUTPUT' in os.environ:
            self.logger.info("正在将产物清单输出到 GitHub Actions...")
            try:
                with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                    print(f"generated_files={' '.join(generated_files)}", file=f)
                self.logger.info("成功输出到 GitHub Actions")
            except Exception as e:
                self.logger.error(f"输出到 GitHub Actions 失败: {e}")
    
    def run(self, pre_tested_nodes_file: str = None) -> None:
        """主执行函数"""
        try:
            # 加载模板文件
            self.load_templates()
            
            # 加载健康节点
            all_nodes = self.load_healthy_nodes(pre_tested_nodes_file)
            
            if not all_nodes:
                self.logger.error("没有可用的节点，退出程序")
                sys.exit(1)
            
            # 生成所有配置文件
            generated_files = self.generate_all_configs(all_nodes)
            
            # 输出到 GitHub Actions
            self.output_to_github_actions(generated_files)
            
            self.logger.info("🎉 所有任务已成功完成！")
            
        except Exception as e:
            self.logger.error(f"程序执行失败: {e}", exc_info=True)
            sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生成 Clash 配置文件。")
    parser.add_argument(
        '--use-pre-tested-nodes',
        type=str,
        help='指定一个包含预先测试好的节点的YAML文件，脚本将直接使用这些节点进行分发生成。'
    )
    
    args = parser.parse_args()
    
    generator = ConfigGenerator()
    generator.run(args.use_pre_tested_nodes)


if __name__ == "__main__":
    main()