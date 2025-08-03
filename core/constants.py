# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 统一配置常量
集中管理所有配置常量，避免重复定义和硬编码
"""

import re
import os

# =============================================================================
# 地区过滤器配置
# =============================================================================
FILTER_PATTERNS = {
    # 增加 \b 单词边界确保精确匹配，并补充英文全称、别称和原生语言名称
    'hk': re.compile(r'香港|🇭🇰|\bHK\b|Hong Kong', flags=re.IGNORECASE),
    'us': re.compile(r'美国|🇺🇸|\bUS\b|\bUSA\b|United States', flags=re.IGNORECASE),
    'jp': re.compile(r'日本|🇯🇵|\bJP\b|Japan', flags=re.IGNORECASE),
    'uk': re.compile(r'英国|🇬🇧|\bUK\b|\bGB\b|United Kingdom|England', flags=re.IGNORECASE),
    'sg': re.compile(r'新加坡|🇸🇬|\bSG\b|Singapore', flags=re.IGNORECASE),
    'tw': re.compile(r'台湾|🇹🇼|\bTW\b|Taiwan', flags=re.IGNORECASE),
    'kr': re.compile(r'韩国|🇰🇷|\bKR\b|Korea|South Korea', flags=re.IGNORECASE),
    'de': re.compile(r'德国|🇩🇪|\bDE\b|Germany|Deutschland', flags=re.IGNORECASE),
    'ca': re.compile(r'加拿大|🇨🇦|\bCA\b|Canada', flags=re.IGNORECASE),
    'au': re.compile(r'澳大利亚|🇦🇺|\bAU\b|Australia', flags=re.IGNORECASE),
}

# =============================================================================
# 黑名单配置
# =============================================================================
BLACKLIST_KEYWORDS = [
    '日期', '免费', '关注', '回国', 'CN', 'China', '中国'
]

# =============================================================================
# 节点测试配置
# =============================================================================
class NodeTestConfig:
    # 默认测试URL
    DEFAULT_TEST_URL = "https://www.google.com/generate_204"
    
    # 延迟限制 (ms)
    DEFAULT_DELAY_LIMIT = int(os.getenv('DELAY_LIMIT', '3000'))
    
    # API超时 (ms)
    DEFAULT_TIMEOUT = int(os.getenv('API_TIMEOUT', '4000'))
    
    # 并发线程数
    DEFAULT_MAX_WORKERS = int(os.getenv('MAX_WORKERS', '100'))
    
    # 测试配置文件名
    TEST_CONFIG_FILE = "config_for_test.yaml"

# =============================================================================
# 文件路径配置
# =============================================================================
class PathConfig:
    # 代理下载目录
    PROXY_DIR = os.getenv('PROXY_DIR', 'external_proxies')
    
    # 配置输出目录
    CONFIG_DIR = "config"
    
    # 模板文件
    CONFIG_TEMPLATE = "config-template.yaml"
    
    # 临时文件
    TEMP_MERGED_FILE = "all_merged_nodes.yaml"
    HEALTHY_NODES_FILE = "healthy_nodes_list.yaml"

# =============================================================================
# 配置生成规则
# =============================================================================
CONFIGS_TO_GENERATE = [
    # 标准 Clash 配置
    {"filter": None, "output": "config/config.yaml", "template": "config-template.yaml"},
    {"filter": "hk", "output": "config/config_hk.yaml", "template": "config-template.yaml"},
    {"filter": "us", "output": "config/config_us.yaml", "template": "config-template.yaml"},
    {"filter": "jp", "output": "config/config_jp.yaml", "template": "config-template.yaml"},
    {"filter": "uk", "output": "config/config_uk.yaml", "template": "config-template.yaml"},
    {"filter": "sg", "output": "config/config_sg.yaml", "template": "config-template.yaml"},
    {"filter": "tw", "output": "config/config_tw.yaml", "template": "config-template.yaml"},
    {"filter": "kr", "output": "config/config_kr.yaml", "template": "config-template.yaml"},
    {"filter": "de", "output": "config/config_de.yaml", "template": "config-template.yaml"},
    {"filter": "ca", "output": "config/config_ca.yaml", "template": "config-template.yaml"},
    {"filter": "au", "output": "config/config_au.yaml", "template": "config-template.yaml"},
]

# =============================================================================
# GitHub Actions 配置
# =============================================================================
class GitHubConfig:
    # CDN缓存刷新配置
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY = int(os.getenv('RETRY_DELAY', '20'))
    
    # jsDelivr CDN URL模板
    JSDELIVR_PURGE_URL = "https://purge.jsdelivr.net/gh/{repository}@main/{file}"

# =============================================================================
# 日志配置
# =============================================================================
class LogConfig:
    # 日志格式
    FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    
    # 日志级别
    LEVEL = os.getenv('LOG_LEVEL', 'INFO')
