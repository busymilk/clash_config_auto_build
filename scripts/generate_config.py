import yaml

# 读取基础配置模板
with open("config-template.yaml", 'r', encoding="utf-8") as f:
    base_config = yaml.safe_load(f)

# 读取合并后的proxies
with open("merged-proxies.yaml", 'r',encoding="utf-8") as f:
    merged_proxies = yaml.safe_load(f)

# 合并配置
base_config['proxies'] = merged_proxies.get('proxies', [])

# 写入最终配置
with open("config/config.yaml", 'w', encoding="utf-8") as f:
    yaml.dump(base_config, f, default_flow_style=False, allow_unicode=True)


#hk------------------------------------------------------------------------------

# 读取基础配置模板
with open("config-template_hk.yaml", 'r', encoding="utf-8") as f:
    base_config = yaml.safe_load(f)

# 读取合并后的proxies
with open("merged-proxies_hk.yaml", 'r',encoding="utf-8") as f:
    merged_proxies = yaml.safe_load(f)

# 合并配置
base_config['proxies'] = merged_proxies.get('proxies', [])

# 写入最终配置
with open("config/config_hk.yaml", 'w', encoding="utf-8") as f:
    yaml.dump(base_config, f, default_flow_style=False, allow_unicode=True)

#us------------------------------------------------------------------------------

# 读取基础配置模板
with open("config-template_us.yaml", 'r', encoding="utf-8") as f:
    base_config = yaml.safe_load(f)

# 读取合并后的proxies
with open("merged-proxies_us.yaml", 'r',encoding="utf-8") as f:
    merged_proxies = yaml.safe_load(f)

# 合并配置
base_config['proxies'] = merged_proxies.get('proxies', [])

# 写入最终配置
with open("config/config_us.yaml", 'w', encoding="utf-8") as f:
    yaml.dump(base_config, f, default_flow_style=False, allow_unicode=True)
