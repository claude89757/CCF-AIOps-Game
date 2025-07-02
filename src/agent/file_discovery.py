#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: 文件发现器 - 适配预处理后的数据结构
"""

import os
import re
import glob
import logging
from datetime import datetime
from typing import List, Dict

from ..config import AgentConfig


class FileDiscovery:
    """文件发现器 - 负责从故障描述中发现相关文件"""
    
    def __init__(self, config: AgentConfig, loggers: Dict[str, logging.Logger]):
        self.config = config
        self.loggers = loggers
    
    def discover_relevant_files(self, description: str, debug: bool = False) -> str:
        """
        从故障描述中提取时间窗口并发现相关文件
        现在数据已预处理，时间戳和文件夹日期一致（UTC时区）
        
        Args:
            description: 故障描述
            debug: 是否显示调试信息
            
        Returns:
            包含文件信息的字符串
        """
        try:
            self.loggers['diagnosis'].info("Start discovering relevant files...")
            
            # 使用正则表达式提取时间信息
            time_pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)'
            times = re.findall(time_pattern, description)
            
            if len(times) >= 2:
                start_time = times[0]
                end_time = times[1]
                
                self.loggers['diagnosis'].info(f"Extracted time window: {start_time} to {end_time}")
                
                # 解析时间并提取日期
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                start_date = start_dt.strftime('%Y-%m-%d')
                end_date = end_dt.strftime('%Y-%m-%d')
                
                return self._discover_files_for_date_range(start_date, end_date, start_time, end_time)
                
            else:
                # 如果无法提取时间，尝试提取日期
                date_pattern = r'(\d{4}-\d{2}-\d{2})'
                dates = re.findall(date_pattern, description)
                
                if dates:
                    target_date = dates[0]
                    return self._discover_files_for_single_date(target_date)
        
        except Exception as e:
            self.loggers['diagnosis'].error(f"File discovery failed: {e}")
            return f"⚠️ Unable to automatically discover files: {str(e)}. Please manually use preview_parquet_in_pd tool to explore data structure."
        
        return "⚠️ Unable to extract time information from description. Please manually use preview_parquet_in_pd tool to explore data structure."
    
    def _discover_files_for_date_range(self, start_date: str, end_date: str, start_time: str, end_time: str) -> str:
        """发现日期范围内的相关文件"""
        # 发现相关文件
        log_files = []
        metric_files = []
        trace_files = []
        
        # 获取所有可用日期
        available_dates = self._get_available_dates()
        
        # 检查目标日期数据是否存在
        processed_data_dir = f"{self.config.data_base_path}/processed_data/{start_date}"
        if not os.path.exists(processed_data_dir):
            # 智能选择最接近的日期
            if available_dates:
                best_match_date = self._find_best_matching_date(start_date, available_dates)
                self.loggers['diagnosis'].warning(f"Target date {start_date} has no data, using closest available date: {best_match_date}")
                
                # 调整时间窗口到匹配日期
                adjusted_start = start_time.replace(start_date, best_match_date)
                adjusted_end = end_time.replace(start_date, best_match_date)
                
                return f"""⚠️ **Time data matching problem automatically corrected**
Target date: {start_date} (data does not exist)
Adjusted to: {best_match_date} (closest available date)
Adjusted time window: {adjusted_start} to {adjusted_end}

💡 **Analysis suggestions**:
1. Use the adjusted time window for analysis
2. Data is now UTC-aligned, so timestamps match folder dates
3. Focus on fault patterns rather than specific time points

