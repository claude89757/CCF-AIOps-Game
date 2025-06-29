#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: 错误处理器
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from ..config import AgentConfig


class ErrorHandler:
    """智能错误处理器"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger('error')
    
    def handle_filter_error_fallback(self, tool_call_name: str, tool_parameters: Dict[str, Any], 
                                   original_error: Exception, tools: Dict) -> Optional[Dict[str, Any]]:
        """
        处理过滤器错误的智能回退策略
        
        Args:
            tool_call_name: 工具名称
            tool_parameters: 工具参数
            original_error: 原始错误
            tools: 可用工具字典
            
        Returns:
            回退执行结果，如果回退失败则返回None
        """
        try:
            self.logger.info("执行过滤器错误智能回退策略")
            
            # 获取原始参数
            original_params = tool_parameters.copy()
            file_path = original_params.get('file_path', '')
            
            # 回退策略序列
            fallback_strategies = [
                # 策略1: 移除所有过滤器，只保留基本参数
                {
                    'name': '移除过滤器策略',
                    'params': {
                        'file_path': file_path,
                        'pd_read_kwargs': {
                            'nrows': self.config.default_nrows,
                            'columns': ['@timestamp', 'message', 'k8_pod'] if 'log' in file_path else None
                        }
                    }
                },
                # 策略2: 最小化读取
                {
                    'name': '最小化读取策略',
                    'params': {
                        'file_path': file_path,
                        'pd_read_kwargs': {'nrows': 200}
                    }
                },
                # 策略3: 预览模式（使用preview工具）
                {
                    'name': '预览模式策略',
                    'tool': 'preview_parquet_in_pd',
                    'params': {
                        'file_path': file_path,
                        'pd_read_kwargs': {}
                    }
                }
            ]
            
            # 尝试回退策略
            for i, strategy in enumerate(fallback_strategies, 1):
                try:
                    self.logger.info(f"尝试回退策略{i}: {strategy['name']}")
                    
                    # 选择工具函数
                    if 'tool' in strategy:
                        tool_func = tools[strategy['tool']]
                        tool_name = strategy['tool']
                    else:
                        tool_func = tools[tool_call_name]
                        tool_name = tool_call_name
                    
                    # 执行回退策略
                    result = tool_func(**strategy['params'])
                    
                    # 如果成功，添加回退信息
                    if 'error' not in result:
                        result['fallback_used'] = True
                        result['fallback_strategy'] = strategy['name']
                        result['original_error'] = str(original_error)
                        
                        self.logger.info(f"回退策略{i}成功: {strategy['name']}")
                        return result
                    
                except Exception as fallback_error:
                    self.logger.warning(f"回退策略{i}失败: {fallback_error}")
                    continue
            
            # 所有回退策略都失败
            self.logger.error("所有回退策略都失败")
            return None
            
        except Exception as e:
            self.logger.error(f"回退策略执行异常: {e}")
            return None
    
    def get_error_suggestion(self, tool_name: str, error_msg: str) -> str:
        """
        根据工具和错误类型提供建议
        
        Args:
            tool_name: 工具名称
            error_msg: 错误信息
            
        Returns:
            错误建议
        """
        error_lower = error_msg.lower()
        
        if tool_name == "get_data_from_parquet":
            if 'malformed filters' in error_lower:
                return "过滤器格式错误，建议检查操作符(使用==,!=,<,>,>=,<=,in,not in)、列名和值格式"
            elif 'file not found' in error_lower or 'no such file' in error_lower:
                return "文件路径不存在，建议使用preview_parquet_in_pd先探索可用文件"
            elif 'columns not found' in error_lower:
                return "指定的列不存在，建议先用preview_parquet_in_pd查看列信息"
            elif 'memory' in error_lower or 'token' in error_lower:
                return "数据量过大，建议增加过滤条件、减少行数或选择关键列"
            else:
                return "建议简化参数：减少过滤条件、限制行数(nrows=500)、选择关键列"
        
        elif tool_name == "preview_parquet_in_pd":
            if 'file not found' in error_lower:
                return "文件路径不存在，请检查路径格式：data/YYYY-MM-DD/类型-parquet/*.parquet"
            else:
                return "文件预览失败，请检查文件路径和权限"
        
        return "请检查参数格式和数据文件可用性"
    
    def is_retryable_error(self, error_msg: str) -> bool:
        """判断错误是否可重试"""
        error_lower = error_msg.lower()
        retryable_errors = self.config.get_retry_errors()
        return any(err in error_lower for err in retryable_errors)
    
    def should_use_filter_fallback(self, tool_name: str, error_msg: str) -> bool:
        """判断是否应该使用过滤器回退策略"""
        if tool_name != "get_data_from_parquet":
            return False
        
        error_lower = error_msg.lower()
        filter_error_keywords = ['malformed filters', 'filter', 'operator']
        return any(keyword in error_lower for keyword in filter_error_keywords)
    
    def calculate_retry_delay(self, attempt: int, error_msg: str) -> float:
        """计算重试延迟时间"""
        base_delay = self.config.retry_delay
        error_lower = error_msg.lower()
        
        # 对于连接错误，使用更长延迟
        if 'connection' in error_lower or 'timeout' in error_lower:
            return base_delay * (attempt + 1) * 2
        
        # 其他错误使用指数退避
        return base_delay * attempt
    
    def log_error_with_context(self, error: Exception, context: str = "", uuid: str = "", 
                             case_error_logger: Optional[logging.Logger] = None):
        """记录错误信息，包含完整上下文"""
        import traceback
        
        error_msg = f"错误上下文: {context}\n错误信息: {str(error)}\n堆栈跟踪:\n{traceback.format_exc()}"
        
        self.logger.error(error_msg)
        
        # 如果有案例特定的错误日志记录器，也记录到那里
        if case_error_logger:
            case_error_logger.error(f"案例 {uuid} 错误: {error_msg}") 