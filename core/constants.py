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
    'hk': re.compile(
        r'\b(HK|Hong[\s_-]?Kong|HKG|HGC)\b|香港|🇭🇰',
        flags=re.IGNORECASE
    ),
    'us': re.compile(
        r'\b(us|usa|america|united[\s-]?states)\b|美国|🇺🇸',
        flags=re.IGNORECASE
    ),
    'jp': re.compile(
        r'\b(jp|japan|tokyo|tyo|osaka|nippon)\b|日本|🇯🇵',
        flags=re.IGNORECASE
    ),
    'uk': re.compile(
        r'\b(uk|england|britain|united[\s-]?kingdom)\b|英国|🇬🇧',
        flags=re.IGNORECASE
    ),
    'sg': re.compile(
        r'\b(sg|singapore|sin)\b|新加坡|🇸🇬',
        flags=re.IGNORECASE
    ),
    'tw': re.compile(
        r'\b(tw|taiwan|taipei|tpe)\b|台湾|🇹🇼',
        flags=re.IGNORECASE
    ),
    'kr': re.compile(
        r'\b(kr|korea|seoul|kor)\b|韩国|🇰🇷',
        flags=re.IGNORECASE
    ),
    'de': re.compile(
        r'\b(de|germany|berlin|frankfurt)\b|德国|🇩🇪',
        flags=re.IGNORECASE
    ),
    'ca': re.compile(
        r'\b(ca|canada|toronto|vancouver)\b|加拿大|🇨🇦',
        flags=re.IGNORECASE
    ),
    'au': re.compile(
        r'\b(au|australia|sydney|melbourne)\b|澳大利亚|🇦🇺',
        flags=re.IGNORECASE
    ),
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
    DEFAULT_DELAY_LIMIT = int(os.getenv('DELAY_LIMIT', '4000'))
    
    # API超时 (ms)
    DEFAULT_TIMEOUT = int(os.getenv('API_TIMEOUT', '6000'))
    
    # 并发线程数
    DEFAULT_MAX_WORKERS = int(os.getenv('MAX_WORKERS', '100'))
    
    # mihomo版本
    MIHOMO_VERSION = os.getenv('MIHOMO_VERSION', 'v1.19.11')
    
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
    STASH_TEMPLATE = "stash-template.yaml"
    
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
    
    # Stash 专用配置
    {"filter": None, "output": "config/stash.yaml", "template": "stash-template.yaml"},
    {"filter": "hk", "output": "config/stash_hk.yaml", "template": "stash-template.yaml"},
    {"filter": "us", "output": "config/stash_us.yaml", "template": "stash-template.yaml"},
    {"filter": "jp", "output": "config/stash_jp.yaml", "template": "stash-template.yaml"},
    {"filter": "uk", "output": "config/stash_uk.yaml", "template": "stash-template.yaml"},
    {"filter": "sg", "output": "config/stash_sg.yaml", "template": "stash-template.yaml"},
    {"filter": "tw", "output": "config/stash_tw.yaml", "template": "stash-template.yaml"},
    {"filter": "kr", "output": "config/stash_kr.yaml", "template": "stash-template.yaml"},
    {"filter": "de", "output": "config/stash_de.yaml", "template": "stash-template.yaml"},
    {"filter": "ca", "output": "config/stash_ca.yaml", "template": "stash-template.yaml"},
    {"filter": "au", "output": "config/stash_au.yaml", "template": "stash-template.yaml"}
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