#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-28
@description: AI智能体工具函数 - 用于微服务故障诊断
"""

import pandas as pd
import os
import json
from typing import Dict, Any, Optional, Union


def estimate_tokens(data: Any) -> int:
    """
    估算数据的token数量
    
    Args:
        data: 要估算的数据
    
    Returns:
        估算的token数量
    """
    try:
        # 将数据转换为JSON字符串
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, ensure_ascii=False)
        else:
            json_str = str(data)
        
        # 计算字符数
        char_count = len(json_str)
        
        # 估算token数量 (1 token ≈ 3-4 characters for mixed Chinese/English)
        # 为了安全起见，使用较小的除数
        estimated_tokens = char_count // 3
        
        return estimated_tokens
    except:
        return 0


def preview_parquet_in_pd(file_path: str, pd_read_kwargs: dict = {}) -> Dict[str, Any]:
    """
    预览parquet文件基本信息和前几行数据
    
    Args:
        file_path: parquet文件路径
        pd_read_kwargs: pandas.read_parquet的额外参数
    
    Returns:
        包含文件基本信息、列信息和示例数据的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "error": f"File not found: {file_path}",
                "suggestion": "Please check if the file path is correct"
            }
        
        # 读取数据（先读取完整数据，然后取前几行用于预览）
        df = pd.read_parquet(file_path, **pd_read_kwargs)
        
        # 限制预览行数
        preview_rows = 3
        df = df.head(preview_rows)
        
        # 获取文件大小
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        # 构建预览信息
        preview_info = {
            "file_path": file_path,
            "file_size_mb": round(file_size_mb, 2),
            "shape": f"({df.shape[0]} rows × {df.shape[1]} columns) - Only showing first {preview_rows} rows",
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "sample_data": df.to_dict(orient='records'),
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 3),
            "null_counts": df.isnull().sum().to_dict(),
            "ai_tips": "This is a data preview. Use get_data_from_parquet function for complete data"
        }
        
        # 如果文件较大，添加警告
        if file_size_mb > 50:
            preview_info["warning"] = f"Large file ({file_size_mb:.1f}MB), recommend using parameters to limit data reading"
        
        return preview_info
        
    except Exception as e:
        return {
            "error": f"Failed to read file: {str(e)}",
            "file_path": file_path,
            "suggestion": "Please check file format or use correct pd_read_kwargs parameters"
        }


