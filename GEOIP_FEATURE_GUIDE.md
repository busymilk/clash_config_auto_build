# 🌍 地理位置检测功能使用指南

## 📋 功能概述

新增的地理位置检测功能可以：
1. **自动检测节点出口IP** - 通过代理获取真实的出口IP地址
2. **精确识别地理位置** - 使用多个GeoIP服务确保准确性
3. **智能重命名节点** - 根据实际地理位置重新命名节点
4. **扩展地区支持** - 新增台湾、韩国、德国、加拿大、澳大利亚等地区

## 🚀 使用方法

### 1. 基础使用 (仅延迟测试)
```bash
# 传统模式：只测试延迟，不检测地理位置
python scripts/node_tester_with_geoip.py \
  --input-file all_unique_nodes.yaml \
  --output healthy_nodes_list.yaml \
  --clash-path /usr/local/bin/mihomo
```

### 2. 启用地理位置检测
```bash
# 完整模式：延迟测试 + 地理位置检测 + 节点重命名
python scripts/node_tester_with_geoip.py \
  --input-file all_unique_nodes.yaml \
  --output healthy_nodes_list.yaml \
  --clash-path /usr/local/bin/mihomo \
  --enable-geoip \
  --geoip-workers 5 \
  --geoip-timeout 20 \
  --save-geoip-details
```

### 3. 参数说明

#### 基础参数
- `--input-file`: 输入的节点配置文件
- `--output-file`: 输出的健康节点文件
- `--clash-path`: mihomo 可执行文件路径

#### 延迟测试参数
- `--test-url`: 测试URL (默认: Google 204)
- `--delay-limit`: 最大延迟限制 (默认: 4000ms)
- `--timeout`: 请求超时时间 (默认: 6000ms)
- `--max-workers`: 延迟测试并发数 (默认: 100)

#### 地理位置检测参数
- `--enable-geoip`: 启用地理位置检测 (默认: 关闭)
- `--geoip-workers`: 地理位置检测并发数 (默认: 5)
- `--geoip-timeout`: 地理位置检测超时 (默认: 20秒)
- `--save-geoip-details`: 保存详细的地理位置信息

## 🌏 支持的地区

### 原有地区 (5个)
- 🇭🇰 **香港** (HK) - Hong Kong
- 🇺🇸 **美国** (US) - United States  
- 🇯🇵 **日本** (JP) - Japan
- 🇬🇧 **英国** (UK) - United Kingdom
- 🇸🇬 **新加坡** (SG) - Singapore

### 新增地区 (5个)
- 🇹🇼 **台湾** (TW) - Taiwan
- 🇰🇷 **韩国** (KR) - Korea
- 🇩🇪 **德国** (DE) - Germany
- 🇨🇦 **加拿大** (CA) - Canada
- 🇦🇺 **澳大利亚** (AU) - Australia

### 扩展支持 (更多地区)
GeoIP检测器还支持识别更多地区：
- 🇫🇷 法国、🇳🇱 荷兰、🇷🇺 俄罗斯、🇮🇳 印度
- 🇹🇭 泰国、🇲🇾 马来西亚、🇵🇭 菲律宾、🇻🇳 越南
- 🇮🇩 印尼、🇹🇷 土耳其、🇦🇷 阿根廷、🇧🇷 巴西

## 📊 工作流程

### 第一阶段：延迟测试
```
输入节点 → mihomo启动 → 并发延迟测试 → 筛选健康节点
```

### 第二阶段：地理位置检测 (可选)
```
健康节点 → 切换代理 → 获取出口IP → GeoIP查询 → 重新命名
```

## 🔍 节点重命名规则

### 重命名前
```
- "Relay_🇭🇰HK-🇭🇰HK_123"
- "US-Premium-01"  
- "Japan-Tokyo-Fast"
- "免费节点-香港"
```

### 重命名后
```
- "🇭🇰 香港 Relay_123"
- "🇺🇸 美国 Premium-01"
- "🇯🇵 日本-东京 Fast"  
- "🇭🇰 香港 节点"
```

### 命名规则
1. **地区标识**: `🇭🇰 香港` (emoji + 中文名称)
2. **城市信息**: `🇯🇵 日本-东京` (包含城市时)
3. **原始信息**: 保留清理后的原始节点信息
4. **智能清理**: 自动移除原名称中的重复地区标识

