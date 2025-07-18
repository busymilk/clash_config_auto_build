# 🧪 重构测试验证清单

## 📋 测试步骤

### 1. 手动触发 GitHub Actions
- [ ] 访问: https://github.com/busymilk/clash_config_auto_build/actions
- [ ] 点击 "Generate Clash Config (Refactored)" workflow
- [ ] 点击 "Run workflow" 按钮手动触发

### 2. 监控运行状态

#### 🔍 关键检查点
- [ ] **步骤4**: 创建目录 - 应该成功创建 config/ 和 utils/ 目录
- [ ] **步骤7**: 合并代理 - 使用重构版 `merge_proxies.py`
- [ ] **步骤9**: 测试节点 - 使用重构版 `node_tester.py`  
- [ ] **步骤10**: 生成配置 - 使用重构版 `generate_config.py`

#### 📊 预期日志输出
```
✅ 统一日志格式: 
[INFO] 2025-01-27 XX:XX:XX - merge_proxies - 发现 X 个代理文件，准备开始处理...
[INFO] 2025-01-27 XX:XX:XX - node_tester - 开始测试 X 个代理节点...
[INFO] 2025-01-27 XX:XX:XX - config_generator - 成功加载模板: config-template.yaml

✅ 进度报告:
[INFO] 已测试 100/1000 个节点，健康节点: 85
[INFO] 已测试 200/1000 个节点，健康节点: 170

✅ 配置生成:
[INFO] 为 config/config.yaml 分配了 X 个节点。
[INFO] 地区过滤器 'hk' 筛选出 X 个节点
```

### 3. 验证输出结果

#### 📁 生成的文件
- [ ] `config/config.yaml` - 所有健康节点
- [ ] `config/config_hk.yaml` - 香港节点
- [ ] `config/config_us.yaml` - 美国节点
- [ ] `config/config_jp.yaml` - 日本节点
- [ ] `config/config_uk.yaml` - 英国节点
- [ ] `config/config_sg.yaml` - 新加坡节点
- [ ] `config/stash*.yaml` - Stash 版本配置

#### 🔍 文件内容检查
- [ ] 配置文件格式正确 (YAML 语法)
- [ ] 节点数量合理 (与之前版本对比)
- [ ] 地区过滤正确 (HK文件只包含香港节点)

### 4. 性能对比

#### ⏱️ 运行时间
- **重构前**: 约 X 分钟
- **重构后**: 约 X 分钟 (预期相近或略有改善)

#### 📊 节点数量
- **总节点数**: 应与重构前基本一致
- **健康节点数**: 应与重构前基本一致
- **各地区分布**: 应与重构前基本一致

### 5. 错误处理验证

#### 🛡️ 容错能力
- [ ] 网络异常时的处理
- [ ] 无效节点的过滤
- [ ] 空配置文件的处理

#### 📝 日志质量
- [ ] 错误信息详细明确
- [ ] 警告信息适当
- [ ] 调试信息有用

## 🚨 故障排除

### 常见问题及解决方案

#### 问题1: 模块导入失败
```
ModuleNotFoundError: No module named 'config'
```
**解决方案**: 检查 config/__init__.py 和 utils/__init__.py 是否存在

#### 问题2: 环境变量未生效
```
使用默认值而非环境变量值
```
**解决方案**: 检查 workflow 中的 env 配置

#### 问题3: 节点数量异常
```
生成的节点数量明显少于预期
```
**解决方案**: 检查过滤逻辑和黑名单配置

### 🔄 回滚方案
如果测试失败，可以快速回滚：
```bash
# 恢复原始文件
git checkout HEAD~1 -- scripts/
git checkout HEAD~1 -- .github/workflows/clash-config.yml

# 或者使用备份文件
cp scripts/*.backup scripts/
cp .github/workflows/clash-config.yml.backup .github/workflows/clash-config.yml
```

## ✅ 测试通过标准

### 必须通过的检查
- [ ] GitHub Actions 运行成功 (绿色✅)
- [ ] 生成所有预期的配置文件
- [ ] 配置文件格式正确
- [ ] 节点数量在合理范围内
- [ ] 日志输出清晰有序

### 性能要求
- [ ] 运行时间不超过重构前的120%
- [ ] 内存使用正常
- [ ] 无明显性能退化

### 功能要求
- [ ] 所有地区过滤正常工作
- [ ] 节点去重功能正常
- [ ] 健康检查功能正常
- [ ] CDN 缓存刷新正常

## 📊 测试结果记录

### 运行信息
- **测试时间**: ___________
- **运行时长**: ___________
- **总节点数**: ___________
- **健康节点数**: ___________

### 各地区节点数
- **香港 (HK)**: ___________
- **美国 (US)**: ___________
- **日本 (JP)**: ___________
- **英国 (UK)**: ___________
- **新加坡 (SG)**: ___________

### 测试结论
- [ ] ✅ 测试通过，重构成功
- [ ] ⚠️ 部分问题，需要调整
- [ ] ❌ 测试失败，需要回滚

---

**下一步**: 根据测试结果决定是否需要进一步优化或添加新功能。