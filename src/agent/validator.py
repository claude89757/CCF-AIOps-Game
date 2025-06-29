#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: 工具参数验证器
"""

import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

from ..config import AgentConfig


class ParameterValidator:
    """工具参数验证和修正器"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger('interaction')
    
    def validate_tool_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """增强的验证和修正工具调用参数，智能处理过滤器错误"""
        validated_params = parameters.copy()
        
        if tool_name == "get_data_from_parquet":
            validated_params = self._validate_parquet_parameters(validated_params)
        
        return validated_params
    
    def _validate_parquet_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证和修正Parquet工具参数"""
        # 检查并修正pd_read_kwargs参数
        if 'pd_read_kwargs' in parameters:
            kwargs = parameters['pd_read_kwargs']
            if isinstance(kwargs, str):
                try:
                    kwargs = eval(kwargs)
                    parameters['pd_read_kwargs'] = kwargs
                except:
                    parameters['pd_read_kwargs'] = {}
            
            # 智能过滤器验证和修正
            if isinstance(kwargs, dict) and 'filters' in kwargs:
                filters = kwargs['filters']
                if isinstance(filters, list):
                    valid_filters, filter_issues = self._validate_parquet_filters(filters)
                    
                    # 如果发现过滤器问题，提供智能回退策略
                    if filter_issues:
                        self.logger.warning(f"发现过滤器问题: {filter_issues}")
                        
                        # 策略1: 如果所有过滤器都有问题，移除过滤器
                        if not valid_filters:
                            self.logger.warning("移除所有过滤器，使用无过滤读取")
                            kwargs.pop('filters', None)
                            # 限制行数以防止数据过大
                            if 'nrows' not in kwargs or kwargs.get('nrows', 1000) > self.config.default_nrows:
                                kwargs['nrows'] = self.config.default_nrows
                                self.logger.info(f"设置安全行数限制: {self.config.default_nrows}")
                        else:
                            kwargs['filters'] = valid_filters
                            self.logger.info(f"保留有效过滤器: {valid_filters}")
            
            # 时间戳格式智能修正
            self._fix_timestamp_formats_in_kwargs(kwargs)
            
            # 安全性检查：确保参数合理性
            self._apply_safety_limits(kwargs)
        
        return parameters
    
    def _validate_parquet_filters(self, filters: List) -> Tuple[List, List]:
        """
        验证Parquet过滤器的有效性
        
        Args:
            filters: 过滤器列表
            
        Returns:
            (有效过滤器列表, 问题列表)
        """
        valid_filters = []
        issues = []
        
        supported_ops = self.config.get_supported_filter_operators()
        problematic_columns = self.config.get_problematic_columns()
        
        for filter_item in filters:
            if not isinstance(filter_item, list) or len(filter_item) != 3:
                issues.append(f"过滤器格式错误: {filter_item}")
                continue
            
            col, op, val = filter_item
            
            # 检查操作符
            if op not in supported_ops:
                if op in ['like', 'contains', 'ilike', 'regex']:
                    issues.append(f"不支持的操作符 '{op}'，已跳过过滤器 {filter_item}")
                    continue
                else:
                    issues.append(f"未知操作符 '{op}'，尝试替换为 '=='")
                    op = '=='
            
            # 检查时间戳格式
            if '@timestamp' in str(col) and isinstance(val, str):
                # 尝试修正时间戳格式
                fixed_val = self._fix_timestamp_value(val)
                if fixed_val != val:
                    issues.append(f"修正时间戳格式: {val} -> {fixed_val}")
                    val = fixed_val
            
            # 检查可能有问题的列名
            if col in problematic_columns:
                issues.append(f"可能有问题的列名 '{col}'，建议预览数据确认列名")
            
            # 检查None值
            if val is None:
                issues.append(f"过滤值为None: {filter_item}")
                continue
            
            valid_filters.append([col, op, val])
        
        return valid_filters, issues
    
    def _fix_timestamp_formats_in_kwargs(self, kwargs: Dict[str, Any]):
        """修正kwargs中的时间戳格式"""
        if 'filters' in kwargs and isinstance(kwargs['filters'], list):
            for filter_item in kwargs['filters']:
                if isinstance(filter_item, list) and len(filter_item) == 3:
                    col, op, val = filter_item
                    if '@timestamp' in str(col) and isinstance(val, str):
                        filter_item[2] = self._fix_timestamp_value(val)
    
    def _fix_timestamp_value(self, timestamp_str: str) -> str:
        """
        智能修正时间戳格式
        
        Args:
            timestamp_str: 原始时间戳字符串
            
        Returns:
            修正后的时间戳字符串
        """
        # 移除常见的问题字符
        fixed = timestamp_str.strip()
        
        # 处理ISO格式中的Z结尾
        if fixed.endswith('Z'):
            fixed = fixed[:-1]
        
        # 处理微秒部分
        if '.' in fixed and len(fixed.split('.')[-1]) > 6:
            # 截断微秒到6位
            main_part, micro_part = fixed.rsplit('.', 1)
            fixed = f"{main_part}.{micro_part[:6]}"
        
        # 确保格式为 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS
        import re
        if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', fixed):
            # ISO格式，保持不变
            return fixed
        elif re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', fixed):
            # 标准格式，保持不变
            return fixed
        else:
            # 其他格式，尝试解析和标准化
            try:
                # 尝试多种格式解析
                formats = [
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%d %H:%M:%S.%f',
                    '%Y-%m-%d %H:%M:%S',
                ]
                
                for fmt in formats:
                    try:
                        dt = datetime.strptime(fixed, fmt)
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        continue
                        
                # 如果都失败了，返回原值
                return timestamp_str
            except:
                return timestamp_str
    
    def _apply_safety_limits(self, kwargs: Dict[str, Any]):
        """应用安全限制，防止数据过载"""
        # 如果没有指定行数限制，添加默认限制
        if 'nrows' not in kwargs:
            # 如果有过滤器，可以稍微放宽限制
            if 'filters' in kwargs and kwargs['filters']:
                kwargs['nrows'] = self.config.default_nrows
            else:
                kwargs['nrows'] = int(self.config.default_nrows * 0.8)
            self.logger.info(f"添加安全行数限制: {kwargs['nrows']}")
        else:
            # 如果指定的行数过大，进行限制
            if kwargs['nrows'] > self.config.max_safe_rows:
                self.logger.warning(f"行数限制过大({kwargs['nrows']})，调整为{self.config.max_safe_rows}")
                kwargs['nrows'] = self.config.max_safe_rows
        
        # 确保列选择合理
        if 'columns' in kwargs and isinstance(kwargs['columns'], list):
            if len(kwargs['columns']) > self.config.max_columns:
                self.logger.warning(f"列数过多({len(kwargs['columns'])})，可能影响性能")
                # 保留前10个重要列
                important_cols = ['@timestamp', 'message', 'level', 'k8_pod', 'k8_namespace']
                selected_cols = []
                for col in important_cols:
                    if col in kwargs['columns']:
                        selected_cols.append(col)
                # 添加其他列，最多10个
                for col in kwargs['columns']:
                    if col not in selected_cols and len(selected_cols) < 10:
                        selected_cols.append(col)
                kwargs['columns'] = selected_cols
                self.logger.info(f"优化列选择: {selected_cols}") 