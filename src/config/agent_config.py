#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: 智能体配置管理
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class AgentConfig:
    """智能体配置类 - 统一管理所有配置参数"""
    
    # 模型相关配置
    default_model: str = "deepseek-v3:671b"
    max_iterations: int = 30
    max_model_retries: int = 5
    
    # 已申请支持的模型配置
    MODEL_CONFIGS: Dict[str, Dict[str, Any]] = None
    
    # 上下文管理配置 - 更严格的限制
    context_safety_ratio: float = 0.75  # 降低安全余量比例，从0.8改为0.75
    context_compress_ratio: float = 0.8  # 更早触发压缩，从0.9改为0.8
    max_tool_result_ratio: float = 0.12  # 降低工具结果限制比例，从0.15改为0.12
    
    # 数据处理配置 - 更严格的数据限制
    default_nrows: int = 300  # 降低默认行数限制，从500改为300
    max_safe_rows: int = 800  # 降低最大安全行数，从1000改为800
    max_columns: int = 12  # 降低最大列数，从15改为12
    preview_rows: int = 3  # 降低预览行数，从5改为3
    
    # 重试配置
    retry_delay: float = 2.0  # 重试延迟（秒）
    max_retry_attempts: int = 5  # 最大重试次数
    
    # Token管理配置 - 更严格的token限制
    max_token_limit: int = 6000  # 大幅降低工具数据最大token限制，从10000改为6000
    token_estimation_ratio: int = 3  # token估算比例（字符数/3）
    
    # 日志配置
    log_base_dir: str = "src/logs"
    log_level: str = "INFO"
    
    # 数据路径配置
    data_base_path: str = "data"  # 基础数据目录，预处理后的数据在 data/processed_data/
    
    def __post_init__(self):
        """初始化后处理"""
        if self.MODEL_CONFIGS is None:
            self.MODEL_CONFIGS = {
                "deepseek-v3:671b": {"max_context_length": 63000, "temperature": 0.0},
                "qwen3:235b": {"max_context_length": 38000, "temperature": 0.0},
                "deepseek-r1:671b-0528": {"max_context_length": 63000, "temperature": 0.0},
            }
    
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """获取模型配置"""
        return self.MODEL_CONFIGS.get(model_name, self.MODEL_CONFIGS[self.default_model])
    
    def get_context_limits(self, max_context_length: int) -> Dict[str, int]:
        """根据模型上下文长度计算各种限制"""
        max_context_tokens = int(max_context_length * self.context_safety_ratio)
        context_compress_threshold = int(max_context_tokens * self.context_compress_ratio)
        max_tool_result_tokens = min(8000, int(max_context_tokens * self.max_tool_result_ratio))
        
        return {
            "max_context_tokens": max_context_tokens,
            "context_compress_threshold": context_compress_threshold,
            "max_tool_result_tokens": max_tool_result_tokens
        }
    
    def get_retry_errors(self) -> list:
        """获取可重试的错误类型"""
        return [
            'connection error',
            'timeout',
            'ssl',
            'network',
            'rate limit',
            'server error',
            'service unavailable',
            'bad gateway',
            'gateway timeout',
            'read timeout',
            'write timeout'
        ]
    
    def get_supported_filter_operators(self) -> list:
        """获取支持的过滤操作符"""
        return ['==', '!=', '<', '<=', '>', '>=', 'in', 'not in']
    
    def get_problematic_columns(self) -> list:
        """获取可能有问题的列名"""
        return ['level', 'severity', 'log_level'] 