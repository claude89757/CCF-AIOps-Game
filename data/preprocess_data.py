#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据预处理脚本 - 解决时区不一致问题
处理parquet文件中的时区转换和数据重组
优化版本：按组件分组处理，避免去重操作，内存优化版本
"""

import os
import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import shutil
from typing import Dict, List, Tuple
import logging
from tqdm import tqdm
import gc
from collections import defaultdict
import traceback

# 设置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataPreprocessor:
    def __init__(self, source_dir: str = ".", target_dir: str = "processed_data", batch_size: int = 10):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.cst_tz = pytz.timezone('Asia/Shanghai')  # CST时区
        self.utc_tz = pytz.UTC  # UTC时区
        self.batch_size = batch_size  # 批处理大小，减少内存使用
        
        # 统计信息
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'total_records': 0
        }
        
        # 确保目标目录存在
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)
        self.target_dir.mkdir(exist_ok=True)
    
    def parse_timestamp_column(self, df: pd.DataFrame, timestamp_col: str) -> pd.DataFrame:
        """解析时间戳列并转换为UTC日期"""
        df_copy = df.copy()
        
        try:
            if timestamp_col == 'startTimeMillis':
                # 调用链数据：毫秒时间戳
                df_copy['timestamp'] = pd.to_datetime(df_copy[timestamp_col], unit='ms', utc=True)
            elif timestamp_col in ['@timestamp', 'timestamp', 'time']:
                # 日志和指标数据：ISO格式时间字符串
                df_copy['timestamp'] = pd.to_datetime(df_copy[timestamp_col], utc=True)
            else:
                # 尝试自动解析
                df_copy['timestamp'] = pd.to_datetime(df_copy[timestamp_col], utc=True)
            
            # 添加UTC日期列
            df_copy['utc_date'] = df_copy['timestamp'].dt.date.astype(str)
            return df_copy
        except Exception as e:
            logger.error(f"解析时间戳列 {timestamp_col} 时出错: {e}")
            raise
    
    def identify_timestamp_column(self, df: pd.DataFrame) -> str:
        """识别时间戳列"""
        possible_cols = ['@timestamp', 'timestamp', 'startTimeMillis', 'time']
        for col in possible_cols:
            if col in df.columns:
                return col
        
        # 如果没有找到，尝试查找包含时间相关词的列
        for col in df.columns:
            if any(time_word in col.lower() for time_word in ['time', 'timestamp', 'date']):
                return col
        
        raise ValueError(f"无法识别时间戳列，可用列: {list(df.columns)}")
    
    def collect_file_groups(self) -> Dict[str, List[Path]]:
        """按组件分组收集文件"""
        file_groups = defaultdict(list)
        
        for date_folder in self.source_dir.iterdir():
            if not date_folder.is_dir() or not date_folder.name.startswith('2025-'):
                continue
            
            # 收集log文件
            log_folder = date_folder / "log-parquet"
            if log_folder.exists():
                for file_path in log_folder.glob("*.parquet"):
                    file_groups['log'].append(file_path)
            
            # 收集trace文件
            trace_folder = date_folder / "trace-parquet"
            if trace_folder.exists():
                for file_path in trace_folder.glob("*.parquet"):
                    file_groups['trace'].append(file_path)
            
            # 收集metric文件，按具体文件名分组
            metric_folder = date_folder / "metric-parquet"
            if metric_folder.exists():
                for file_path in metric_folder.rglob("*.parquet"):
                    # 使用相对路径作为组键，移除日期部分
                    relative_path = file_path.relative_to(date_folder)
                    # 移除文件名中的日期部分来创建组键
                    group_key = str(relative_path).replace(date_folder.name, "DATE_PLACEHOLDER")
                    file_groups[f"metric_{group_key}"].append(file_path)
        
        return file_groups
    
    def write_utc_data(self, utc_date_data: Dict[str, List], component_type: str):
        """将UTC日期数据写入文件"""
        for utc_date, dfs in utc_date_data.items():
            if not dfs:
                continue
            
            # 合并同一UTC日期的所有数据
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # 按时间戳排序
            timestamp_col = self.identify_timestamp_column(combined_df)
            combined_df = combined_df.sort_values(timestamp_col).reset_index(drop=True)
            
            # 创建目标文件夹
            target_folder = self.target_dir / utc_date / f"{component_type}-parquet"
            target_folder.mkdir(parents=True, exist_ok=True)
            
            # 生成输出文件名
            if component_type == 'log':
                output_filename = f"log_filebeat-server_{utc_date}.parquet"
            else:  # trace
                output_filename = f"trace_jaeger-span_{utc_date}.parquet"
            
            output_path = target_folder / output_filename
            
            # 如果文件已存在，需要合并数据
            if output_path.exists():
                existing_df = pd.read_parquet(output_path)
                combined_df = pd.concat([existing_df, combined_df], ignore_index=True)
                # 重新排序
                combined_df = combined_df.sort_values(timestamp_col).reset_index(drop=True)
                del existing_df
                gc.collect()
            
            combined_df.to_parquet(output_path, index=False)
            
            self.stats['total_records'] += len(combined_df)
            logger.info(f"保存 {component_type} 文件: {output_path} ({len(combined_df)} 条记录)")
            
            # 释放内存
            del combined_df
            gc.collect()
    
    def process_log_trace_group(self, component_type: str, files: List[Path]):
        """处理日志或调用链文件组 - 内存优化版本"""
        logger.info(f"处理 {component_type} 组件，共 {len(files)} 个文件，批处理大小: {self.batch_size}")
        
        # 分批处理文件
        for i in range(0, len(files), self.batch_size):
            batch_files = files[i:i + self.batch_size]
            logger.info(f"处理批次 {i//self.batch_size + 1}/{(len(files) + self.batch_size - 1)//self.batch_size}，"
                       f"文件 {i+1}-{min(i+self.batch_size, len(files))}")
            
            # 按UTC日期分组收集当前批次数据
            utc_date_data = defaultdict(list)
            
            for file_path in tqdm(batch_files, desc=f"读取{component_type}文件", leave=False):
                try:
                    # 读取parquet文件
                    df = pd.read_parquet(file_path)
                    
                    if df.empty:
                        logger.warning(f"文件为空: {file_path.name}")
                        continue
                    
                    # 识别时间戳列
                    timestamp_col = self.identify_timestamp_column(df)
                    
                    # 解析时间戳并添加UTC日期
                    df_with_date = self.parse_timestamp_column(df, timestamp_col)
                    
                    # 按UTC日期分组
                    for utc_date, group_df in df_with_date.groupby('utc_date'):
                        clean_df = group_df.drop(['utc_date'], axis=1)
                        utc_date_data[utc_date].append(clean_df)
                    
                    self.stats['processed_files'] += 1
                    
                    # 释放内存
                    del df, df_with_date
                    gc.collect()
                    
                except Exception as e:
                    logger.error(f"处理文件 {file_path.name} 时出错: {e}")
                    self.stats['failed_files'] += 1
                    continue
            
            # 写入当前批次的数据
            self.write_utc_data(utc_date_data, component_type)
            
            # 清理当前批次数据
            del utc_date_data
            gc.collect()
    
    def write_metric_data(self, utc_date_data: Dict[str, List], group_key: str):
        """写入指标数据"""
        for utc_date, data_list in utc_date_data.items():
            if not data_list:
                continue
            
            # 合并同一UTC日期的所有数据
            dfs = [item[0] for item in data_list]
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # 按时间戳排序
            timestamp_col = self.identify_timestamp_column(combined_df)
            combined_df = combined_df.sort_values(timestamp_col).reset_index(drop=True)
            
            # 使用第一个文件的路径信息来确定输出路径
            _, original_date, sample_file = data_list[0]
            
            # 计算相对路径
            metric_folder = sample_file.parent.parent  # metric-parquet文件夹
            relative_path = sample_file.relative_to(metric_folder)
            target_path = self.target_dir / utc_date / relative_path
            
            # 创建目标文件夹
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 修改文件名中的日期为UTC日期
            new_filename = sample_file.name.replace(original_date, utc_date)
            output_path = target_path.parent / new_filename
            
            # 如果文件已存在，需要合并数据
            if output_path.exists():
                existing_df = pd.read_parquet(output_path)
                combined_df = pd.concat([existing_df, combined_df], ignore_index=True)
                # 重新排序
                combined_df = combined_df.sort_values(timestamp_col).reset_index(drop=True)
                del existing_df
                gc.collect()
            
            # 保存文件
            combined_df.to_parquet(output_path, index=False)
            
            self.stats['total_records'] += len(combined_df)
            logger.info(f"保存指标文件: {output_path} ({len(combined_df)} 条记录)")
            
            # 释放内存
            del combined_df
            gc.collect()
    
    def process_metric_group(self, group_key: str, files: List[Path]):
        """处理指标文件组 - 内存优化版本"""
        logger.info(f"处理指标组件 {group_key}，共 {len(files)} 个文件，批处理大小: {self.batch_size}")
        
        # 分批处理文件
        for i in range(0, len(files), self.batch_size):
            batch_files = files[i:i + self.batch_size]
            logger.info(f"处理批次 {i//self.batch_size + 1}/{(len(files) + self.batch_size - 1)//self.batch_size}，"
                       f"文件 {i+1}-{min(i+self.batch_size, len(files))}")
            
            # 按UTC日期分组收集当前批次数据
            utc_date_data = defaultdict(list)
            
            for file_path in batch_files:
                try:
                    # 读取parquet文件
                    df = pd.read_parquet(file_path)
                    
                    if df.empty:
                        logger.warning(f"文件为空: {file_path.name}")
                        continue
                    
                    # 获取原始日期
                    original_date = file_path.parent.parent.parent.name  # 从路径中提取日期
                    
                    # 识别时间戳列
                    timestamp_col = self.identify_timestamp_column(df)
                    
                    # 解析时间戳并添加UTC日期
                    df_with_date = self.parse_timestamp_column(df, timestamp_col)
                    
                    # 按UTC日期分组
                    for utc_date, group_df in df_with_date.groupby('utc_date'):
                        clean_df = group_df.drop(['utc_date'], axis=1)
                        utc_date_data[utc_date].append((clean_df, original_date, file_path))
                    
                    self.stats['processed_files'] += 1
                    
                    # 释放内存
                    del df, df_with_date
                    gc.collect()
                    
                except Exception as e:
                    logger.error(f"处理文件 {file_path.name} 时出错: {e}")
                    self.stats['failed_files'] += 1
                    continue
            
            # 写入当前批次的数据
            self.write_metric_data(utc_date_data, group_key)
            
            # 清理当前批次数据
            del utc_date_data
            gc.collect()
    
    def process_all_data(self):
        """处理所有数据"""
        logger.info("开始数据预处理...")
        
        # 收集文件分组
        logger.info("收集文件分组...")
        file_groups = self.collect_file_groups()
        
        # 统计总文件数
        total_files = sum(len(files) for files in file_groups.values())
        self.stats['total_files'] = total_files
        logger.info(f"总共需要处理 {total_files} 个文件，分为 {len(file_groups)} 个组")
        
        try:
            # 处理日志文件组
            if 'log' in file_groups:
                self.process_log_trace_group('log', file_groups['log'])
                gc.collect()  # 强制垃圾回收
            
            # 处理调用链文件组
            if 'trace' in file_groups:
                self.process_log_trace_group('trace', file_groups['trace'])
                gc.collect()  # 强制垃圾回收
            
            # 处理指标文件组
            for group_key, files in file_groups.items():
                if group_key.startswith('metric_'):
                    self.process_metric_group(group_key, files)
                    gc.collect()  # 强制垃圾回收
        
        except KeyboardInterrupt:
            logger.info("用户中断处理")
            raise
        except Exception as e:
            logger.error(f"处理过程中发生错误: {e}")
            logger.error(traceback.format_exc())
            raise
        
        logger.info("数据预处理完成！")
        self.print_summary()
    
    def print_summary(self):
        """打印处理摘要"""
        logger.info("=" * 50)
        logger.info("处理摘要:")
        logger.info(f"总文件数: {self.stats['total_files']}")
        logger.info(f"成功处理: {self.stats['processed_files']}")
        logger.info(f"失败文件: {self.stats['failed_files']}")
        logger.info(f"总记录数: {self.stats['total_records']}")
        if self.stats['total_files'] > 0:
            logger.info(f"成功率: {self.stats['processed_files']/self.stats['total_files']*100:.2f}%")
        logger.info("=" * 50)
    
    def verify_data_integrity(self):
        """验证数据完整性"""
        logger.info("验证数据完整性...")
        
        # 统计原始数据
        original_stats = self._count_stats_recursive(self.source_dir)
        processed_stats = self._count_stats_recursive(self.target_dir)
        
        logger.info(f"原始数据: {original_stats['files']} 文件, {original_stats['size']/(1024**3):.2f} GB")
        logger.info(f"处理后数据: {processed_stats['files']} 文件, {processed_stats['size']/(1024**3):.2f} GB")
        
        return original_stats, processed_stats
    
    def _count_stats_recursive(self, folder: Path) -> Dict[str, int]:
        """递归统计文件统计信息"""
        stats = {'files': 0, 'size': 0}
        
        for item in folder.rglob('*.parquet'):
            stats['files'] += 1
            stats['size'] += item.stat().st_size
        
        return stats


def main():
    """主函数"""
    logger.info("数据预处理脚本启动")
    
    # 创建预处理器实例，使用较小的批处理大小以减少内存使用
    batch_size = 5  # 减少批处理大小
    preprocessor = DataPreprocessor(batch_size=batch_size)
    
    try:
        # 处理所有数据
        preprocessor.process_all_data()
        
        # 验证数据完整性
        preprocessor.verify_data_integrity()
        
        logger.info("所有任务完成！")
        
    except KeyboardInterrupt:
        logger.info("用户中断处理")
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