def get_data_from_parquet(file_path: str, pd_read_kwargs: dict = {}) -> Dict[str, Any]:
    """
    从parquet文件获取数据，考虑AI上下文窗口限制
    
    Args:
        file_path: parquet文件路径
        pd_read_kwargs: pandas.read_parquet的参数，如：
                       - nrows: 限制读取行数
                       - columns: 指定读取的列
                       - filters: 过滤条件
    
    Returns:
        包含数据和相关信息的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "error": f"File not found: {file_path}",
                "suggestion": "Please check if the file path is correct"
            }
        
        # 获取文件大小
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        # 检查是否需要限制行数
        original_kwargs = pd_read_kwargs.copy()  # 保存原始参数
        nrows_limit = pd_read_kwargs.pop('nrows', None)  # 从参数中取出nrows
        suggested_limit = False
        
        # 如果没有指定行数限制且文件较大，设置默认限制
        if nrows_limit is None and file_size_mb > 10:
            nrows_limit = 800  # 从1000改为800，更严格的限制
            suggested_limit = True
        
        # 读取数据
        df = pd.read_parquet(file_path, **pd_read_kwargs)
        
        # 应用行数限制
        if nrows_limit is not None:
            df = df.head(nrows_limit)
        
        # 计算内存使用
        memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
        
        # 准备返回的数据
        data_dict = df.to_dict(orient='records')
        
        # 估算token数量
        estimated_tokens = estimate_tokens(data_dict)
        max_tokens = 6000  # 大幅降低最大token限制，从10000改为6000
        
        # 构建返回信息
        result = {
            "file_path": file_path,
            "shape": df.shape,
            "columns": list(df.columns),
            "memory_usage_mb": round(memory_mb, 3),
            "read_params": original_kwargs,
            "actual_rows_read": df.shape[0],
            "estimated_tokens": estimated_tokens
        }
        
        # 检查token数量是否超限
        if estimated_tokens > max_tokens:
            result.update({
                "data_too_large": True,
                "error": f"Data too large, estimated {estimated_tokens} tokens, exceeds {max_tokens} token limit",
                "suggestion": "Please adjust filter conditions to reduce data size, recommended actions:",
                "optimization_tips": [
                    "1. Use nrows parameter to limit rows, e.g.: {'nrows': 100}",
                    "2. Use columns parameter to read only needed columns, e.g.: {'columns': ['timestamp', 'message']}",
                    "3. Use filters parameter to filter data, e.g.: {'filters': [('level', '==', 'ERROR')]}",
                    "4. Combine multiple conditions: {'nrows': 200, 'columns': ['time', 'level', 'message']}"
                ],
                "current_row_count": df.shape[0],
                "current_column_count": df.shape[1],
                "recommended_max_rows": min(300, max_tokens // (len(df.columns) * 12))  # 更保守的建议行数，从500改为300，从10改为12
            })
            # 不返回实际数据
            return result
        
        # 数据量合适，返回数据
        result["data"] = data_dict
        
        # 根据数据量添加相应的提示
        if df.shape[0] > 300:  # 从500改为300，更早警告
            result["ai_warning"] = f"Large dataset ({df.shape[0]} rows), may affect AI processing efficiency"
            result["suggestion"] = "Recommend using nrows parameter to limit rows, or columns parameter to read only needed columns"
        
        if memory_mb > 3:  # 从5改为3，更早警告
            result["memory_warning"] = f"High memory usage ({memory_mb:.1f}MB)"
            result["suggestion"] = "Recommend reducing data size or processing in batches"
        
        if suggested_limit:
            result["auto_limit_applied"] = f"Large file, automatically limited to first {nrows_limit} rows"
            result["suggestion"] = "If you need more data, please specify nrows parameter in pd_read_kwargs"
        
        # 为AI智能体提供数据理解辅助信息
        if df.shape[1] > 0:
            # 数值列统计
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                result["numeric_summary"] = df[numeric_cols].describe().to_dict()
            
            # 时间列识别
            time_cols = []
            for col in df.columns:
                if any(keyword in col.lower() for keyword in ['time', 'timestamp', 'date']):
                    time_cols.append(col)
            if time_cols:
                result["time_columns"] = time_cols
        
        return result
        
    except Exception as e:
        return {
            "error": f"Failed to read file: {str(e)}",
            "file_path": file_path,
            "suggestion": "Please check file format, path or adjust pd_read_kwargs parameters"
        }


# 测试用例
def test_get_data_from_parquet():
    """测试 get_data_from_parquet 函数的各种情况"""
    
    # 测试文件路径（请根据实际情况调整）
    test_file = 'data/2025-06-06/log-parquet/log_filebeat-server_2025-06-06_03-00-00.parquet'
    
    print("=" * 60)
    print("测试 get_data_from_parquet 函数")
    print("=" * 60)
    
    # 测试1: 正常读取少量数据
    print("\n测试1: 正常读取少量数据 (nrows=10)")
    result1 = get_data_from_parquet(test_file, {'nrows': 10})
    print(f"结果: 读取了 {result1.get('actual_rows_read', 0)} 行，估算token数: {result1.get('estimated_tokens', 0)}")
    if 'data_too_large' in result1:
        print("❌ 数据量过大")
    else:
        print("✅ 数据量合适")
    
    # 测试2: 读取较多数据，可能触发token限制
    print("\n测试2: 读取较多数据 (nrows=2000)")
    result2 = get_data_from_parquet(test_file, {'nrows': 2000})
    print(f"结果: 读取了 {result2.get('actual_rows_read', 0)} 行，估算token数: {result2.get('estimated_tokens', 0)}")
    if 'data_too_large' in result2:
        print("❌ 数据量过大，已阻止返回数据")
        print("建议操作:", result2.get('optimization_tips', [])[:2])
    else:
        print("✅ 数据量合适")
    
    # 测试3: 不限制行数，可能触发token限制
    print("\n测试3: 不限制行数读取")
    result3 = get_data_from_parquet(test_file)
    print(f"结果: 读取了 {result3.get('actual_rows_read', 0)} 行，估算token数: {result3.get('estimated_tokens', 0)}")
    if 'data_too_large' in result3:
        print("❌ 数据量过大，已阻止返回数据")
        print(f"建议最大行数: {result3.get('recommended_max_rows', 'N/A')}")
    else:
        print("✅ 数据量合适")
    
    # 测试4: 使用列限制减少数据量
    print("\n测试4: 限制列数读取 (只读取前3列)")
    result4 = get_data_from_parquet(test_file, {'nrows': 500})
    if 'columns' in result4 and len(result4['columns']) > 3:
        limited_columns = result4['columns'][:3]
        result4_limited = get_data_from_parquet(test_file, {
            'nrows': 500, 
            'columns': limited_columns
        })
        print(f"结果: 读取了 {result4_limited.get('actual_rows_read', 0)} 行，{len(limited_columns)} 列")
        print(f"估算token数: {result4_limited.get('estimated_tokens', 0)}")
        if 'data_too_large' in result4_limited:
            print("❌ 即使限制列数，数据量仍然过大")
        else:
            print("✅ 通过限制列数，数据量变得合适")
    
    # 测试5: 使用过滤条件（如果数据中有可过滤的列）
    print("\n测试5: 使用过滤条件")
    # 先获取列信息
    preview = preview_parquet_in_pd(test_file)
    if 'columns' in preview:
        print(f"可用列: {preview['columns'][:5]}...")  # 显示前5列
        
        # 尝试使用过滤条件（这里假设有某个列可以过滤）
        # 注意：实际使用时需要根据数据的具体列名和值来设置过滤条件
        # 例如：filters=[('level', '==', 'ERROR')] 或 filters=[('k8_namespace', '==', 'hipstershop')]
        print("提示: 可以使用 filters 参数进行过滤，例如:")
        print("  {'filters': [('column_name', '==', 'value')]}")
        print("  {'filters': [('level', '==', 'ERROR')]}")
        print("  {'filters': [('timestamp', '>', '2025-06-06 10:00:00')]}")
    
    # 测试6: 实际使用过滤条件控制数据量
    print("\n测试6: 实际过滤测试 - 过滤特定namespace + 限制行数和列")
    result6 = get_data_from_parquet(test_file, {
        'filters': [('k8_namespace', '==', 'hipstershop')],
        'nrows': 100,
        'columns': ['@timestamp', 'k8_pod', 'message']
    })
    print(f"结果: 读取了 {result6.get('actual_rows_read', 0)} 行，{len(result6.get('columns', []))} 列")
    print(f"估算token数: {result6.get('estimated_tokens', 0)}")
    if 'data_too_large' in result6:
        print("❌ 数据量仍然过大")
        print(f"建议最大行数: {result6.get('recommended_max_rows', 'N/A')}")
    else:
        print("✅ 通过过滤条件成功控制数据量")
        print(f"实际数据示例(前2条): {result6.get('data', [])[:2]}")
    
    # 测试7: 更严格的过滤 - 只读取关键列和更少行数
    print("\n测试7: 更严格过滤 - 最小数据集")
    result7 = get_data_from_parquet(test_file, {
        'filters': [('k8_namespace', '==', 'hipstershop')],
        'nrows': 20,
        'columns': ['@timestamp', 'message']
    })
    print(f"结果: 读取了 {result7.get('actual_rows_read', 0)} 行，{len(result7.get('columns', []))} 列")
    print(f"估算token数: {result7.get('estimated_tokens', 0)}")
    if 'data_too_large' in result7:
        print("❌ 数据量仍然过大")
    else:
        print("✅ 成功获取最小数据集")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


# 主程序测试
if __name__ == "__main__":
    # 运行测试
    test_get_data_from_parquet()
    
    print("\n" + "-" * 40)
    print("单独测试示例:")
    print("-" * 40)
    
    # 单独测试一个文件
    result = preview_parquet_in_pd('data/processed_data/2025-06-05/log-parquet/log_filebeat-server_2025-06-05.parquet')
    print("预览结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))



"""
===================================================================================
AI智能体数据获取工具使用指南
===================================================================================

