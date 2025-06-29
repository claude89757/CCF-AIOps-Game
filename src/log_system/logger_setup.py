#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: 日志系统配置管理
"""

import os
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict


class LoggerSetup:
    """日志系统配置类"""
    
    def __init__(self, base_dir: str = "src/logs"):
        self.base_dir = Path(base_dir)
        self.setup_directories()
        self.loggers = {}
        self.setup_loggers()
    
    def setup_directories(self):
        """创建日志目录结构"""
        directories = [
            self.base_dir / "diagnosis",        # 诊断过程日志
            self.base_dir / "errors",           # 错误日志
            self.base_dir / "interactions",     # 智能体交互日志
            self.base_dir / "tools",            # 工具执行日志
            self.base_dir / "summary",          # 总结日志
            self.base_dir / "llm_interactions", # 大模型原始交互日志
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def setup_loggers(self):
        """设置不同类型的日志记录器"""
        # 获取当前时间用于文件命名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 主诊断日志
        self.loggers['diagnosis'] = self._create_logger(
            'diagnosis',
            self.base_dir / "diagnosis" / f"diagnosis_{timestamp}.log",
            level=logging.INFO
        )
        
        # 错误日志
        self.loggers['error'] = self._create_logger(
            'error',
            self.base_dir / "errors" / f"errors_{timestamp}.log",
            level=logging.ERROR
        )
        
        # 交互日志 - 设为DEBUG级别以记录详细信息
        self.loggers['interaction'] = self._create_logger(
            'interaction',
            self.base_dir / "interactions" / f"interactions_{timestamp}.log",
            level=logging.DEBUG
        )
        
        # 工具日志
        self.loggers['tool'] = self._create_logger(
            'tool',
            self.base_dir / "tools" / f"tools_{timestamp}.log",
            level=logging.INFO
        )
        
        # 总结日志
        self.loggers['summary'] = self._create_logger(
            'summary',
            self.base_dir / "summary" / f"summary_{timestamp}.log",
            level=logging.INFO
        )
        
        # 大模型原始交互日志
        self.loggers['llm_interactions'] = self._create_logger(
            'llm_interactions',
            self.base_dir / "llm_interactions" / f"llm_interactions_{timestamp}.log",
            level=logging.INFO
        )
    
    def _create_logger(self, name: str, log_file: Path, level=logging.INFO):
        """创建单个日志记录器"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
            
        # 文件处理器 - 总是使用指定级别记录到文件
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        
        # 控制台处理器 - 设置为最高级别，让所有日志都只记录到文件
        console_handler = logging.StreamHandler(sys.stdout)
        # 设置为CRITICAL级别，这样日志信息不会在控制台显示
        # 所有详细信息都记录到文件中
        console_handler.setLevel(logging.CRITICAL + 1)  # 设置为超过CRITICAL的级别，不显示任何日志
        
        # 格式器 - 对于LLM交互日志使用更简洁的格式
        if name == 'llm_interactions':
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def create_case_error_logger(self, uuid: str):
        """为特定案例创建错误日志记录器"""
        case_error_file = self.base_dir / "errors" / f"case_{uuid}_error.log"
        return self._create_logger(f'case_error_{uuid}', case_error_file, level=logging.ERROR) 