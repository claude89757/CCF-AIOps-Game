# CCF AIOps智能体日志系统

## 📁 日志目录结构

```
src/logs/
├── diagnosis/          # 诊断过程日志
├── errors/            # 错误日志
├── interactions/      # 智能体交互日志  
├── tools/             # 工具执行日志
├── summary/           # 总结日志
└── README.md          # 本说明文档
```

## 📝 日志文件类型

### 1. 总结日志 (`summary/`)
**文件格式**: `summary_YYYYMMDD_HHMMSS.log`

**内容**:
- 智能体初始化信息
- 处理进度统计
- 案例处理结果
- 最终统计信息

**示例**:
```
2025-06-29 04:04:05 | summary | INFO | === CCF AIOps智能体初始化完成 ===
2025-06-29 04:04:05 | summary | INFO | 模型: deepseek-v3:671b
2025-06-29 04:04:05 | summary | INFO | 共发现 211 个故障案例
2025-06-29 04:04:05 | summary | INFO | 处理案例 1/211: 345fbe93-80
```

### 2. 诊断过程日志 (`diagnosis/`)
**文件格式**: `diagnosis_YYYYMMDD_HHMMSS.log`

**内容**:
- 每个故障案例的详细诊断过程
- 推理步骤记录 (步骤编号、行动、观察、推理)
- 时间窗口提取和文件发现
- 诊断轮次记录

**示例**:
```
2025-06-29 04:04:05 | diagnosis | INFO | 开始诊断故障案例: 345fbe93-80
2025-06-29 04:04:09 | diagnosis | INFO | 步骤 1:
2025-06-29 04:04:09 | diagnosis | INFO |   行动: preview_parquet_in_pd({"file_path": "data/2025-06-06/metric-parquet/"})
2025-06-29 04:04:09 | diagnosis | INFO |   观察: {'error': '读取文件失败: Float value 3.23 was truncated...'}
```

### 3. 工具执行日志 (`tools/`)
**文件格式**: `tools_YYYYMMDD_HHMMSS.log`

**内容**:
- 工具调用详情
- 参数完整记录 (JSON格式)
- 执行结果统计
- 执行时间统计
- 成功/失败状态

**示例**:
```
2025-06-29 04:04:09 | tool | INFO | 执行工具: preview_parquet_in_pd
2025-06-29 04:04:09 | tool | INFO | 参数: {"file_path": "data/2025-06-06/metric-parquet/"}
2025-06-29 04:04:09 | tool | ERROR | 工具执行失败: 读取文件失败
2025-06-29 04:04:09 | tool | INFO | 执行时间: 0.05秒
```

### 4. 智能体交互日志 (`interactions/`)
**文件格式**: `interactions_YYYYMMDD_HHMMSS.log`

**内容**:
- 模型交互轮次
- 消息数量统计
- 响应长度统计
- 工具调用解析结果

**示例**:
```
2025-06-29 04:04:05 | interaction | INFO | 第 1 轮模型交互
2025-06-29 04:04:05 | interaction | INFO | 消息数量: 2
2025-06-29 04:04:05 | interaction | INFO | 响应长度: 713 字符
2025-06-29 04:04:09 | interaction | DEBUG | 解析到工具调用: preview_parquet_in_pd
```

### 5. 错误日志 (`errors/`)

#### 5.1 全局错误日志
**文件格式**: `errors_YYYYMMDD_HHMMSS.log`
**内容**: 系统级错误和异常

#### 5.2 案例特定错误日志
**文件格式**: `case_{uuid}_error.log`
**内容**: 
- 特定案例的所有错误记录
- 工具执行失败详情
- 完整错误堆栈信息

**示例**:
```
2025-06-29 04:04:09 | case_error_345fbe93-80 | ERROR | 工具执行失败 - preview_parquet_in_pd: 读取文件失败
2025-06-29 04:04:13 | case_error_345fbe93-80 | ERROR | 工具执行失败 - preview_parquet_in_pd: 文件不存在
```

## 🔧 日志系统功能

### ✅ 已实现功能

1. **自动目录创建**: 程序启动时自动创建日志目录结构
2. **时间戳命名**: 按启动时间命名日志文件，避免覆盖
3. **案例隔离**: 每个故障案例有独立的错误日志文件
4. **分级记录**: INFO/WARNING/ERROR/DEBUG 多级别日志
5. **结构化格式**: 时间戳 | 类型 | 级别 | 消息
6. **执行统计**: 工具执行时间、数据量统计
7. **错误追踪**: 完整的错误堆栈和上下文信息
8. **进度监控**: 实时处理进度和状态记录

### 🎯 日志用途

1. **问题诊断**: 
   - 查看案例特定错误日志定位问题
   - 分析工具执行失败原因
   - 追踪智能体推理过程

2. **性能分析**:
   - 工具执行时间统计
   - 模型交互轮次分析
   - 数据处理量统计

3. **系统监控**:
   - 处理进度跟踪
   - 成功率统计
   - 系统运行状态监控

## 📊 日志分析示例

### 查看处理总结
```bash
tail -f src/logs/summary/summary_*.log
```

### 查看特定案例错误
```bash
cat src/logs/errors/case_{uuid}_error.log
```

### 分析工具执行性能
```bash
grep "执行时间" src/logs/tools/tools_*.log
```

### 监控诊断进度
```bash
grep "步骤" src/logs/diagnosis/diagnosis_*.log
```

## 🚀 快速排错指南

1. **案例处理失败**:
   - 查看: `src/logs/errors/case_{uuid}_error.log`
   - 定位: 工具执行失败的具体原因

2. **系统运行异常**:
   - 查看: `src/logs/summary/summary_*.log`
   - 分析: 整体处理流程和统计信息

3. **数据读取问题**:
   - 查看: `src/logs/tools/tools_*.log`
   - 分析: 文件路径、参数配置等

4. **推理过程异常**:
   - 查看: `src/logs/diagnosis/diagnosis_*.log`
   - 追踪: 每个步骤的执行情况

## 🔄 日志轮转和清理

- **手动清理**: 定期删除旧的日志文件
- **建议保留**: 最近3-7天的日志文件
- **压缩存档**: 可使用 `gzip` 压缩历史日志

```bash
# 清理7天前的日志
find src/logs -name "*.log" -mtime +7 -delete

# 压缩历史日志
find src/logs -name "*.log" -mtime +1 -exec gzip {} \;
``` 