## 核心功能
1. **preview_parquet_in_pd**: 快速预览parquet文件结构和少量示例数据
2. **get_data_from_parquet**: 智能获取数据，自动控制数据量在10K token以内

## Token限制说明
- 最大限制: 10,000 tokens
- 超过限制时会返回提示信息，不返回实际数据
- 估算方式: 字符数 ÷ 3 (适用于中英文混合文本)

## 使用策略（推荐顺序）

### 1. 先预览数据结构
```python
preview = preview_parquet_in_pd('path/to/file.parquet')
print(f"可用列: {preview['columns']}")
print(f"数据类型: {preview['dtypes']}")
```

### 2. 根据需求选择合适的读取策略

#### 策略A: 限制行数 + 选择关键列
```python
result = get_data_from_parquet('path/to/file.parquet', {
    'nrows': 100,
    'columns': ['timestamp', 'level', 'message']
})
```

#### 策略B: 使用过滤条件 + 限制行数
```python
result = get_data_from_parquet('path/to/file.parquet', {
    'filters': [('level', '==', 'ERROR')],
    'nrows': 200
})
```

#### 策略C: 组合使用（推荐）
```python
result = get_data_from_parquet('path/to/file.parquet', {
    'filters': [('k8_namespace', '==', 'hipstershop')],
    'nrows': 100,
    'columns': ['@timestamp', 'k8_pod', 'message']
})
```