## 🛠️ 技术实现

### GeoIP服务
使用多个GeoIP服务提供冗余：
1. **ipapi.co** - 主要服务
2. **ip-api.com** - 备用服务  
3. **ipinfo.io** - 备用服务

### 出口IP检测
通过多个IP检测服务获取出口IP：
1. **api.ipify.org**
2. **ifconfig.me/ip**
3. **icanhazip.com**
4. **ipecho.net/plain**

### 容错机制
- 服务失败自动切换到备用服务
- 网络超时自动重试
- 检测失败保持原始节点名称

## 📈 性能优化

### 并发控制
- 延迟测试：默认100并发
- 地理位置检测：默认5并发 (避免API限制)

### 超时设置
- 延迟测试：6秒超时
- 地理位置检测：20秒超时
- 代理切换：2秒等待

### 进度报告
- 每100个节点报告延迟测试进度
- 每20个节点报告地理位置检测进度

## 🔧 集成到 GitHub Actions

### 更新 workflow 文件
```yaml
# 在 .github/workflows/clash-config.yml 中
- name: Test All Nodes with GeoIP
  run: |
    python scripts/node_tester_with_geoip.py \
      --input-file all_unique_nodes.yaml \
      --output healthy_nodes_list.yaml \
      --clash-path /usr/local/bin/mihomo \
      --enable-geoip \
      --geoip-workers 3 \
      --geoip-timeout 15
```

### 环境变量配置
```yaml
env:
  # 地理位置检测配置
  ENABLE_GEOIP: "true"
  GEOIP_WORKERS: "3"
  GEOIP_TIMEOUT: "15"
```

## 📋 输出文件

### 标准输出
```yaml
# healthy_nodes_list.yaml
proxies:
  - name: "🇭🇰 香港 Premium-01"
    type: vmess
    server: example.com
    port: 443
    # ... 其他配置
```

### 详细信息输出 (启用 --save-geoip-details)
```yaml
# healthy_nodes_list_geoip_details.yaml
proxies:
  - name: "🇭🇰 香港 Premium-01"
    type: vmess
    server: example.com
    port: 443
    _original_name: "HK-Premium-01"
    _exit_ip: "203.198.7.66"
    _location:
      country_code: "HK"
      city: "Hong Kong"
      region: "Hong Kong"
      service: "ipapi.co"
    _renamed: true
```

## ⚠️ 注意事项

### API限制
- 某些GeoIP服务有请求频率限制
- 建议设置合理的并发数 (3-5个)
- 避免短时间内大量请求

### 网络要求
- 需要稳定的网络连接
- 某些地区可能无法访问部分GeoIP服务
- 建议在网络条件良好时运行

### 时间成本
- 地理位置检测会增加总运行时间
- 1000个节点大约需要额外10-20分钟
- 可根据需要调整并发数和超时时间

## 🎯 最佳实践

### 推荐配置
```bash
# 生产环境推荐配置
python scripts/node_tester_with_geoip.py \
  --input-file all_unique_nodes.yaml \
  --output healthy_nodes_list.yaml \
  --clash-path /usr/local/bin/mihomo \
  --enable-geoip \
  --geoip-workers 3 \
  --geoip-timeout 15 \
  --delay-limit 3000 \
  --max-workers 50
```

### 调试模式
```bash
# 调试模式：详细日志 + 保存详细信息
LOG_LEVEL=DEBUG python scripts/node_tester_with_geoip.py \
  --input-file test_nodes.yaml \
  --output test_output.yaml \
  --clash-path /usr/local/bin/mihomo \
  --enable-geoip \
  --geoip-workers 1 \
  --geoip-timeout 30 \
  --save-geoip-details
```

## 🔄 迁移指南

### 从原版本迁移
1. **保持兼容**: 不启用 `--enable-geoip` 时功能完全一致
2. **逐步启用**: 先在小规模节点上测试
3. **监控性能**: 观察运行时间和成功率
4. **调整参数**: 根据实际情况优化并发数和超时时间

### 回退方案
如需回退到原版本：
```bash
# 使用原始的 node_tester.py
python scripts/node_tester.py \
  --input-file all_unique_nodes.yaml \
  --output healthy_nodes_list.yaml \
  --clash-path /usr/local/bin/mihomo
```

---

**🎉 现在您可以享受更精确的地理位置识别和更丰富的地区支持！**