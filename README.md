# Clash Config Auto Builder

[![Generate Clash Config](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml/badge.svg)](https://github.com/busymilk/clash_config_auto_build/actions/workflows/clash-config.yml)

这是一个通过 GitHub Actions 自动定时抓取、合并、去重 Clash 代理订阅，并生成最终配置文件的项目。

## ✨ 项目特性

- **全自动化**: 无需人工干预，定时更新配置文件。
- **定时执行**: 默认每4小时自动运行一次，确保节点信息保持最新。
- **多版本生成**: 同时生成 `全部节点`、`香港节点`、`美国节点` 三个版本的配置文件。
- **智能去重**: 自动识别并移除重复的代理节点，保持配置清爽。
- **灵活过滤**: 支持按地区关键词（如 `HK`, `US`）过滤，也支持按名称关键词（如 `免费`）排除。
- **自动发布**: 每次更新后，自动将最新的配置文件发布到 GitHub Release，方便下载。
- **CDN 刷新**: 自动刷新 jsDelivr 的 CDN 缓存，确保通过链接访问的是最新版本。
- **高可定制**: 可以轻松修改配置模板、过滤规则和订阅列表。

## 🚀 如何使用

1.  **Fork 本仓库**
    点击页面右上角的 `Fork` 按钮，将此项目复制到你自己的 GitHub 账户下。

2.  **添加订阅链接**
    - 进入你 Fork 后的仓库，点击 `Settings` -> `Secrets and variables` -> `Actions`。
    - 在 `Repository variables` 部分，点击 `New repository variable`。
    - 创建一个名为 `URL_LIST` 的变量，将你的所有 Clash 订阅链接粘贴进去，**注意：多个链接之间必须用空格分隔**。

3.  **触发运行**
    - **自动触发**: 完成以上步骤后，GitHub Actions 会根据预设的 `cron` 表达式（默认为每4小时）自动运行。
    - **手动触发**: 如果想立即生成配置文件，可以进入仓库的 `Actions` 标签页，选择 `Generate Clash Config` 工作流程，然后点击 `Run workflow` 手动触发。

4.  **获取配置文件**
    - **从 Release 下载**: 推荐方式。工作流程运行成功后，会自动创建一个名为 `latest-config` 的 Release，你可以在其中找到并下载所有版本的配置文件。
    - **从仓库文件查看**: 配置文件会保存在仓库的 `config/` 目录下，你可以直接查看或使用文件的 Raw 链接。
    - **通过 jsDelivr 访问**: 你也可以通过 jsDelivr 的 CDN 链接来使用配置文件，例如:
      ```
      https://cdn.jsdelivr.net/gh/你的用户名/clash_config_auto_build@main/config/config.yaml
      ```

## 🔧 自定义配置

- **基础配置**:
  直接修改根目录下的 `config-template.yaml`, `config-template_hk.yaml`, `config-template_us.yaml` 文件，可以调整 Clash 的基础设置（如 DNS, 代理组, 规则等）。

- **节点过滤规则**:
  如果需要增加新的地区过滤或修改关键词，可以编辑 `scripts/merge_proxies.py` 文件：
  - **地区白名单**: 在 `FILTER_PATTERNS` 字典中添加新的正则表达式。
  - **关键词黑名单**: 在 `BLACKLIST_KEYWORDS` 列表中添加不希望出现的词语。

- **生成不同版本**:
  如果需要生成更多或更少版本的配置文件，可以编辑 `scripts/generate_config.py` 文件中的 `configs_to_generate` 列表。