## 常见过滤条件示例

### 时间过滤
```python
{'filters': [('@timestamp', '>', '2025-06-06 10:00:00')]}
```

### 日志级别过滤
```python
{'filters': [('level', '==', 'ERROR')]}
{'filters': [('level', 'in', ['ERROR', 'WARN'])]}
```

### 服务/命名空间过滤
```python
{'filters': [('k8_namespace', '==', 'hipstershop')]}
{'filters': [('k8_pod', 'like', 'cartservice*')]}
```

### 组合过滤
```python
{'filters': [
    ('k8_namespace', '==', 'hipstershop'),
    ('@timestamp', '>', '2025-06-06 10:00:00')
]}
```

## 错误处理和重试策略

### 当遇到 "data_too_large" 错误时的处理步骤：

1. **检查建议信息**
```python
if 'data_too_large' in result:
    print("错误:", result['error'])
    print("建议:", result['optimization_tips'])
    print("推荐最大行数:", result['recommended_max_rows'])
```

2. **根据建议调整参数**
```python
# 原始调用失败
result = get_data_from_parquet('file.parquet', {'nrows': 2000})

# 根据建议重试
if 'data_too_large' in result:
    max_rows = result['recommended_max_rows']
    result = get_data_from_parquet('file.parquet', {
        'nrows': max_rows,
        'columns': ['timestamp', 'message']  # 只读取关键列
    })
```

## 测试结果参考
- ✅ 10行数据: ~1,300 tokens (正常)
- ✅ 100行过滤数据: ~9,100 tokens (接近限制但可用)
- ✅ 20行精简数据: ~1,400 tokens (最佳)
- ❌ 2000行数据: ~238,000 tokens (超限)
- ❌ 不限制行数: ~18M tokens (远超限制)

## 最佳实践
1. 总是先使用 preview_parquet_in_pd 了解数据结构
2. 优先使用过滤条件减少无关数据
3. 只读取分析所需的列
4. 从小数据量开始，逐步增加
5. 利用时间窗口限制数据范围
6. 针对特定服务或错误类型进行过滤

===================================================================================
"""