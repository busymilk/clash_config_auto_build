import yaml
import os
import glob

proxies = []
seen = set()

# 处理所有下载的代理文件
for file in glob.glob("external_proxies/*.yaml"):
    try:
        with open(file, 'r') as f:
            data = yaml.safe_load(f)
            if data and 'proxies' in data:
                for proxy in data['proxies']:
                    # 使用name作为唯一标识
                    name = proxy.get('name')
                    if name and name not in seen:
                        seen.add(name)
                        proxies.append(proxy)
    except Exception as e:
        print(f"Error processing {file}: {e}")

# 保存合并后的proxies
with open("merged-proxies.yaml", 'w') as f:
    yaml.dump({'proxies': proxies}, f, default_flow_style=False)
