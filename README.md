
# Clash Config Auto Builder

[![Generate Clash Config](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml/badge.svg)](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml)

这是一个通过 GitHub Actions 自动定时抓取、合并、去重 Clash 代理订阅，并生成最终配置文件的项目。

## ✨ 项目特性

- **极致简约**: 只维护一个极简的配置文件模板，逻辑清晰，易于管理。
- **全自动化**: 无需人工干预，定时更新配置文件。
- **多版本生成**: 同时生成 `全部节点` 和多个 `地区限定节点` 版本的配置文件。
- **智能去重与过滤**: 自动识别并移除重复的代理节点，并可按地区关键词过滤。
- **自动发布**: 每次更新后，自动将最新的配置文件发布到 GitHub Release，方便下载。
- **CDN 刷新**: 自动刷新 jsDelivr 的 CDN 缓存，确保通过链接访问的是最新版本。

## 🚀 最终效果

本项目会生成多个配置文件，它们的**代理组结构完全相同**，区别仅在于包含的**代理节点列表**不同：

- `config/config.yaml`: 包含**所有**代理节点，适用于标准 Clash 客户端。
- `config/stash.yaml`: 包含**所有**代理节点，但配置针对 Stash 客户端进行了优化（如移除 external-ui）。
- `config/config_hk.yaml`: **仅包含**香港地区节点。
- `config/config_us.yaml`: **仅包含**美国地区节点。
- ... 以此类推。

## 🔧 如何使用与自定义

### 1. 修改核心模板

所有配置的“源头”都统一到了根目录下的 `config-template.yaml` 文件。你需要修改 DNS、规则、代理组等，**只需要修改这一个文件**即可。

### 2. 管理节点过滤规则

打开 `scripts/merge_proxies.py` 文件：
- **地区白名单**: 在 `FILTER_PATTERNS` 字典中添加或修改地区的正则表达式。
- **关键词黑名单**: 在 `BLACKLIST_KEYWORDS` 列表中添加不希望在全局配置中出现的词语。

### 3. 管理输出版本 (唯一的真相来源)

项目的核心控制逻辑位于 `scripts/generate_config.py` 文件顶部的 `configs_to_generate` 列表。这个列表是**唯一的真相来源**，它决定了整个项目需要生成哪些版本的配置文件。

```python
# scripts/generate_config.py

configs_to_generate = [
    # ...
    # 示例：增加一个“台湾”地区的配置
    {
        "filter": "tw", # 对应 merge_proxies.py 中的过滤器名称
        "proxies_file": "merged-proxies_tw.yaml", # 生成的临时节点数据文件名
        "output": "config/config_tw.yaml" # 最终输出的配置文件路径
    },
    # ...
]
```

要新增或删除一个版本，你只需要修改 `merge_proxies.py` 的 `FILTER_PATTERNS` 和 `generate_config.py` 的 `configs_to_generate` 列表即可。**无需再关心任何其他文件**。

### 4. 添加订阅链接

- 进入你 Fork 后的仓库，点击 `Settings` -> `Secrets and variables` -> `Actions`。
- 在 `Repository variables` 部分，点击 `New repository variable`。
- 创建一个名为 `URL_LIST` 的变量，将你的所有 Clash 订阅链接粘贴进去，**注意：多个链接之间必须用空格分隔**。
