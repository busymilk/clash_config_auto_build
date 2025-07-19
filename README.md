
# Clash Config Auto Builder

[![Generate Clash Config](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml/badge.svg)](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml)

这是一个通过 GitHub Actions 自动抓取、合并、去重、测试并生成高可用 Clash 配置文件的项目。

## ✨ 项目特性

- **增量更新与状态保持**: 每次运行都会自动拉取上一次发布的健康节点，与本次从订阅源获取的新节点合并。这确保了节点的稳定积累，即使订阅链接临时失效，也能保证配置文件的可用性。
- **全自动化**: 无需人工干预，定时更新配置文件，始终保持最佳状态。
- **强制地理位置检测**: 所有通过延迟测试的节点都将强制进行地理位置检测，并根据检测结果重命名。
- **高效测试流程**:
    1.  **智能合并**: 将所有订阅源的节点与**上一次的健康节点**合并并去重，形成一个“母列表”。在合并过程中，会自动过滤掉端口格式不正确的代理节点。
    2.  **集中测试**: 只对“母列表”进行一次严格的健康检查（延迟测试）。
    3.  **健康节点筛选与 Mihomo 重启**: 延迟测试后，会生成一个只包含健康节点的新 Mihomo 配置，并用此配置重启 Mihomo 核心，确保后续地理位置检测的效率和准确性。
    4.  **地理位置检测**: 使用 Mihomo 的 `content_check` API 对健康节点进行地理位置检测。
    5.  **分发生成**: 使用经过完整测试和地理位置重命名的“精华节点”列表，生成所有最终的配置文件。
- **多版本生成**: 同时生成 `全部节点` 和多个 `地区限定节点` 版本的配置文件。
- **双模板支持**: 支持标准 Clash 客户端 (`config-template.yaml`) 和 Stash (`stash-template.yaml`)。
- **自动发布与刷新**: 每次更新后，自动将最新的配置文件发布到 GitHub Release，并刷新 jsDelivr 的 CDN 缓存。

## 🚀 最终效果

本项目会生成多个配置文件，所有文件的**代理组结构都由其使用的模板决定**，区别仅在于包含的**代理节点列表**不同。

### 节点命名规则

节点名称将遵循以下格式：`[Emoji] [国家名称]-[城市名称] ([唯一标识符])`。例如：`🇺🇸 美国-纽约 (abc123)`。

如果无法获取地理位置信息，节点名称将以 `未知 ([唯一标识符])` 开头。例如：`未知 (def456)`。

### 标准 Clash 版本 (使用 `config-template.yaml`)
- `config/config.yaml`: 包含**所有**通过测试的健康节点。
- `config/config_hk.yaml`: **仅包含**香港地区的健康节点。
- `config/config_us.yaml`: **仅包含**美国地区的健康节点。
- ... 以此类推。

### Stash 专用版本 (使用 `stash-template.yaml`)
- `config/stash.yaml`: 包含**所有**健康节点，配置针对 Stash 优化。
- `config/stash_hk.yaml`: **仅包含**香港地区的健康节点，配置针对 Stash 优化。
- `config/stash_us.yaml`: **仅包含**美国地区的健康节点，配置针对 Stash 优化。
- ... 以此类推.

## 🔧 如何使用与自定义

### 1. 修改核心模板文件

项目现在有两个核心模板文件，分别对应不同的客户端：

- **`config-template.yaml`**: 用于所有**标准 Clash**客户端。
- **`stash-template.yaml`**: 专为 **Stash** 客户端优化，包含一些专属配置。

如果你需要修改通用配置（如 DNS、路由规则等），请根据你的需要，修改对应的模板文件。如果希望两边都生效，则需要**同时修改这两个文件**。

### 2. 管理输出版本 (唯一的真相来源)

项目的核心控制逻辑位于 `scripts/generate_config.py` 文件中的 `CONFIGS_TO_GENERATE` 列表。这个列表是**唯一的真相来源**，它决定了整个项目需要生成哪些版本的配置文件。

```python
# core/constants.py

CONFIGS_TO_GENERATE = [
    # ...
    # 示例：增加一个“台湾”地区的 Stash 配置
    {
        "filter": "tw", # 对应 FILTER_PATTERNS 中的过滤器名称
        "output": "config/stash_tw.yaml",
        "template": "stash-template.yaml" # 指定使用的模板
    },
    # ...
]
```

### 3. 修改代理下载目录 (可选)

如果你想修改存放订阅文件的目录名称（默认为 `external_proxies`），你只需要修改 `.github/workflows/clash-config.yml` 文件顶部 `env` 部分的 `PROXY_DIR` 变量即可。整个流程会自动适应这个新名称。

### 4. 添加订阅链接

- 进入你 Fork 后的仓库，点击 `Settings` -> `Secrets and variables` -> `Actions`。
- 在 `Repository variables` 部分，点击 `New repository variable`。
- 创建一个名为 `URL_LIST` 的变量，将你的所有 Clash 订阅链接粘贴进去，**注意：多个链接之间必须用空格分隔**。

### 5. 配置环境变量 (可选)

项目支持通过环境变量调整运行参数，无需修改代码。你可以在 `.github/workflows/clash-config.yml` 文件的 `env` 部分修改这些变量：

```yaml
env:
  # 代理下载目录
  PROXY_DIR: external_proxies
  # 最大可接受延迟 (毫秒)
  DELAY_LIMIT: "4000"
  # 并发测试线程数
  MAX_WORKERS: "100"
  # 日志级别 (INFO, DEBUG, WARNING, ERROR)
  LOG_LEVEL: "INFO"
  # 地理位置检测超时时间 (秒)
  GEOIP_TIMEOUT: "20"
```
