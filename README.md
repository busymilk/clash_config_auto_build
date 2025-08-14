# Clash Config Auto Builder

[![Generate Clash Config](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml/badge.svg)](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml)

这是一个通过 GitHub Actions 自动抓取、合并、去重、测试并生成高可用 Clash 配置文件的项目。

## ✨ 项目特性

- **健壮的并发域名解析**: 在流程的最前端，通过调用外部DNS工具 `q`，高速地将所有节点的 `server` 字段（如果它是域名）解析为纯IP地址（优先使用IPv6）。该过程能够正确处理 `CNAME` 记录，并支持通过 `ECS` 获取最优CDN节点，彻底杜绝了DNS相关的所有问题。
- **智能去重**: 独创的 `server_url` 标记机制。在解析域名前，会先将原始域名保存到 `server_url` 字段。后续的节点去重将基于这个原始域名进行，完美解决了因CDN等技术导致同一域名解析到不同IP时，被误判为重复节点的问题。
- **增量更新与状态保持**: 每次运行都会自动拉取上一次发布的健康节点，与本次从订阅源获取的新节点合并。这确保了节点的稳定积累，即使订阅链接临时失效，也能保证配置文件的可用性。
- **全自动化**: 无需人工干预，定时更新配置文件，始终保持最佳状态。
- **强大的地区过滤**: 地区过滤规则经过优化，能够精确匹配节点名称中的**中文、英文全称、双字母缩写 (如 US, HK) 及常见别名**，确保在不重命名的情况下也能准确分类。
- **高效的【两阶段】测试流程**: 
    1.  **智能合并与解析**: 将所有订阅源的节点与**上一次的健康节点**合并，并完成域名到IP的转换和智能去重。
    2.  **第一阶段：连通性与延迟初筛**: 使用轻量级的 HTTP 请求，快速测试所有节点的**基本连通性**和**响应延迟**。
    3.  **第二阶段：TLS 握手能力精选**: 对通过了第一阶段测试的节点，进一步进行严格的 **TLS 握手测试**（通过 `openssl s_client` 模拟与高安全域名如谷歌API的连接），确保节点具备与现代高安全网站进行稳定加密通信的能力。
    4.  **架构支撑**: 整个测试流程在一个高性能的**多进程“工作池”**上并行执行，每个测试都拥有独立的运行环境，确保了测试的速度和结果的准确性。
    5.  **分发生成**: 仅使用通过了**全部两轮测试**的“高可用、高信赖”节点列表，根据优化后的地区规则，生成所有最终的配置文件。
- **自动发布与刷新**: 每次更新后，自动将最新的配置文件发布到 GitHub Release，并刷新 jsDelivr 的 CDN 缓存。

## 🚀 最终效果

本项目会生成多个配置文件，所有文件的**代理组结构都由其使用的模板决定**，区别仅在于包含的**代理节点列表**不同。

### 节点命名规则

节点将**保留其在原始订阅链接中的名称**。

项目通过优化后的正则表达式（匹配中文、英文、地区缩写等）对这些原始名称进行地区分类，以生成地区限定版本的配置文件。

### 标准 Clash 版本 (使用 `config-template.yaml`)
- `config/config.yaml`: 包含**所有**通过测试的健康节点。
- `config/config_hk.yaml`: **仅包含**香港地区的健康节点。
- `config/config_us.yaml`: **仅包含**美国地区的健康节点。
- ... 以此类推。

## 部署到 Vercel (提供受密码保护的订阅链接)

除了通过 GitHub Release 下载，你还可以将此项目部署到 Vercel，以获得一个私有的、受密码保护的订阅链接，方便在国内直接访问。

### 工作原理

我们利用 Vercel 的边缘函数 (`api/[file].ts`) 拦截所有对 `.yaml` 文件的请求。该函数会验证 URL 中是否包含正确的访问令牌 (`token`)。

- **验证通过**: 返回 `config` 目录中对应的 YAML 文件内容。
- **验证失败**: 返回 `401 Unauthorized` 错误，保护你的配置文件不被泄露。

### 设置步骤

1.  **Fork 本仓库**

2.  **登录 Vercel**
    使用你的 GitHub 账号登录 Vercel。

3.  **导入项目 (Import Project)**
    - 在 Vercel Dashboard 点击 `Add New...` -> `Project`。
    - 选择你 Fork 的 GitHub 仓库并点击 `Import`。