Available dates: {', '.join(available_dates)}
Recommended data directory: {self.config.data_base_path}/processed_data/{best_match_date}/"""
            else:
                return "⚠️ No monitoring data found."
        
        # 发现具体文件
        log_files, metric_files, trace_files = self._scan_files_in_directory(processed_data_dir)
        
        self.loggers['diagnosis'].info(f"Found {len(log_files)} logs, {len(metric_files)} metrics, {len(trace_files)} traces")
        
        # 格式化文件信息
        return self._format_file_info(start_time, end_time, start_date, log_files, metric_files, trace_files)
    
    def _discover_files_for_single_date(self, target_date: str) -> str:
        """发现单个日期的相关文件"""
        self.loggers['diagnosis'].info(f"提取到日期: {target_date}")
        
        # 检查该日期的数据是否存在
        processed_data_dir = f"{self.config.data_base_path}/processed_data/{target_date}"
        if not os.path.exists(processed_data_dir):
            # 查找可用的日期
            available_dates = self._get_available_dates()
            
            if available_dates:
                available_dates = sorted(available_dates)
                return f"⚠️ Date {target_date} has no data. Available dates: {', '.join(available_dates)}"
            else:
                return "⚠️ No monitoring data found."
        
        return f"## Available monitoring data files\nTarget date: {target_date}\n💡 Tip: Use preview_parquet_in_pd tool to explore specific files."
    
    def _get_available_dates(self) -> List[str]:
        """获取所有可用的数据日期"""
        available_dates = []
        pattern = f"{self.config.data_base_path}/processed_data/2025-*"
        for date_dir in glob.glob(pattern):
            if os.path.isdir(date_dir):
                date_name = os.path.basename(date_dir)
                available_dates.append(date_name)
        return sorted(available_dates)
    
    def _find_best_matching_date(self, target_date: str, available_dates: List[str]) -> str:
        """智能寻找最佳匹配的数据日期"""
        try:
            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
            available_dts = []
            
            for date_str in available_dates:
                try:
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                    available_dts.append((dt, date_str))
                except:
                    continue
            
            if not available_dts:
                return available_dates[0] if available_dates else target_date
            
            # 找到时间差最小的日期
            best_match = min(available_dts, key=lambda x: abs((x[0] - target_dt).days))
            return best_match[1]
            
        except:
            return available_dates[0] if available_dates else target_date
    
    def _scan_files_in_directory(self, data_dir: str) -> tuple:
        """扫描目录中的文件 - 适配新的数据结构"""
        log_files = []
        metric_files = []
        trace_files = []
        
        # 发现日志文件
        log_pattern = f"{data_dir}/log-parquet/*.parquet"
        log_files = sorted(glob.glob(log_pattern))
        
        # 发现调用链文件
        trace_pattern = f"{data_dir}/trace-parquet/*.parquet"
        trace_files = sorted(glob.glob(trace_pattern))
        
        # 发现指标文件 - 新的扁平化结构
        # APM指标
        apm_pattern = f"{data_dir}/apm/*.parquet"
        metric_files.extend(glob.glob(apm_pattern))
        
        # Pod指标
        pod_pattern = f"{data_dir}/pod/*.parquet"
        metric_files.extend(glob.glob(pod_pattern))
        
        # Service指标
        service_pattern = f"{data_dir}/service/*.parquet"
        metric_files.extend(glob.glob(service_pattern))
        
        # 基础设施指标
        infra_patterns = [
            f"{data_dir}/infra_node/*.parquet",
            f"{data_dir}/infra_pod/*.parquet",
            f"{data_dir}/infra_tidb/*.parquet"
        ]
        for pattern in infra_patterns:
            metric_files.extend(glob.glob(pattern))
        
        # 其他指标
        other_pattern = f"{data_dir}/other/*.parquet"
        metric_files.extend(glob.glob(other_pattern))
        
        metric_files = sorted(metric_files)
        
        return log_files, metric_files, trace_files
    
    def _format_file_info(self, start_time: str, end_time: str, start_date: str, 
                         log_files: List[str], metric_files: List[str], trace_files: List[str]) -> str:
        """格式化文件信息"""
        file_info_parts = [
            "## Available monitoring data files (UTC-aligned)",
            f"Time window: {start_time} to {end_time}",
            f"Related date: {start_date}",
            f"File statistics: {len(log_files)} logs, {len(metric_files)} metrics, {len(trace_files)} traces"
        ]
        
        if log_files:
            file_info_parts.append("\n### Log files:")
            for log_file in log_files[:self.config.preview_rows]:
                file_info_parts.append(f"- {log_file}")
            if len(log_files) > self.config.preview_rows:
                file_info_parts.append(f"- ... and {len(log_files) - self.config.preview_rows} more logs")
        
        if trace_files:
            file_info_parts.append("\n### Trace files:")
            for trace_file in trace_files[:self.config.preview_rows]:
                file_info_parts.append(f"- {trace_file}")
            if len(trace_files) > self.config.preview_rows:
                file_info_parts.append(f"- ... and {len(trace_files) - self.config.preview_rows} more traces")
        
        if metric_files:
            file_info_parts.append("\n### Metric files:")
            # 按类型分组显示指标文件
            metric_groups = self._group_metric_files(metric_files)
            for group_name, files in metric_groups.items():
                file_info_parts.append(f"\n#### {group_name} ({len(files)} files):")
                for file in files[:3]:  # 每组显示前3个文件
                    file_info_parts.append(f"- {file}")
                if len(files) > 3:
                    file_info_parts.append(f"- ... and {len(files) - 3} more")
        
        file_info_parts.append("\n💡 **Data is now UTC-aligned**: Timestamps in files match folder dates")
        file_info_parts.append("💡 **Next steps**: Use preview_parquet_in_pd tool to preview file structure, then use get_data_from_parquet to get specific data.")
        
        return "\n".join(file_info_parts)
    
    def _group_metric_files(self, metric_files: List[str]) -> Dict[str, List[str]]:
        """将指标文件按类型分组"""
        groups = {
            "APM Metrics": [],
            "Pod Metrics": [],
            "Service Metrics": [],
            "Infrastructure Node": [],
            "Infrastructure Pod": [],
            "Infrastructure TiDB": [],
            "Other Metrics": []
        }
        
        for file in metric_files:
            if "/apm/" in file:
                groups["APM Metrics"].append(file)
            elif "/pod/" in file:
                groups["Pod Metrics"].append(file)
            elif "/service/" in file:
                groups["Service Metrics"].append(file)
            elif "/infra_node/" in file:
                groups["Infrastructure Node"].append(file)
            elif "/infra_pod/" in file:
                groups["Infrastructure Pod"].append(file)
            elif "/infra_tidb/" in file:
                groups["Infrastructure TiDB"].append(file)
            elif "/other/" in file:
                groups["Other Metrics"].append(file)
        
        # 移除空组
        return {k: v for k, v in groups.items() if v} 