#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: 工具执行器
"""

import json
import logging
from typing import Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass

from ..config import AgentConfig
from .validator import ParameterValidator
from .error_handler import ErrorHandler
from ..tools import preview_parquet_in_pd, get_data_from_parquet


@dataclass
class ToolCall:
    """工具调用数据结构"""
    name: str
    parameters: Dict[str, Any]


class ToolExecutor:
    """工具执行器"""
    
    def __init__(self, config: AgentConfig, loggers: Dict[str, logging.Logger]):
        self.config = config
        self.loggers = loggers
        self.validator = ParameterValidator(config)
        self.error_handler = ErrorHandler(config)
        self.tools = self._register_tools()
    
    def _register_tools(self) -> Dict[str, Callable]:
        """注册可用的工具函数"""
        return {
            "preview_parquet_in_pd": preview_parquet_in_pd,
            "get_data_from_parquet": get_data_from_parquet,
            "attempt_completion": self._handle_completion
        }
    
    def _handle_completion(self, result: str) -> Dict[str, Any]:
        """处理完成任务的工具调用"""
        try:
            self.loggers['diagnosis'].info("尝试完成任务，解析结果...")
            
            # 尝试解析JSON结果
            result_data = json.loads(result)
            
            # 验证必需字段
            required_fields = ["uuid", "component", "reason", "time", "reasoning_trace"]
            for field in required_fields:
                if field not in result_data:
                    error_msg = f"缺少必需字段: {field}"
                    self.loggers['diagnosis'].error(error_msg)
                    return {
                        "status": "error",
                        "error": error_msg,
                        "raw_result": result
                    }
            
            # 验证reasoning_trace格式
            if not isinstance(result_data["reasoning_trace"], list):
                error_msg = "reasoning_trace必须是数组"
                self.loggers['diagnosis'].error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "raw_result": result
                }
            
            for i, step in enumerate(result_data["reasoning_trace"]):
                if not isinstance(step, dict) or "step" not in step or "action" not in step or "observation" not in step:
                    error_msg = f"reasoning_trace第{i+1}步格式错误，需要包含step、action、observation字段"
                    self.loggers['diagnosis'].error(error_msg)
                    return {
                        "status": "error",
                        "error": error_msg,
                        "raw_result": result
                    }
            
            self.loggers['diagnosis'].info("任务完成，结果格式验证通过")
            return {
                "status": "completed",
                "result": result_data,
                "message": "故障诊断完成，结果格式验证通过"
            }
            
        except json.JSONDecodeError as e:
            error_msg = f"JSON解析失败: {str(e)}"
            self.loggers['diagnosis'].error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "raw_result": result
            }
    
    def execute_tool(self, tool_call: ToolCall, case_error_logger: logging.Logger = None) -> Dict[str, Any]:
        """
        增强的工具执行，支持智能错误处理和自动回退
        
        Args:
            tool_call: 工具调用对象
            case_error_logger: 案例特定的错误日志记录器
            
        Returns:
            工具执行结果
        """
        start_time = datetime.now()
        
        if tool_call.name not in self.tools:
            error_result = {
                "error": f"未知工具: {tool_call.name}",
                "available_tools": list(self.tools.keys())
            }
            self._log_tool_execution(tool_call, error_result)
            return error_result
        
        # 参数验证和修正
        try:
            validated_params = self.validator.validate_tool_parameters(tool_call.name, tool_call.parameters)
            tool_call.parameters = validated_params
        except Exception as e:
            self.loggers['tool'].warning(f"参数验证失败: {e}")
        
        try:
            tool_func = self.tools[tool_call.name]
            result = tool_func(**tool_call.parameters)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._log_tool_execution(tool_call, result, execution_time)
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_str = str(e)
            
            # 智能错误处理：针对不同错误类型提供自动回退策略
            if self.error_handler.should_use_filter_fallback(tool_call.name, error_str):
                # 过滤器错误 - 尝试自动回退策略
                self.loggers['diagnosis'].warning(f"检测到过滤器错误，尝试自动回退: {e}")
                
                fallback_result = self.error_handler.handle_filter_error_fallback(
                    tool_call.name, tool_call.parameters, e, self.tools
                )
                if fallback_result:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    self._log_tool_execution(tool_call, fallback_result, execution_time)
                    return fallback_result
            
            # 标准错误处理
            error_result = {
                "error": f"工具执行失败: {error_str}",
                "tool": tool_call.name,
                "parameters": tool_call.parameters,
                "suggestion": self.error_handler.get_error_suggestion(tool_call.name, error_str)
            }
            
            self._log_tool_execution(tool_call, error_result, execution_time)
            self.error_handler.log_error_with_context(e, f"执行工具 {tool_call.name}", case_error_logger=case_error_logger)
            
            return error_result
    
    def _log_tool_execution(self, tool_call: ToolCall, result: Dict[str, Any], execution_time: float = 0):
        """记录工具执行，安全处理JSON序列化"""
        self.loggers['tool'].info(f"执行工具: {tool_call.name}")
        
        # 安全的参数序列化
        try:
            safe_params = self._json_serialize_safe(tool_call.parameters)
            self.loggers['tool'].info(f"参数: {json.dumps(safe_params, ensure_ascii=False, indent=2)}")
        except Exception as e:
            self.loggers['tool'].info(f"参数: {str(tool_call.parameters)} (JSON序列化失败: {e})")
        
        if "error" in result:
            self.loggers['tool'].error(f"工具执行失败: {result['error']}")
        else:
            self.loggers['tool'].info(f"工具执行成功")
            if "data" in result:
                self.loggers['tool'].info(f"数据条数: {len(result['data'])}")
                self.loggers['tool'].info(f"数据形状: {result.get('shape', 'N/A')}")
        
        if execution_time > 0:
            self.loggers['tool'].info(f"执行时间: {execution_time:.2f}秒")
        
        self.loggers['tool'].info("-" * 40)
    
    def _json_serialize_safe(self, obj: Any) -> Any:
        """
        安全的JSON序列化，处理numpy数组等特殊类型
        
        Args:
            obj: 要序列化的对象
            
        Returns:
            可序列化的对象
        """
        import numpy as np
        
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, dict):
            return {key: self._json_serialize_safe(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._json_serialize_safe(item) for item in obj]
        elif isinstance(obj, tuple):
            return [self._json_serialize_safe(item) for item in obj]
        else:
            return obj
    
    def format_tool_result(self, tool_call: ToolCall, result: Dict[str, Any]) -> str:
        """
        格式化工具执行结果为文本，智能压缩大型结果
        
        Args:
            tool_call: 工具调用对象
            result: 工具执行结果
            
        Returns:
            格式化的结果文本
        """
        formatted_result = f"=== Tool Execution Result: {tool_call.name} ===\n"
        
        # 格式化结果
        if "error" in result:
            formatted_result += f"❌ Tool execution failed: {result['error']}\n"
            formatted_result += f"<tool_result>\n{result}\n</tool_result>\n"
        else:
            # 成功执行
            if tool_call.name == "attempt_completion":
                # 只有attempt_completion需要JSON格式处理
                formatted_result += f"✅ {result.get('message', 'Task completed')}\n"
                if "result" in result:
                    formatted_result += f"Result: {json.dumps(result['result'], ensure_ascii=False, indent=2)}\n"
            else:
                formatted_result += f"✅ Tool execution successful\n"
                formatted_result += f"<tool_result>\n{result}\n</tool_result>\n"
        
        return formatted_result
