#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-28
@description: CCF AIOps挑战赛 React模式故障诊断智能体
"""

import re
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Callable, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import os
import logging
import sys
from pathlib import Path

from src.model import ModelClient
from src.prompt import SYSTEM_PROMPT
from src.tools import preview_parquet_in_pd, get_data_from_parquet


@dataclass
class ToolCall:
    """工具调用数据结构"""
    name: str
    parameters: Dict[str, Any]


@dataclass
class AgentStep:
    """Agent执行步骤"""
    step_num: int
    action: str
    observation: str
    reasoning: Optional[str] = None


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
            self.base_dir / "diagnosis",    # 诊断过程日志
            self.base_dir / "errors",       # 错误日志
            self.base_dir / "interactions", # 智能体交互日志
            self.base_dir / "tools",        # 工具执行日志
            self.base_dir / "summary"       # 总结日志
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
        
        # 交互日志
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
    
    def _create_logger(self, name: str, log_file: Path, level=logging.INFO):
        """创建单个日志记录器"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
            
        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING if name == 'error' else logging.CRITICAL)
        
        # 格式器
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


class AIOpsReactAgent:
    """CCF AIOps挑战赛专用React模式故障诊断智能体"""
    
    def __init__(self, model_name: str = "deepseek-v3:671b", max_iterations: int = 15):
        """
        初始化Agent
        
        Args:
            model_name: 使用的模型名称
            max_iterations: 最大迭代次数，防止无限循环
        """
        # 初始化日志系统
        self.logger_setup = LoggerSetup()
        self.loggers = self.logger_setup.loggers
        
        self.model_client = ModelClient()
        self.model_name = model_name
        self.max_iterations = max_iterations
        
        # 注册工具函数
        self.tools = self._register_tools()
        
        # 记录执行步骤
        self.steps: List[AgentStep] = []
        self.current_step = 0
        
        # 比赛专用配置
        self.competition_mode = True
        
        # 当前案例的错误日志记录器
        self.case_error_logger = None
        
        # 记录初始化
        self.loggers['summary'].info("=== CCF AIOps智能体初始化完成 ===")
        self.loggers['summary'].info(f"模型: {model_name}")
        self.loggers['summary'].info(f"最大迭代次数: {max_iterations}")
        self.loggers['summary'].info(f"可用工具: {list(self.tools.keys())}")
    
    def _register_tools(self) -> Dict[str, Callable]:
        """注册可用的工具函数"""
        return {
            "preview_parquet_in_pd": preview_parquet_in_pd,
            "get_data_from_parquet": get_data_from_parquet,
            "attempt_completion": self._handle_completion
        }
    
    def _log_diagnosis_start(self, uuid: str, description: str):
        """记录诊断开始"""
        self.loggers['diagnosis'].info("=" * 80)
        self.loggers['diagnosis'].info(f"开始诊断故障案例: {uuid}")
        self.loggers['diagnosis'].info(f"故障描述: {description}")
        self.loggers['diagnosis'].info("=" * 80)
    
    def _log_diagnosis_step(self, step_num: int, action: str, observation: str, reasoning: str = ""):
        """记录诊断步骤"""
        self.loggers['diagnosis'].info(f"步骤 {step_num}:")
        self.loggers['diagnosis'].info(f"  行动: {action}")
        self.loggers['diagnosis'].info(f"  观察: {observation[:200]}{'...' if len(observation) > 200 else ''}")
        if reasoning:
            self.loggers['diagnosis'].info(f"  推理: {reasoning[:200]}{'...' if len(reasoning) > 200 else ''}")
        self.loggers['diagnosis'].info("-" * 40)
    
    def _log_tool_execution(self, tool_call: ToolCall, result: Dict[str, Any], execution_time: float = 0):
        """记录工具执行"""
        self.loggers['tool'].info(f"执行工具: {tool_call.name}")
        self.loggers['tool'].info(f"参数: {json.dumps(tool_call.parameters, ensure_ascii=False, indent=2)}")
        
        if "error" in result:
            self.loggers['tool'].error(f"工具执行失败: {result['error']}")
            # 同时记录到错误日志
            if self.case_error_logger:
                self.case_error_logger.error(f"工具执行失败 - {tool_call.name}: {result['error']}")
        else:
            self.loggers['tool'].info(f"工具执行成功")
            if "data" in result:
                self.loggers['tool'].info(f"数据条数: {len(result['data'])}")
                self.loggers['tool'].info(f"数据形状: {result.get('shape', 'N/A')}")
        
        if execution_time > 0:
            self.loggers['tool'].info(f"执行时间: {execution_time:.2f}秒")
        
        self.loggers['tool'].info("-" * 40)
    
    def _log_model_interaction(self, iteration: int, messages_count: int, response_length: int):
        """记录模型交互"""
        self.loggers['interaction'].info(f"第 {iteration} 轮模型交互")
        self.loggers['interaction'].info(f"消息数量: {messages_count}")
        self.loggers['interaction'].info(f"响应长度: {response_length} 字符")
    
    def _log_error(self, error: Exception, context: str = "", uuid: str = ""):
        """记录错误信息"""
        import traceback
        
        error_msg = f"错误上下文: {context}\n错误信息: {str(error)}\n堆栈跟踪:\n{traceback.format_exc()}"
        
        self.loggers['error'].error(error_msg)
        
        # 如果有案例特定的错误日志记录器，也记录到那里
        if self.case_error_logger:
            self.case_error_logger.error(f"案例 {uuid} 错误: {error_msg}")
    
    def _discover_relevant_files(self, description: str, debug: bool = False) -> str:
        """
        从故障描述中提取时间窗口并发现相关文件
        
        Args:
            description: 故障描述
            debug: 是否显示调试信息
            
        Returns:
            包含文件信息的字符串
        """
        import re
        import glob
        from datetime import datetime
        
        try:
            self.loggers['diagnosis'].info("开始发现相关文件...")
            
            # 使用正则表达式提取时间信息
            time_pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)'
            times = re.findall(time_pattern, description)
            
            if len(times) >= 2:
                start_time = times[0]
                end_time = times[1]
                
                self.loggers['diagnosis'].info(f"提取到时间窗口: {start_time} to {end_time}")
                
                # 解析时间并提取日期
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                start_date = start_dt.strftime('%Y-%m-%d')
                end_date = end_dt.strftime('%Y-%m-%d')
                
                # 发现相关文件
                log_files = []
                metric_files = []
                trace_files = []
                
                # 检查目标日期数据是否存在
                data_dir = f"data/{start_date}"
                if not os.path.exists(data_dir):
                    # 查找可用的日期
                    available_dates = []
                    for date_dir in glob.glob("data/2025-*"):
                        if os.path.isdir(date_dir):
                            date_name = os.path.basename(date_dir)
                            available_dates.append(date_name)
                    
                    self.loggers['diagnosis'].warning(f"日期 {start_date} 无数据，可用日期: {available_dates}")
                    
                    if available_dates:
                        available_dates = sorted(available_dates)
                        return f"⚠️ 日期 {start_date} 无数据。可用日期: {', '.join(available_dates)}。建议使用最接近的日期数据进行分析。"
                    else:
                        return "⚠️ 未找到任何监控数据。"
                
                # 发现日志文件
                log_pattern = f"{data_dir}/log-parquet/*.parquet"
                log_files = sorted(glob.glob(log_pattern))
                
                # 发现调用链文件
                trace_pattern = f"{data_dir}/trace-parquet/*.parquet"
                trace_files = sorted(glob.glob(trace_pattern))
                
                # 发现指标文件（更复杂的结构）
                apm_patterns = [
                    f"{data_dir}/metric-parquet/apm/*.parquet",
                    f"{data_dir}/metric-parquet/apm/*/*.parquet"
                ]
                for pattern in apm_patterns:
                    metric_files.extend(glob.glob(pattern))
                
                infra_patterns = [
                    f"{data_dir}/metric-parquet/infra/*.parquet",
                    f"{data_dir}/metric-parquet/infra/*/*.parquet"
                ]
                for pattern in infra_patterns:
                    metric_files.extend(glob.glob(pattern))
                
                other_pattern = f"{data_dir}/metric-parquet/other/*.parquet"
                metric_files.extend(glob.glob(other_pattern))
                
                metric_files = sorted(metric_files)
                
                self.loggers['diagnosis'].info(f"发现文件: {len(log_files)} 日志, {len(metric_files)} 指标, {len(trace_files)} 调用链")
                
                # 格式化文件信息
                file_info_parts = [
                    "## 可用监控数据文件",
                    f"时间窗口: {start_time} to {end_time}",
                    f"相关日期: {start_date}",
                    f"文件统计: {len(log_files)} 个日志文件, {len(metric_files)} 个指标文件, {len(trace_files)} 个调用链文件"
                ]
                
                if log_files:
                    file_info_parts.append("\n### 日志文件:")
                    for log_file in log_files[:5]:  # 最多显示5个
                        file_info_parts.append(f"- {log_file}")
                    if len(log_files) > 5:
                        file_info_parts.append(f"- ... 等共{len(log_files)}个日志文件")
                
                if trace_files:
                    file_info_parts.append("\n### 调用链文件:")
                    for trace_file in trace_files[:5]:  # 最多显示5个
                        file_info_parts.append(f"- {trace_file}")
                    if len(trace_files) > 5:
                        file_info_parts.append(f"- ... 等共{len(trace_files)}个调用链文件")
                
                if metric_files:
                    file_info_parts.append("\n### 指标文件:")
                    for metric_file in metric_files[:8]:  # 最多显示8个
                        file_info_parts.append(f"- {metric_file}")
                    if len(metric_files) > 8:
                        file_info_parts.append(f"- ... 等共{len(metric_files)}个指标文件")
                
                file_info_parts.append("\n💡 提示: 使用preview_parquet_in_pd工具先预览文件结构，再用get_data_from_parquet获取具体数据。")
                
                return "\n".join(file_info_parts)
                
            else:
                # 如果无法提取时间，尝试提取日期
                date_pattern = r'(\d{4}-\d{2}-\d{2})'
                dates = re.findall(date_pattern, description)
                
                if dates:
                    target_date = dates[0]
                    self.loggers['diagnosis'].info(f"提取到日期: {target_date}")
                    
                    # 检查该日期的数据是否存在
                    data_dir = f"data/{target_date}"
                    if not os.path.exists(data_dir):
                        # 查找可用的日期
                        available_dates = []
                        for date_dir in glob.glob("data/2025-*"):
                            if os.path.isdir(date_dir):
                                date_name = os.path.basename(date_dir)
                                available_dates.append(date_name)
                        
                        if available_dates:
                            available_dates = sorted(available_dates)
                            return f"⚠️ 日期 {target_date} 无数据。可用日期: {', '.join(available_dates)}"
                        else:
                            return "⚠️ 未找到任何监控数据。"
                    
                    return f"## 可用监控数据文件\n目标日期: {target_date}\n💡 提示: 使用preview_parquet_in_pd工具探索具体文件。"
        
        except Exception as e:
            self.loggers['diagnosis'].error(f"文件发现失败: {e}")
            return f"⚠️ 无法自动发现文件: {str(e)}。请手动使用preview_parquet_in_pd工具探索数据结构。"
        
        return "⚠️ 无法从描述中提取时间信息。请手动使用preview_parquet_in_pd工具探索数据结构。"
    
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
    
    def parse_xml_tool_calls(self, text: str) -> List[ToolCall]:
        """
        解析文本中的XML格式工具调用
        
        Args:
            text: 包含XML工具调用的文本
            
        Returns:
            解析出的工具调用列表
        """
        tool_calls = []
        
        # 查找所有可能的工具调用
        for tool_name in self.tools.keys():
            # 构建正则表达式匹配对应的XML标签
            pattern = f'<{tool_name}>(.*?)</{tool_name}>'
            matches = re.findall(pattern, text, re.DOTALL)
            
            for match in matches:
                try:
                    # 解析参数
                    parameters = self._parse_tool_parameters(match.strip())
                    tool_calls.append(ToolCall(name=tool_name, parameters=parameters))
                    self.loggers['interaction'].debug(f"解析到工具调用: {tool_name}")
                except Exception as e:
                    self.loggers['interaction'].error(f"解析工具调用 {tool_name} 时出错: {e}")
                    continue
        
        return tool_calls
    
    def _parse_tool_parameters(self, xml_content: str) -> Dict[str, Any]:
        """
        解析工具参数的XML内容
        
        Args:
            xml_content: XML参数内容
            
        Returns:
            解析出的参数字典
        """
        parameters = {}
        
        # 使用正则表达式匹配参数标签
        param_pattern = r'<(\w+)>(.*?)</\1>'
        matches = re.findall(param_pattern, xml_content, re.DOTALL)
        
        for param_name, param_value in matches:
            param_value = param_value.strip()
            
            # 尝试解析特殊类型的参数
            if param_name == 'pd_read_kwargs':
                try:
                    # 尝试解析为字典
                    parameters[param_name] = eval(param_value) if param_value else {}
                except:
                    parameters[param_name] = {}
            else:
                parameters[param_name] = param_value
        
        return parameters
    
    def execute_tool(self, tool_call: ToolCall) -> Dict[str, Any]:
        """
        执行工具调用
        
        Args:
            tool_call: 工具调用对象
            
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
        
        try:
            tool_func = self.tools[tool_call.name]
            result = tool_func(**tool_call.parameters)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._log_tool_execution(tool_call, result, execution_time)
            
            return result
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_result = {
                "error": f"工具执行失败: {str(e)}",
                "tool": tool_call.name,
                "parameters": tool_call.parameters
            }
            
            self._log_tool_execution(tool_call, error_result, execution_time)
            self._log_error(e, f"执行工具 {tool_call.name}")
            
            return error_result
    
    def format_tool_result(self, tool_call: ToolCall, result: Dict[str, Any]) -> str:
        """
        格式化工具执行结果为文本
        
        Args:
            tool_call: 工具调用对象
            result: 工具执行结果
            
        Returns:
            格式化的结果文本
        """
        formatted_result = f"=== 工具执行结果: {tool_call.name} ===\n"
        
        # 格式化结果
        if "error" in result:
            formatted_result += f"❌ 错误: {result['error']}\n"
            if "suggestion" in result:
                formatted_result += f"💡 建议: {result['suggestion']}\n"
        else:
            # 成功执行
            if tool_call.name == "attempt_completion":
                formatted_result += f"✅ {result.get('message', '任务完成')}\n"
                if "result" in result:
                    formatted_result += f"结果: {json.dumps(result['result'], ensure_ascii=False, indent=2)}\n"
            else:
                # 数据工具的结果
                if "data" in result:
                    data_count = len(result["data"])
                    formatted_result += f"✅ 成功获取 {data_count} 条数据\n"
                    formatted_result += f"形状: {result.get('shape', 'N/A')}\n"
                    formatted_result += f"列名: {result.get('columns', [])}\n"
                    formatted_result += f"估算Token数: {result.get('estimated_tokens', 'N/A')}\n"
                    
                    # 显示部分数据样例
                    if data_count > 0:
                        formatted_result += f"数据样例 (前2条):\n"
                        for i, record in enumerate(result["data"][:2]):
                            formatted_result += f"  {i+1}. {json.dumps(record, ensure_ascii=False)}\n"
                else:
                    # 预览结果或其他结果
                    for key, value in result.items():
                        if key not in ["data", "error"]:
                            formatted_result += f"{key}: {value}\n"
        
        formatted_result += "=" * 50 + "\n"
        return formatted_result
    
    def diagnose_single_case(self, case: Dict[str, str], debug: bool = False) -> Dict[str, Any]:
        """
        诊断单个故障案例
        
        Args:
            case: 故障案例，包含uuid和Anomaly Description
            debug: 是否显示调试信息
            
        Returns:
            诊断结果
        """
        uuid = case["uuid"]
        description = case["Anomaly Description"]
        
        # 创建案例特定的错误日志记录器
        self.case_error_logger = self.logger_setup.create_case_error_logger(uuid)
        
        # 记录诊断开始
        self._log_diagnosis_start(uuid, description)
        
        print(f"\n🔍 开始诊断故障案例: {uuid}")
        print(f"描述: {description}")
        print("=" * 80)
        
        # 重置步骤计数
        self.steps = []
        self.current_step = 0
        
        try:
            # 从故障描述中提取时间窗口并发现相关文件
            file_info = self._discover_relevant_files(description, debug)
            
            # 构建针对比赛的专用任务提示
            task_prompt = f"""
