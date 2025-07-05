#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: CCF AIOps挑战赛 React模式故障诊断智能体核心逻辑
"""

import re
import json
import time
import concurrent.futures
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# 添加rich库导入用于动态进度条
from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeElapsedColumn, SpinnerColumn
from rich.console import Console
from rich.live import Live
from rich.table import Table

from ..config import AgentConfig
from ..log_system import LoggerSetup
from ..model import ModelClient
from ..prompt import SYSTEM_PROMPT

from .tool_executor import ToolCall, ToolExecutor
from .context_manager import ContextManager
from .error_handler import ErrorHandler
from .file_discovery import FileDiscovery


@dataclass
class AgentStep:
    """Agent执行步骤"""
    step_num: int
    action: str
    observation: str
    reasoning: Optional[str] = None


class AIOpsReactAgent:
    """CCF AIOps挑战赛专用React模式故障诊断智能体"""
    
    # 已申请支持的模型配置（委托给配置类）
    MODEL_CONFIGS = AgentConfig().MODEL_CONFIGS
    
    def __init__(self, model_name: str = "deepseek-v3:671b", max_iterations: int = 15, max_model_retries: int = 3, 
                 max_context_length: Optional[int] = None, temperature: Optional[float] = None,
                 concurrency: int = None):
        """
        初始化Agent
        
        Args:
            model_name: 使用的模型名称
            max_iterations: 最大迭代次数，防止无限循环
            max_model_retries: 模型调用最大重试次数
            max_context_length: 模型支持的最大上下文长度（tokens），如果为None则使用模型的建议配置
            temperature: 模型生成温度，0.0为确定性输出，值越高随机性越强，如果为None则使用模型的建议配置
            concurrency: 并发处理数量，如果为None则使用配置默认值
        """
        # 初始化配置
        self.config = AgentConfig()
        self.config.max_iterations = max_iterations
        self.config.max_model_retries = max_model_retries
        
        # 设置并发数量
        if concurrency is not None:
            self.concurrency = self.config.validate_concurrency(concurrency)
        else:
            self.concurrency = self.config.concurrency
        
        # 自动配置模型参数
        model_config = self.config.get_model_config(model_name)
        
        self.model_client = ModelClient()
        self.model_name = model_name
        self.max_context_length = max_context_length if max_context_length is not None else model_config["max_context_length"]
        self.temperature = temperature if temperature is not None else model_config["temperature"]
        
        # 初始化日志系统
        self.logger_setup = LoggerSetup(self.config.log_base_dir)
        self.loggers = self.logger_setup.loggers
        
        # 初始化各个组件
        self.tool_executor = ToolExecutor(self.config, self.loggers)
        self.context_manager = ContextManager(self.config, self.loggers, self.max_context_length)
        self.error_handler = ErrorHandler(self.config)
        self.file_discovery = FileDiscovery(self.config, self.loggers)
        
        # 记录执行步骤
        self.steps: List[AgentStep] = []
        self.current_step = 0
        
        # 比赛专用配置
        self.competition_mode = True
        
        # 当前案例的错误日志记录器
        self.case_error_logger = None
        
        # 记录初始化
        self._log_initialization()
    
    def _log_initialization(self):
        """记录初始化信息"""
        self.loggers['summary'].info("=== CCF AIOps智能体初始化完成 ===")
        self.loggers['summary'].info(f"模型: {self.model_name}")
        
        # 显示配置来源
        context_source = "auto-configured" if self.max_context_length == self.config.get_model_config(self.model_name)["max_context_length"] else "user-specified"
        temp_source = "auto-configured" if self.temperature == self.config.get_model_config(self.model_name)["temperature"] else "user-specified"
        
        self.loggers['summary'].info(f"模型配置: 最大上下文长度={self.max_context_length:,}tokens ({context_source}), 温度={self.temperature} ({temp_source})")
        self.loggers['summary'].info(f"最大迭代次数: {self.config.max_iterations}")
        self.loggers['summary'].info(f"并发处理数量: {self.concurrency}")
        self.loggers['summary'].info(f"可用工具: {list(self.tool_executor.tools.keys())}")
        self.loggers['summary'].info(f"模型重试次数: {self.config.max_model_retries}")
        self.loggers['summary'].info(f"上下文管理: 最大{self.context_manager.max_context_tokens}tokens，压缩阈值{self.context_manager.context_compress_threshold}tokens，工具结果限制{self.context_manager.max_tool_result_tokens}tokens")
    
    @classmethod
    def get_supported_models(cls) -> Dict[str, Dict[str, Any]]:
        """获取支持的模型配置信息"""
        return cls.MODEL_CONFIGS.copy()
    
    @classmethod 
    def print_supported_models(cls):
        """打印支持的模型配置"""
        print("Supported models and their recommended configurations:")
        print("=" * 60)
        for model, config in cls.MODEL_CONFIGS.items():
            print(f"Model: {model}")
            print(f"  Max Context Length: {config['max_context_length']:,} tokens")
            print(f"  Temperature: {config['temperature']}")
            print("-" * 40)
    
    def _log_diagnosis_start(self, uuid: str, description: str):
        """记录诊断开始"""
        self.loggers['diagnosis'].info("=" * 80)
        self.loggers['diagnosis'].info(f"开始诊断故障案例: {uuid}")
        self.loggers['diagnosis'].info(f"故障描述: {description}")
        self.loggers['diagnosis'].info("=" * 80)
    
    def _log_diagnosis_step(self, step_num: int, action: str, observation: str, reasoning: str = ""):
        """记录诊断步骤 - 增强版本，包含详细和简化两种日志"""
        # 简化版本用于快速浏览
        self.loggers['diagnosis'].info(f"步骤 {step_num}:")
        self.loggers['diagnosis'].info(f"  行动: {action}")
        self.loggers['diagnosis'].info(f"  观察简要: {observation[:300]}{'...' if len(observation) > 300 else ''}")
        if reasoning:
            self.loggers['diagnosis'].info(f"  推理简要: {reasoning[:300]}{'...' if len(reasoning) > 300 else ''}")
        self.loggers['diagnosis'].info("-" * 40)
        
        # 详细版本记录到交互日志 - 完整信息
        self.loggers['interaction'].info(f"=== 诊断步骤 {step_num} - 详细信息 ===")
        self.loggers['interaction'].info(f"行动: {action}")
        self.loggers['interaction'].info(f"观察完整内容 (长度: {len(observation)} 字符):")
        self.loggers['interaction'].info(f"{observation}")
        if reasoning:
            self.loggers['interaction'].info(f"推理完整内容 (长度: {len(reasoning)} 字符):")
            self.loggers['interaction'].info(f"{reasoning}")
        self.loggers['interaction'].info("=" * 60)
    
    def _log_model_interaction(self, iteration: int, messages_count: int, response_length: int, response_preview: str = ""):
        """记录模型交互 - 增强版本"""
        self.loggers['interaction'].info(f"第 {iteration} 轮模型交互")
        self.loggers['interaction'].info(f"消息数量: {messages_count}")
        self.loggers['interaction'].info(f"响应长度: {response_length} 字符")
        if response_preview:
            self.loggers['interaction'].info(f"响应预览: {response_preview[:500]}{'...' if len(response_preview) > 500 else ''}")
            # 完整响应记录到详细日志
            self.loggers['interaction'].debug(f"完整响应内容:\n{response_preview}")
    
    def _log_llm_interaction(self, iteration: int, uuid: str, input_messages: List[Dict[str, Any]], 
                           output_response: str, duration: float = 0, model_name: str = ""):
        """记录大模型原始交互信息"""
        separator = "=" * 100
        
        interaction_data = {
            "interaction_id": f"{uuid}_{iteration}_{datetime.now().strftime('%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration,
            "case_uuid": uuid,
            "model": model_name,
            "duration_seconds": round(duration, 3),
            "input": {
                "messages_count": len(input_messages),
                "messages": input_messages,
                "total_input_length": sum(len(str(msg.get('content', ''))) for msg in input_messages)
            },
            "output": {
                "response": output_response,
                "response_length": len(output_response)
            }
        }
        
        # 格式化JSON输出，确保中文显示正常
        formatted_json = json.dumps(interaction_data, ensure_ascii=False, indent=2)
        
        # 记录到日志
        self.loggers['llm_interactions'].info(f"\n{separator}")
        self.loggers['llm_interactions'].info(f"LLM INTERACTION #{iteration} - CASE: {uuid}")
        self.loggers['llm_interactions'].info(f"{separator}")
        self.loggers['llm_interactions'].info(formatted_json)
        self.loggers['llm_interactions'].info(f"{separator}\n")
    
    def parse_xml_tool_calls(self, text: str) -> List[ToolCall]:
        """
        解析文本中的XML格式工具调用，包含参数验证
        
        Args:
            text: 包含XML工具调用的文本
            
        Returns:
            解析出的工具调用列表
        """
        tool_calls = []
        
        # 查找所有可能的工具调用
        for tool_name in self.tool_executor.tools.keys():
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
    
    def _call_model_with_retry(self, messages: List[Dict[str, Any]], max_retries: int = None, 
                             retry_delay: float = None, debug: bool = False) -> str:
        """
        增强的带重试机制的模型调用，支持上下文长度错误处理
        
        Args:
            messages: 消息列表
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            debug: 是否显示调试信息
            
        Returns:
            模型响应
            
        Raises:
            Exception: 重试耗尽后仍然失败
        """
        if max_retries is None:
            max_retries = self.config.max_model_retries
        if retry_delay is None:
            retry_delay = self.config.retry_delay
            
        last_error = None
        original_messages = messages.copy()
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    self.loggers['error'].warning(f"第 {attempt} 次重试模型调用...")
                    if debug:
                        print(f"🔄 第 {attempt} 次重试模型调用...")
                    delay = self.error_handler.calculate_retry_delay(attempt, str(last_error) if last_error else "")
                    time.sleep(delay)
                
                response = self.model_client.chat(
                    messages=messages,
                    model=self.model_name,
                    temperature=self.temperature,
                    debug=debug
                )
                
                if attempt > 0:
                    self.loggers['error'].info(f"重试成功（第 {attempt} 次）")
                    if debug:
                        print(f"✅ 重试成功（第 {attempt} 次）")
                
                return response
                
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # 检查是否是上下文长度错误
                if 'context length' in error_msg or 'token' in error_msg:
                    self.loggers['error'].warning(f"上下文长度超限，尝试进一步压缩: {e}")
                    
                    # 进一步压缩消息
                    messages = self.context_manager.compress_for_context_limit(messages)
                    if len(messages) <= 3:
                        # 已经压缩到最小，无法继续
                        self.loggers['error'].error(f"无法进一步压缩上下文: {e}")
                        raise e
                    continue
                
                # 检查是否是可重试的错误
                if not self.error_handler.is_retryable_error(error_msg):
                    self.loggers['error'].error(f"遇到不可重试的错误: {e}")
                    raise e
                
                if attempt < max_retries:
                    self.loggers['error'].warning(f"API调用失败 (第 {attempt + 1} 次尝试): {e}")
                    if debug:
                        print(f"⚠️ API调用失败 (第 {attempt + 1} 次尝试): {e}")
                else:
                    self.loggers['error'].error(f"API调用重试耗尽，最后错误: {e}")
                    if debug:
                        print(f"❌ API调用重试耗尽，最后错误: {e}")
        
        # 所有重试都失败了
        raise last_error
    
    def diagnose_single_case(self, case: Dict[str, str], debug: bool = False, progress_callback=None) -> Dict[str, Any]:
        """
        诊断单个故障案例
        
        Args:
            case: 故障案例，包含uuid和Anomaly Description
            debug: 是否显示调试信息
            progress_callback: 进度更新回调函数
            
        Returns:
            诊断结果
        """
        uuid = case["uuid"]
        description = case["Anomaly Description"]
        
        # 创建案例特定的错误日志记录器
        self.case_error_logger = self.logger_setup.create_case_error_logger(uuid)
        
        # 记录诊断开始
        self._log_diagnosis_start(uuid, description)
        
        # 在debug模式下才显示详细信息，否则由进度条显示
        if debug:
            print(f"\n🔍 开始诊断故障案例: {uuid}")
            print(f"描述: {description}")
            print("=" * 80)
        
        # 重置步骤计数
        self.steps = []
        self.current_step = 0
        
        try:
            # 从故障描述中提取时间窗口并发现相关文件
            file_info = self.file_discovery.discover_relevant_files(description, debug)
            
            # Build competition-specific task prompt
            task_prompt = f"""
