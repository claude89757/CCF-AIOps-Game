#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: 上下文管理器
"""

import logging
from typing import Dict, Any, List

from ..config import AgentConfig


class ContextManager:
    """上下文管理器 - 负责管理模型对话上下文长度"""
    
    def __init__(self, config: AgentConfig, loggers: Dict[str, logging.Logger], max_context_length: int):
        self.config = config
        self.loggers = loggers
        
        # 计算上下文限制
        limits = config.get_context_limits(max_context_length)
        self.max_context_tokens = limits["max_context_tokens"]
        self.context_compress_threshold = limits["context_compress_threshold"]
        self.max_tool_result_tokens = limits["max_tool_result_tokens"]
    
    def estimate_message_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """估算消息列表的token数量"""
        total_chars = 0
        for msg in messages:
            total_chars += len(str(msg.get('content', '')))
        return total_chars // self.config.token_estimation_ratio
    
    def manage_context_length(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """智能管理上下文长度，避免超限"""
        current_tokens = self.estimate_message_tokens(messages)
        
        if current_tokens <= self.context_compress_threshold:
            return messages
        
        self.loggers['diagnosis'].warning(f"上下文接近限制({current_tokens}tokens)，开始压缩...")
        
        # 保留系统提示和最近的用户消息
        if len(messages) < 4:
            return messages
        
        # 保留前2条消息（系统提示+初始任务）
        preserved_messages = messages[:2]
        recent_messages = messages[-4:]  # 保留最近4条消息
        
        # 压缩中间的历史消息
        middle_messages = messages[2:-4]
        if middle_messages:
            # 提取关键步骤信息
            compressed_history = self._extract_key_analysis_steps(middle_messages)
            preserved_messages.append({
                "role": "assistant",
                "content": f"[历史分析压缩]: {compressed_history}"
            })
        
        # 组合最终消息
        final_messages = preserved_messages + recent_messages
        
        final_tokens = self.estimate_message_tokens(final_messages)
        self.loggers['diagnosis'].info(f"上下文压缩完成: {current_tokens} -> {final_tokens} tokens")
        
        return final_messages
    
    def _extract_key_analysis_steps(self, messages: List[Dict[str, Any]]) -> str:
        """从历史消息中提取关键分析步骤"""
        key_info = []
        
        for msg in messages:
            content = msg.get('content', '')
            # 提取工具调用和关键发现
            if 'preview_parquet_in_pd' in content:
                key_info.append("数据结构探索")
            elif 'get_data_from_parquet' in content:
                key_info.append("数据查询")
            elif 'error' in content.lower():
                key_info.append("遇到错误")
            elif 'completed' in content:
                key_info.append("步骤完成")
        
        return f"已完成{len(key_info)}个分析步骤: {', '.join(key_info[:5])}"
    
    def compress_for_context_limit(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """针对上下文长度错误进行更激进的压缩"""
        if len(messages) > 3:
            # 只保留系统提示和最近2条消息
            compressed = [messages[0]] + messages[-2:]
            self.loggers['error'].info(f"已压缩到{len(compressed)}条消息，继续重试...")
            return compressed
        else:
            # 已经压缩到最小，返回原消息
            return messages
    
    def should_compress_context(self, messages: List[Dict[str, Any]]) -> bool:
        """判断是否需要压缩上下文"""
        current_tokens = self.estimate_message_tokens(messages)
        return current_tokens > self.context_compress_threshold
    
    def get_context_status(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取当前上下文状态信息"""
        current_tokens = self.estimate_message_tokens(messages)
        
        return {
            "current_tokens": current_tokens,
            "max_tokens": self.max_context_tokens,
            "compress_threshold": self.context_compress_threshold,
            "usage_ratio": current_tokens / self.max_context_tokens,
            "needs_compression": current_tokens > self.context_compress_threshold,
            "message_count": len(messages)
        } 