4.  **配置项目**
    - **Framework Preset**: Vercel 应该会自动识别为 `Other`。保持默认即可。
    - **Environment Variables (重要)**: 
        - 展开 `Environment Variables` 部分。
        - 添加一个新变量：
            - **Name**: `ACCESS_TOKEN`
            - **Value**: 设置一个你自己才知道的强密码/令牌。例如，你可以使用一个 UUID 或者其他随机字符串，如 `a9b8c7d6-e5f4-g3h2-i1j0-k9l8m7n6o5p4`。

5.  **部署 (Deploy)**
    - 点击 `Deploy` 按钮并等待部署完成。

### 如何使用

部署成功后，你的订阅链接格式如下：

```
https://<你的Vercel项目名>.vercel.app/<配置文件名>.yaml?token=<你设置的ACCESS_TOKEN>
```

**示例**:
假如你的 Vercel 项目名是 `my-clash-config`，你想获取美国地区的配置，并且你的 `ACCESS_TOKEN` 设置为 `MySuperSecretPassword123`，那么你的链接将是：

```
https://my-clash-config.vercel.app/config_us.yaml?token=MySuperSecretPassword123
```

将此链接填入你的 Clash 客户端即可。

## 🔧 如何使用与自定义

### 1. 修改核心模板文件

项目现在只有一个核心模板文件：

- **`config-template.yaml`**: 用于所有**标准 Clash**客户端。

如果你需要修改通用配置（如 DNS、路由规则等），请直接修改此文件。

### 2. 管理输出版本 (唯一的真相来源)

项目的核心控制逻辑位于 `core/constants.py` 文件中的 `CONFIGS_TO_GENERATE` 列表。这个列表是**唯一的真相来源**，它决定了整个项目需要生成哪些版本的配置文件。

```python
# core/constants.py

CONFIGS_TO_GENERATE = [
    # ...
    # 示例：增加一个“台湾”地区的 Clash 配置
    {
        "filter": "tw", # 对应 FILTER_PATTERNS 中的过滤器名称
        "output": "config/config_tw.yaml",
        "template": "config-template.yaml" # 指定使用的模板
    },
    # ...
]
```

### 3. 配置DNS解析 (可选)

本项目允许你精细化控制域名解析的行为，以获取最优的CDN节点IP。所有相关配置都在 `core/constants.py` 文件中的 `DnsConfig` 类里：

```python
# core/constants.py

class DnsConfig:
    # 自定义DNS服务器列表。如果为空列表，则使用系统默认配置。
    CUSTOM_DNS_SERVERS = ['8.8.8.8', '1.1.1.1']

    # 用于 EDNS 客户端子网 (ECS) 的IP地址。留空字符串则禁用ECS。
    # 这可以模拟从指定地区发起DNS查询，以获得地理位置更优的IP。
    ECS_IP = '114.114.114.114'
```

### 4. 添加订阅链接

- 进入你 Fork 后的仓库，点击 `Settings` -> `Secrets and variables` -> `Actions`。
- 在 `Repository variables` 部分，点击 `New repository variable`。
- 创建一个名为 `URL_LIST` 的变量，将你的所有 Clash 订阅链接粘贴进去，**注意：多个链接之间必须用空格分隔**。

### 5. 高级配置 (命令行与环境变量)

测试脚本 (`scripts/node_tester_integrated.py`) 支持通过命令行参数或环境变量进行详细配置，这在本地调试或自定义 CI 流程时非常有用。

配置加载的优先级为：**命令行参数 > 环境变量 > 代码内默认值**。

| 命令行参数 | 环境变量 | 说明 |
| :--- | :--- | :--- |
| `--input-file` | `ALL_PROXIES_FILE` | 包含所有待测节点的输入文件路径 |
| `--output-file` | `HEALTHY_PROXIES_FILE` | 用于保存健康节点的输出文件路径 |
| `--clash-path` | `MIHOMO_PATH` | `mihomo` 可执行文件的路径 |
| `--max-workers` | `MAX_WORKERS` | 并发测试的最大工作进程数 |
| `--delay-limit` | `DELAY_LIMIT` | 延迟测试的上限（毫秒） |
| `--latency-test-url` | `LATENCY_TEST_URL` | 延迟测试使用的 URL |
| `--handshake-host` | `HANDSHAKE_TEST_HOST`| TLS 握手测试使用的目标主机 |
| `--log-level` | `LOG_LEVEL` | 日志级别 (DEBUG, INFO, WARNING, ERROR) |