<fault_case>
Please analyze the following fault case and perform root cause localization:

Fault Case UUID: {uuid}
Anomaly Description: {description}
</fault_case>

<available_data>
{file_info}
</available_data>

<analysis_requirements>
You need to complete the following analysis tasks:
1. Analyze the time window when the fault occurred
2. Systematically analyze relevant monitoring data (logs, metrics, traces)
3. Identify the root cause component
4. Determine the fault reason
5. Provide complete reasoning trace
</analysis_requirements>

<output_requirements>
Output format requirements:
- Each reasoning step must include specific action and observation
- Observation field should be limited to 100 characters, highlighting key information
- Must collect multi-dimensional evidence (metric anomalies, log errors, trace anomalies)
- Reasoning steps should be compact and efficient, avoiding redundancy
- Finally use attempt_completion to submit the result
</output_requirements>

<instructions>
Please start the analysis.
</instructions>
            """
            
            # 构建初始消息
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task_prompt}
            ]
            
            iteration = 0
            final_result = None
            interrupt_reason = None  # 跟踪中断的具体原因
            successful_iterations = 0  # 成功执行的轮数
            failed_iterations = 0  # 失败的轮数
            
            while iteration < self.config.max_iterations:
                iteration += 1
                self.current_step += 1
                
                # 更新进度条
                if progress_callback:
                    progress_callback('iteration', iteration, self.config.max_iterations)
                
                self.loggers['diagnosis'].info(f"第 {iteration} 轮推理开始...")
                
                if debug:
                    print(f"\n🔄 第 {iteration} 轮推理...")
                # 在进度条模式下不打印轮次信息，避免干扰显示
                
                try:
                    # 上下文管理 - 在调用模型前进行上下文长度检查和压缩
                    managed_messages = self.context_manager.manage_context_length(messages)
                    
                    # 记录模型交互
                    self._log_model_interaction(iteration, len(managed_messages), 0)
                    
                    # 记录LLM调用开始时间
                    llm_start_time = datetime.now()
                    
                    # 使用带重试机制的模型调用
                    response = self._call_model_with_retry(
                        messages=managed_messages,
                        debug=debug
                    )
                    
                    # 计算LLM调用耗时
                    llm_duration = (datetime.now() - llm_start_time).total_seconds()
                    
                    # 记录LLM原始交互信息
                    self._log_llm_interaction(
                        iteration=iteration,
                        uuid=uuid,
                        input_messages=managed_messages,
                        output_response=response,
                        duration=llm_duration,
                        model_name=self.model_name
                    )
                    
                    # 更新交互日志（传入完整响应）
                    self._log_model_interaction(iteration, len(messages), len(response), response)
                    
                    # 完整响应记录到交互日志 - 无论是否debug都记录
                    self.loggers['interaction'].debug(f"完整模型响应:\n{response}")
                    
                    if debug:
                        print(f"📝 模型响应预览:\n{response[:500]}{'...' if len(response) > 500 else ''}\n")
                    
                    # 解析工具调用
                    tool_calls = self.parse_xml_tool_calls(response)
                    
                    if not tool_calls:
                        warning_msg = "未检测到工具调用，任务可能已完成或存在问题"
                        interrupt_reason = f"第{iteration}轮未检测到工具调用"
                        # 这轮API调用成功了，但是解析工具调用失败
                        successful_iterations += 1
                        self.loggers['diagnosis'].warning(warning_msg)
                        self.loggers['interaction'].warning(warning_msg)  # 也记录到交互日志
                        if debug:
                            print(f"❌ {warning_msg}")
                        break
                    
                    # 执行工具调用
                    tool_results = []
                    for tool_call in tool_calls:
                        # 始终记录工具执行到日志 - 无论是否debug
                        self.loggers['interaction'].info(f"执行工具: {tool_call.name}")
                        self.loggers['interaction'].info(f"工具参数: {json.dumps(tool_call.parameters, ensure_ascii=False)}")
                        
                        if debug:
                            print(f"🔧 执行工具: {tool_call.name}")
                        
                        result = self.tool_executor.execute_tool(tool_call, self.case_error_logger)
                        tool_results.append((tool_call, result))
                        
                        # 记录执行步骤 - 保存完整信息用于详细日志
                        full_observation = str(result)
                        full_reasoning = response
                        
                        step = AgentStep(
                            step_num=self.current_step,
                            action=f"{tool_call.name}({json.dumps(tool_call.parameters, ensure_ascii=False)})",
                            observation=full_observation,  # 保存完整观察信息
                            reasoning=full_reasoning       # 保存完整推理信息
                        )
                        self.steps.append(step)
                        
                        # 传递完整信息给日志记录方法
                        self._log_diagnosis_step(self.current_step, step.action, full_observation, full_reasoning)
                        
                        # 额外记录工具执行的详细信息
                        self.loggers['tool'].info(f"工具执行: {tool_call.name}")
                        self.loggers['tool'].info(f"参数: {json.dumps(tool_call.parameters, ensure_ascii=False, indent=2)}")
                        self.loggers['tool'].info(f"结果长度: {len(full_observation)} 字符")
                        self.loggers['tool'].info(f"结果内容:\n{full_observation}")
                        self.loggers['tool'].info("=" * 60)
                        
                        # 检查是否完成任务
                        if tool_call.name == "attempt_completion" and "status" in result:
                            if result["status"] == "completed":
                                final_result = result.get("result")
                                completion_msg = "故障诊断成功完成!"
                                self.loggers['diagnosis'].info(completion_msg)
                                self.loggers['interaction'].info(completion_msg)  # 也记录到交互日志
                                if debug:
                                    print("✅ 故障诊断完成!")
                                # 更新进度条为完成状态
                                if progress_callback:
                                    progress_callback('completed', iteration, self.config.max_iterations)
                                return {
                                    "status": "completed",
                                    "result": final_result,
                                    "steps": self.steps,
                                    "iterations": iteration
                                }
                            else:
                                error_msg = f"任务完成调用失败: {result.get('error', '未知错误')}"
                                self.loggers['diagnosis'].error(error_msg)
                                self.loggers['interaction'].error(error_msg)  # 也记录到交互日志
                                if self.case_error_logger:
                                    self.case_error_logger.error(error_msg)
                                if debug:
                                    print(f"⚠️ {error_msg}")
                    
                    # 将工具结果添加到对话历史
                    tool_results_text = "\n".join([
                        self.tool_executor.format_tool_result(tool_call, result) 
                        for tool_call, result in tool_results
                    ])
                    
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"Tool execution results:\n{tool_results_text}\nContinue analysis."})
                    
                    # 这轮执行成功
                    successful_iterations += 1
                    
                except Exception as e:
                    error_msg = f"第 {iteration} 轮执行出错: {e}"
                    self.loggers['diagnosis'].error(error_msg)
                    self.loggers['interaction'].error(error_msg)  # 也记录到交互日志
                    self.error_handler.log_error_with_context(e, f"第 {iteration} 轮执行", uuid, self.case_error_logger)
                    if debug:
                        print(f"❌ {error_msg}")
                    else:
                        print("❌", end="", flush=True)
                    
                    # 无论是否debug都记录完整异常信息到日志
                    import traceback
                    full_traceback = traceback.format_exc()
                    self.loggers['interaction'].debug(f"完整异常堆栈:\n{full_traceback}")
                    
                    if debug:
                        traceback.print_exc()
                    
                    # 这轮执行失败
                    failed_iterations += 1
                    
                    # 如果是早期错误（前3轮），尝试继续
                    if iteration <= 3:
                        continue_msg = "早期错误，尝试继续执行..."
                        self.loggers['diagnosis'].warning(continue_msg)
                        self.loggers['interaction'].warning(continue_msg)
                        continue
                    else:
                        interrupt_reason = f"第{iteration}轮出现异常: {str(e)}"
                        break
            
            # 达到最大迭代次数或其他原因结束
            if iteration >= self.config.max_iterations:
                if failed_iterations > successful_iterations:
                    failure_reason = f"API连续失败导致迭代耗尽 (成功{successful_iterations}轮/失败{failed_iterations}轮)"
                else:
                    failure_reason = f"达到最大迭代次数 (成功{successful_iterations}轮/失败{failed_iterations}轮)"
            elif interrupt_reason:
                failure_reason = f"{interrupt_reason} (成功{successful_iterations}轮/失败{failed_iterations}轮)"
            else:
                failure_reason = f"未知原因导致执行中断 (成功{successful_iterations}轮/失败{failed_iterations}轮)"
                
            result_summary = {
                "status": "incomplete",
                "result": final_result,
                "steps": self.steps,
                "iterations": iteration,
                "reason": failure_reason
            }
            
                                            # 更新进度条为失败状态
            if progress_callback:
                progress_callback('failed', iteration, self.config.max_iterations, failure_reason)
            
            self.loggers['diagnosis'].warning(f"诊断未完成: {result_summary['reason']}")
            return result_summary
            
        except Exception as e:
            # 更新进度条为异常状态
            if progress_callback:
                progress_callback('error', 0, self.config.max_iterations, str(e))
                
            self.error_handler.log_error_with_context(e, "诊断单个案例", uuid, self.case_error_logger)
            return {
                "status": "error", 
                "error": str(e),
                "steps": self.steps,
                "iterations": 0
            }
    
    def _diagnose_case_with_index(self, case_with_index: Tuple[int, Dict[str, str]], debug: bool = False, progress_callback=None) -> Tuple[int, Dict[str, Any]]:
        """
        带索引的单个案例诊断方法，用于并行处理
        
        Args:
            case_with_index: (索引, 案例数据) 元组
            debug: 是否显示调试信息
            progress_callback: 进度更新回调函数
            
        Returns:
            (索引, 诊断结果) 元组
        """
        index, case = case_with_index
        
        # 为每个线程创建独立的日志记录器
        thread_id = threading.current_thread().ident
        
        try:
            # 诊断单个案例，传递进度回调
            diagnosis_result = self.diagnose_single_case(case, debug=debug, progress_callback=progress_callback)
            
            return index, {
                "diagnosis_result": diagnosis_result,
                "case": case,
                "thread_id": thread_id
            }
            
        except Exception as e:
            # 记录线程级别的错误
            error_msg = f"线程 {thread_id} 处理案例 {case.get('uuid', 'unknown')} 时出错: {e}"
            self.loggers['summary'].error(error_msg)
            
            # 添加控制台打印
            print(f"❌ 案例 {case.get('uuid', 'unknown')} 处理异常: {str(e)[:50]}...")
            
            return index, {
                "diagnosis_result": {
                    "status": "error", 
                    "error": str(e),
                    "steps": [],
                    "iterations": 0
                },
                "case": case,
                "thread_id": thread_id,
                "error": str(e)
            }
    
    def process_input_json_parallel(self, input_file: str = "input.json", output_file: str = "answer.jsonl", 
                                  debug: bool = False, concurrency: int = None, output_format: str = "jsonl", limit: int = None) -> Dict[str, Any]:
        """
        并行处理input.json文件中的所有故障案例，生成answer.jsonl或answer.json
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            debug: 是否显示调试信息
            concurrency: 并发数量，如果为None则使用实例配置
            output_format: 输出格式，'jsonl' 或 'json'
            limit: 限制处理的案例数量，如果为None则处理所有案例
            
        Returns:
            处理结果统计
        """
        # 使用指定的并发数量或实例配置
        actual_concurrency = concurrency if concurrency is not None else self.concurrency
        actual_concurrency = self.config.validate_concurrency(actual_concurrency)
        
        limit_text = '全量处理' if limit is None else f'限制处理前{limit}个案例'
        print(f"🚀 开始并行处理故障案例（并发数：{actual_concurrency}，{limit_text}）")
        if debug:
            print(f"输入文件: {input_file}")
            print(f"输出文件: {output_file}")
            print("=" * 80)
        
        self.loggers['summary'].info("=" * 80)
        self.loggers['summary'].info("开始并行处理 CCF AIOps 挑战赛故障案例")
        self.loggers['summary'].info(f"输入文件: {input_file}")
        self.loggers['summary'].info(f"输出文件: {output_file}")
        self.loggers['summary'].info(f"并发数量: {actual_concurrency}")
        self.loggers['summary'].info(f"案例限制: {limit_text}")
        self.loggers['summary'].info("=" * 80)
        
        # 读取输入文件
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                cases = json.load(f)
        except Exception as e:
            error_msg = f"读取输入文件失败: {e}"
            print(f"❌ 读取输入文件失败")
            self.loggers['summary'].error(error_msg)
            self.error_handler.log_error_with_context(e, "读取输入文件")
            return {"status": "error", "error": str(e)}
        
        # 如果指定了限制数量，则截取前N个案例
        if limit is not None and limit > 0:
            original_count = len(cases)
            cases = cases[:limit]
            print(f"📊 共 {original_count} 个案例，限制处理前 {len(cases)} 个")
            self.loggers['summary'].info(f"共发现 {original_count} 个故障案例，限制处理前 {len(cases)} 个")
        else:
            print(f"📊 共 {len(cases)} 个案例")
            self.loggers['summary'].info(f"共发现 {len(cases)} 个故障案例")
        
        # 准备案例数据（添加索引）
        cases_with_index = [(i, case) for i, case in enumerate(cases)]
        
        # 初始化结果容器
        results = [None] * len(cases)  # 保证结果按原顺序排列
        successful_count = 0
        failed_count = 0
        completed_count = 0
        
        # 并行处理锁
        progress_lock = threading.Lock()
        
        def update_progress(future):
            """更新进度的回调函数（简化版，主要负责结果处理）"""
            nonlocal completed_count, successful_count, failed_count
            
            try:
                index, result_data = future.result()
                diagnosis_result = result_data["diagnosis_result"]
                case = result_data["case"]
                
                with progress_lock:
                    completed_count += 1
                    
                    if diagnosis_result["status"] == "completed" and diagnosis_result.get("result"):
                        results[index] = diagnosis_result["result"]
                        successful_count += 1
                        success_msg = f"案例 {case['uuid']} 诊断完成"
                        self.loggers['summary'].info(success_msg)
                    else:
                        failed_count += 1
                        fail_reason = diagnosis_result.get('reason', diagnosis_result.get('error', '未知原因'))
                        fail_msg = f"案例 {case['uuid']} 诊断失败: {fail_reason}"
                        self.loggers['summary'].error(fail_msg)
                        
                        # 触发失败回调，传递失败原因
                        case_id = case['uuid'][:8]
                        if case_id not in failure_reasons:
                            failure_reasons[case_id] = fail_reason
                        
                        # 为失败的案例生成一个基本结果
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
                        results[index] = fallback_result
                        
            except Exception as e:
                with progress_lock:
                    completed_count += 1
                    failed_count += 1
                # 尝试获取案例信息
                try:
                    case_info = future_to_case.get(future, {})
                    case_uuid = case_info.get('uuid', 'unknown') if isinstance(case_info, dict) else 'unknown'
                    case_id = case_uuid[:8] if case_uuid != 'unknown' else 'unknown'
                    
                    # 记录异常失败原因
                    failure_reasons[case_id] = f"处理结果异常: {str(e)}"
                except:
                    case_uuid = 'unknown'
                    case_id = 'unknown'
                    failure_reasons[case_id] = f"未知异常: {str(e)}"
                
                error_msg = f"处理案例 {case_uuid} 结果时出错: {e}"
                self.loggers['summary'].error(error_msg)
        
        # 使用Rich进度条显示并发处理进度
        print(f"⚡ 开始并行处理...")
        start_time = time.time()
        
        # 创建进度条配置
        console = Console()
        
        # 创建高级进度条管理器
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[case_id]:<8}", justify="left", style="bold blue"),
            BarColumn(
                bar_width=None,
                complete_style="green",
                finished_style="bright_green"
            ),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            TextColumn("{task.fields[status]:<8}", justify="center", style="bold"),
            "•",
            TextColumn("{task.fields[iteration]:<6}", style="dim cyan"),
            "•",
            TextColumn("{task.fields[speed]:<12}", style="magenta"),
            "•",
            TextColumn("{task.fields[eta]:<8}", style="yellow"),
            TimeElapsedColumn(),
            console=console,
            expand=True
        )
        
        # 为每个案例创建进度条
        task_ids = {}
        progress_callbacks = {}
        task_start_times = {}
        failure_reasons = {}  # 收集失败原因
        
        with progress:
            # 添加总体进度统计任务
            overall_task_id = progress.add_task(
                "总体进度",
                total=len(cases),
                case_id="[bold green]总体",
                status="📊 准备中",
                iteration=f"0/{len(cases)}",
                speed="0案例/分钟",
                eta="计算中"
            )
            
            # 为每个案例创建进度条
            for i, case in enumerate(cases):
                case_id = case['uuid'][:8]  # 使用UUID前8位作为显示ID
                task_id = progress.add_task(
                    f"案例-{case_id}",
                    total=self.config.max_iterations,
                    case_id=case_id,
                    status="⏳ 等待中",
                    iteration=f"0/{self.config.max_iterations}",
                    speed="0轮/分钟",
                    eta="--"
                )
                task_ids[i] = task_id
                task_start_times[i] = None
                
                # 创建每个任务的进度回调函数
                def make_callback(task_id, case_id, task_index):
                    def callback(event_type, current, total, reason=None):
                        nonlocal task_start_times, overall_task_id, failure_reasons
                        
                        # 记录开始时间
                        if event_type == 'iteration' and current == 1 and task_start_times[task_index] is None:
                            task_start_times[task_index] = time.time()
                        
                        # 计算速度和ETA
                        if task_start_times[task_index] and current > 0:
                            elapsed = time.time() - task_start_times[task_index]
                            speed = (current / elapsed) * 60 if elapsed > 0 else 0
                            speed_text = f"{speed:.1f}轮/分钟"
                            
                            # 计算ETA
                            if speed > 0:
                                remaining_iterations = total - current
                                eta_minutes = remaining_iterations / speed
                                if eta_minutes < 1:
                                    eta_text = f"{int(eta_minutes * 60)}秒"
                                else:
                                    eta_text = f"{int(eta_minutes)}分钟"
                            else:
                                eta_text = "--"
                        else:
                            speed_text = "0轮/分钟"
                            eta_text = "--"
                        
                        if event_type == 'iteration':
                            progress.update(
                                task_id,
                                completed=current,
                                status="🔄 处理中",
                                iteration=f"{current}/{total}",
                                speed=speed_text,
                                eta=eta_text
                            )
                        elif event_type == 'completed':
                            progress.update(
                                task_id,
                                completed=total,
                                status="✅ 完成",
                                iteration=f"{current}/{total}",
                                speed=speed_text,
                                eta="已完成"
                            )
                            # 更新总体进度
                            with progress_lock:
                                overall_elapsed = time.time() - start_time
                                overall_speed = (successful_count + failed_count) / (overall_elapsed / 60) if overall_elapsed > 0 else 0
                                overall_remaining = len(cases) - (successful_count + failed_count)
                                overall_eta = f"{int(overall_remaining / overall_speed)}分钟" if overall_speed > 0 and overall_remaining > 0 else "即将完成"
                                progress.update(
                                    overall_task_id,
                                    completed=successful_count + failed_count,
                                    status=f"📊 {successful_count}✅ {failed_count}❌",
                                    iteration=f"{successful_count + failed_count}/{len(cases)}",
                                    speed=f"{overall_speed:.1f}案例/分钟",
                                    eta=overall_eta
                                )
                        elif event_type == 'failed':
                            # 收集失败原因
                            failure_reason = reason or "未知失败原因"
                            failure_reasons[case_id] = failure_reason
                            
                            progress.update(
                                task_id,
                                completed=total,
                                status="❌ 失败",
                                iteration=f"{current}/{total}",
                                speed=speed_text,
                                eta="已终止"
                            )
                            # 更新总体进度
                            with progress_lock:
                                overall_elapsed = time.time() - start_time
                                overall_speed = (successful_count + failed_count) / (overall_elapsed / 60) if overall_elapsed > 0 else 0
                                overall_remaining = len(cases) - (successful_count + failed_count)
                                overall_eta = f"{int(overall_remaining / overall_speed)}分钟" if overall_speed > 0 and overall_remaining > 0 else "即将完成"
                                progress.update(
                                    overall_task_id,
                                    completed=successful_count + failed_count,
                                    status=f"📊 {successful_count}✅ {failed_count}❌",
                                    iteration=f"{successful_count + failed_count}/{len(cases)}",
                                    speed=f"{overall_speed:.1f}案例/分钟",
                                    eta=overall_eta
                                )
                        elif event_type == 'error':
                            # 收集异常原因
                            error_reason = reason or "未知异常"
                            failure_reasons[case_id] = f"异常: {error_reason}"
                            
                            progress.update(
                                task_id,
                                completed=total,
                                status="⚠️ 异常",
                                iteration=f"0/{total}",
                                speed="0轮/分钟",
                                eta="异常终止"
                            )
                            # 更新总体进度
                            with progress_lock:
                                overall_elapsed = time.time() - start_time
                                overall_speed = (successful_count + failed_count) / (overall_elapsed / 60) if overall_elapsed > 0 else 0
                                overall_remaining = len(cases) - (successful_count + failed_count)
                                overall_eta = f"{int(overall_remaining / overall_speed)}分钟" if overall_speed > 0 and overall_remaining > 0 else "即将完成"
                                progress.update(
                                    overall_task_id,
                                    completed=successful_count + failed_count,
                                    status=f"📊 {successful_count}✅ {failed_count}❌",
                                    iteration=f"{successful_count + failed_count}/{len(cases)}",
                                    speed=f"{overall_speed:.1f}案例/分钟",
                                    eta=overall_eta
                                )
                    return callback
                
                progress_callbacks[i] = make_callback(task_id, case_id, i)
            
            # 使用ThreadPoolExecutor进行并行处理
            with ThreadPoolExecutor(max_workers=actual_concurrency) as executor:
                # 提交所有任务，传递对应的进度回调
                future_to_case = {}
                for case_with_index in cases_with_index:
                    index = case_with_index[0]
                    callback = progress_callbacks[index]
                    future = executor.submit(self._diagnose_case_with_index, case_with_index, debug, callback)
                    future_to_case[future] = case_with_index[1]
                
                # 添加回调函数处理结果（简化版，不重复打印）
                for future in future_to_case:
                    future.add_done_callback(update_progress)
                
                # 等待所有任务完成
                concurrent.futures.wait(future_to_case)
        
        processing_time = time.time() - start_time
        
        # 过滤掉None结果
        final_results = [result for result in results if result is not None]
        
        # 使用Rich显示最终统计结果
        console.print("\n" + "="*80)
        
        # 创建统计表格
        stats_table = Table(title="📊 处理统计", show_header=True, header_style="bold magenta")
        stats_table.add_column("指标", style="cyan", justify="left")
        stats_table.add_column("数值", style="green", justify="right")
        
        success_rate = successful_count / len(cases) * 100
        speed = len(cases) / processing_time * 60 if processing_time > 0 else 0
        
        stats_table.add_row("总案例数", str(len(cases)))
        stats_table.add_row("成功案例", f"{successful_count} ✅")
        stats_table.add_row("失败案例", f"{failed_count} ❌")
        stats_table.add_row("成功率", f"{success_rate:.1f}%")
        stats_table.add_row("总用时", f"{processing_time:.1f}秒")
        stats_table.add_row("平均速度", f"{speed:.1f}案例/分钟")
        stats_table.add_row("并发数", str(actual_concurrency))
        
        console.print(stats_table)
        
        # 如果有失败案例，显示失败原因汇总
        if failure_reasons:
            console.print("\n")
            failure_table = Table(title="❌ 失败案例详情", show_header=True, header_style="bold red")
            failure_table.add_column("案例ID", style="yellow", justify="left")
            failure_table.add_column("失败原因", style="red", justify="left")
            
            for case_id, reason in failure_reasons.items():
                failure_table.add_row(case_id, reason)
            
            console.print(failure_table)
            
            # 失败原因分类统计
            reason_stats = {}
            for reason in failure_reasons.values():
                # 简化失败原因分类
                if "达到最大迭代次数" in reason:
                    category = "达到最大迭代次数"
                elif "API" in reason and "失败" in reason:
                    category = "API调用失败"
                elif "异常" in reason:
                    category = "程序异常"
                elif "未检测到工具调用" in reason:
                    category = "工具调用失败"
                else:
                    category = "其他原因"
                
                reason_stats[category] = reason_stats.get(category, 0) + 1
            
            if len(reason_stats) > 1:  # 只有在有多种失败原因时才显示分类统计
                console.print("\n")
                category_table = Table(title="📊 失败原因分类统计", show_header=True, header_style="bold yellow")
                category_table.add_column("失败类型", style="cyan", justify="left")
                category_table.add_column("案例数", style="red", justify="right")
                category_table.add_column("占比", style="magenta", justify="right")
                
                for category, count in sorted(reason_stats.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / failed_count) * 100
                    category_table.add_row(category, str(count), f"{percentage:.1f}%")
                
                console.print(category_table)
        
        console.print("="*80 + "\n")
        
        # 保存结果
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                if output_format.lower() == 'jsonl':
                    # 保存为 JSONL 格式
                    for result in final_results:
                        json.dump(result, f, ensure_ascii=False, separators=(',', ':'))
                        f.write('\n')
                else:
                    # 保存为 JSON 格式
                    json.dump(final_results, f, ensure_ascii=False, indent=2)
            
            save_msg = f"结果已保存到 {output_file} (格式: {output_format.upper()})"
            console.print(f"✅ [bold green]结果已保存到 {output_file} ({output_format.upper()})[/bold green]")
            self.loggers['summary'].info(save_msg)
        except Exception as e:
            error_msg = f"保存结果失败: {e}"
            if debug:
                print(f"❌ {error_msg}")
            else:
                print(f"❌ 保存失败")
            self.loggers['summary'].error(error_msg)
            self.error_handler.log_error_with_context(e, "保存结果")
            return {"status": "error", "error": f"保存失败: {str(e)}"}
        
        # 返回统计结果
        summary = {
            "status": "completed",
            "total_cases": len(cases),
            "successful_cases": successful_count,
            "failed_cases": failed_count,
            "success_rate": successful_count / len(cases) * 100,
            "output_file": output_file,
            "output_format": output_format,
            "processing_time": processing_time,
            "concurrency": actual_concurrency,
            "cases_per_second": len(cases) / processing_time if processing_time > 0 else 0
        }
        
        if debug:
            print(f"\n{'='*80}")
            print(f"📊 并行处理完成统计:")
            print(f"总案例数: {summary['total_cases']}")
            print(f"成功案例: {summary['successful_cases']}")
            print(f"失败案例: {summary['failed_cases']}")
            print(f"成功率: {summary['success_rate']:.1f}%")
            print(f"处理时间: {summary['processing_time']:.2f}秒")
            print(f"并发数: {summary['concurrency']}")
            print(f"处理速度: {summary['cases_per_second']:.2f}案例/秒")
            print(f"{'='*80}")
        else:
            print(f"\n📊 完成: 成功{summary['successful_cases']}/{summary['total_cases']} ({summary['success_rate']:.1f}%) - {summary['processing_time']:.1f}秒")
        
        # 记录最终统计信息
        self.loggers['summary'].info("=" * 80)
        self.loggers['summary'].info("并行处理完成统计:")
        self.loggers['summary'].info(f"总案例数: {summary['total_cases']}")
        self.loggers['summary'].info(f"成功案例: {summary['successful_cases']}")
        self.loggers['summary'].info(f"失败案例: {summary['failed_cases']}")
        self.loggers['summary'].info(f"成功率: {summary['success_rate']:.1f}%")
        self.loggers['summary'].info(f"处理时间: {summary['processing_time']:.2f}秒")
        self.loggers['summary'].info(f"并发数: {summary['concurrency']}")
        self.loggers['summary'].info(f"处理速度: {summary['cases_per_second']:.2f}案例/秒")
        self.loggers['summary'].info("=" * 80)
        
        return summary
    
    def process_input_json(self, input_file: str = "input.json", output_file: str = "answer.jsonl", 
                          debug: bool = False, concurrency: int = None, output_format: str = None, limit: int = None) -> Dict[str, Any]:
        """
        处理input.json文件中的所有故障案例，生成answer.jsonl或answer.json
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            debug: 是否显示调试信息
            concurrency: 并发数量，设置为1可实现串行处理效果，设置为None则使用默认配置
            output_format: 输出格式，'jsonl' 或 'json'，如果为None则根据文件扩展名自动检测
            limit: 限制处理的案例数量，如果为None则处理所有案例
            
        Returns:
            处理结果统计
        """
        # 如果没有指定输出格式，则根据文件扩展名自动检测
        if output_format is None:
            output_format = 'jsonl' if output_file.endswith('.jsonl') else 'json'
        
        return self.process_input_json_parallel(input_file, output_file, debug, concurrency, output_format, limit)