请分析以下故障案例并进行根因定位：

故障案例UUID: {uuid}
故障描述: {description}

{file_info}

你需要：
1. 分析故障发生的时间窗口
2. 系统性分析相关监控数据（logs、metrics、traces）
3. 识别根因组件（component）
4. 确定故障原因（reason）
5. 提供完整的推理轨迹（reasoning_trace）

要求：
- 每个推理步骤必须包含具体的action和observation
- observation字段控制在100字以内，突出关键信息
- 必须收集多维度证据（指标异常、日志错误、调用链异常）
- 推理步骤要紧凑高效，避免冗余
- 最终使用attempt_completion提交结果

请开始分析。
            """
            
            # 构建初始消息
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task_prompt}
            ]
            
            iteration = 0
            final_result = None
            
            while iteration < self.max_iterations:
                iteration += 1
                self.current_step += 1
                
                self.loggers['diagnosis'].info(f"第 {iteration} 轮推理开始...")
                
                if debug:
                    print(f"\n🔄 第 {iteration} 轮推理...")
                
                try:
                    # 记录模型交互
                    self._log_model_interaction(iteration, len(messages), 0)
                    
                    # 获取模型响应，设置temperature=0确保稳定性
                    response = self.model_client.chat(
                        messages=messages,
                        model=self.model_name,
                        temperature=0.0,  # 比赛要求稳定输出
                        debug=debug
                    )
                    
                    # 更新交互日志
                    self._log_model_interaction(iteration, len(messages), len(response))
                    
                    if debug:
                        print(f"📝 模型响应:\n{response[:200]}...\n")
                    
                    # 解析工具调用
                    tool_calls = self.parse_xml_tool_calls(response)
                    
                    if not tool_calls:
                        self.loggers['diagnosis'].warning("未检测到工具调用，任务可能已完成或存在问题")
                        if debug:
                            print("❌ 未检测到工具调用，任务可能已完成或存在问题")
                        break
                    
                    # 执行工具调用
                    tool_results = []
                    for tool_call in tool_calls:
                        if debug:
                            print(f"🔧 执行工具: {tool_call.name}")
                        
                        result = self.execute_tool(tool_call)
                        tool_results.append((tool_call, result))
                        
                        # 记录执行步骤
                        step = AgentStep(
                            step_num=self.current_step,
                            action=f"{tool_call.name}({json.dumps(tool_call.parameters, ensure_ascii=False)})",
                            observation=str(result)[:100] + "..." if len(str(result)) > 100 else str(result),
                            reasoning=response[:100] + "..." if len(response) > 100 else response
                        )
                        self.steps.append(step)
                        self._log_diagnosis_step(self.current_step, step.action, step.observation, step.reasoning)
                        
                        # 检查是否完成任务
                        if tool_call.name == "attempt_completion" and "status" in result:
                            if result["status"] == "completed":
                                final_result = result.get("result")
                                self.loggers['diagnosis'].info("故障诊断成功完成!")
                                if debug:
                                    print("✅ 故障诊断完成!")
                                return {
                                    "status": "completed",
                                    "result": final_result,
                                    "steps": self.steps,
                                    "iterations": iteration
                                }
                            else:
                                error_msg = f"任务完成调用失败: {result.get('error', '未知错误')}"
                                self.loggers['diagnosis'].error(error_msg)
                                if self.case_error_logger:
                                    self.case_error_logger.error(error_msg)
                                if debug:
                                    print(f"⚠️ {error_msg}")
                    
                    # 将工具结果添加到对话历史
                    tool_results_text = "\n".join([
                        self.format_tool_result(tool_call, result) 
                        for tool_call, result in tool_results
                    ])
                    
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"工具执行结果:\n{tool_results_text}\n继续分析。"})
                    
                except Exception as e:
                    error_msg = f"第 {iteration} 轮执行出错: {e}"
                    self.loggers['diagnosis'].error(error_msg)
                    self._log_error(e, f"第 {iteration} 轮执行", uuid)
                    print(f"❌ {error_msg}")
                    if debug:
                        import traceback
                        traceback.print_exc()
                    break
            
            # 达到最大迭代次数或其他原因结束
            result_summary = {
                "status": "incomplete",
                "result": final_result,
                "steps": self.steps,
                "iterations": iteration,
                "reason": "达到最大迭代次数" if iteration >= self.max_iterations else "执行中断"
            }
            
            self.loggers['diagnosis'].warning(f"诊断未完成: {result_summary['reason']}")
            return result_summary
            
        except Exception as e:
            self._log_error(e, "诊断单个案例", uuid)
            return {
                "status": "error", 
                "error": str(e),
                "steps": self.steps,
                "iterations": 0
            }
    
    def process_input_json(self, input_file: str = "input.json", output_file: str = "answer.json", debug: bool = False) -> Dict[str, Any]:
        """
        处理input.json文件中的所有故障案例，生成answer.json
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            debug: 是否显示调试信息
            
        Returns:
            处理结果统计
        """
        print(f"🚀 开始处理 CCF AIOps 挑战赛故障案例")
        print(f"输入文件: {input_file}")
        print(f"输出文件: {output_file}")
        print("=" * 80)
        
        self.loggers['summary'].info("=" * 80)
        self.loggers['summary'].info("开始处理 CCF AIOps 挑战赛故障案例")
        self.loggers['summary'].info(f"输入文件: {input_file}")
        self.loggers['summary'].info(f"输出文件: {output_file}")
        self.loggers['summary'].info("=" * 80)
        
        # 读取输入文件
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                cases = json.load(f)
        except Exception as e:
            error_msg = f"读取输入文件失败: {e}"
            print(f"❌ {error_msg}")
            self.loggers['summary'].error(error_msg)
            self._log_error(e, "读取输入文件")
            return {"status": "error", "error": str(e)}
        
        print(f"📊 共发现 {len(cases)} 个故障案例")
        self.loggers['summary'].info(f"共发现 {len(cases)} 个故障案例")
        
        # 处理所有案例
        results = []
        successful_count = 0
        failed_count = 0
        
        for i, case in enumerate(cases):
            try:
                print(f"\n{'='*80}")
                print(f"进度: {i+1}/{len(cases)} - {(i+1)/len(cases)*100:.1f}%")
                
                self.loggers['summary'].info(f"处理案例 {i+1}/{len(cases)}: {case.get('uuid', 'unknown')}")
                
                # 诊断单个案例
                diagnosis_result = self.diagnose_single_case(case, debug=debug)
                
                if diagnosis_result["status"] == "completed" and diagnosis_result["result"]:
                    results.append(diagnosis_result["result"])
                    successful_count += 1
                    success_msg = f"案例 {case['uuid']} 诊断完成"
                    print(f"✅ {success_msg}")
                    self.loggers['summary'].info(success_msg)
                else:
                    failed_count += 1
                    fail_msg = f"案例 {case['uuid']} 诊断失败: {diagnosis_result.get('reason', '未知原因')}"
                    print(f"❌ {fail_msg}")
                    self.loggers['summary'].error(fail_msg)
                    
                    # 为失败的案例生成一个基本结果，避免丢失
                    fallback_result = {
                        "uuid": case["uuid"],
                        "component": "unknown",
                        "reason": "analysis_failed", 
                        "time": "2025-06-06 12:00:00",
                        "reasoning_trace": [
                            {
                                "step": 1,
                                "action": "DiagnosisAttempt",
                                "observation": "Automatic diagnosis failed, requires manual investigation"
                            }
                        ]
                    }
                    results.append(fallback_result)
                
            except Exception as e:
                error_msg = f"处理案例 {case.get('uuid', 'unknown')} 时出错: {e}"
                print(f"❌ {error_msg}")
                self.loggers['summary'].error(error_msg)
                self._log_error(e, f"处理案例 {case.get('uuid', 'unknown')}")
                failed_count += 1
                if debug:
                    import traceback
                    traceback.print_exc()
        
        # 保存结果
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            save_msg = f"结果已保存到 {output_file}"
            print(f"\n✅ {save_msg}")
            self.loggers['summary'].info(save_msg)
        except Exception as e:
            error_msg = f"保存结果失败: {e}"
            print(f"❌ {error_msg}")
            self.loggers['summary'].error(error_msg)
            self._log_error(e, "保存结果")
            return {"status": "error", "error": f"保存失败: {str(e)}"}
        
        # 返回统计结果
        summary = {
            "status": "completed",
            "total_cases": len(cases),
            "successful_cases": successful_count,
            "failed_cases": failed_count,
            "success_rate": successful_count / len(cases) * 100,
            "output_file": output_file
        }
        
        print(f"\n{'='*80}")
        print(f"📊 处理完成统计:")
        print(f"总案例数: {summary['total_cases']}")
        print(f"成功案例: {summary['successful_cases']}")
        print(f"失败案例: {summary['failed_cases']}")
        print(f"成功率: {summary['success_rate']:.1f}%")
        print(f"{'='*80}")
        
        # 记录最终统计信息
        self.loggers['summary'].info("=" * 80)
        self.loggers['summary'].info("处理完成统计:")
        self.loggers['summary'].info(f"总案例数: {summary['total_cases']}")
        self.loggers['summary'].info(f"成功案例: {summary['successful_cases']}")
        self.loggers['summary'].info(f"失败案例: {summary['failed_cases']}")
        self.loggers['summary'].info(f"成功率: {summary['success_rate']:.1f}%")
        self.loggers['summary'].info("=" * 80)
        
        return summary


def main():
    """主函数 - 比赛模式"""
    # 创建智能体
    agent = AIOpsReactAgent(model_name="deepseek-v3:671b", max_iterations=12)
    
    print("🏆 CCF AIOps挑战赛故障诊断智能体")
    print("=" * 80)
    
    # 处理所有故障案例
    result = agent.process_input_json(
        input_file="input.json",
        output_file="answer.json", 
        debug=False
    )
    
    if result["status"] == "completed":
        print(f"\n🎉 比赛提交文件已生成!")
        print(f"📁 文件位置: {result['output_file']}")
        print(f"📈 成功率: {result['success_rate']:.1f}%")
    else:
        print(f"\n❌ 处理失败: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()
