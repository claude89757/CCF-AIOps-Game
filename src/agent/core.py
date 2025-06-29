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
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

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
                 max_context_length: Optional[int] = None, temperature: Optional[float] = None):
        """
        初始化Agent
        
        Args:
            model_name: 使用的模型名称
            max_iterations: 最大迭代次数，防止无限循环
            max_model_retries: 模型调用最大重试次数
            max_context_length: 模型支持的最大上下文长度（tokens），如果为None则使用模型的建议配置
            temperature: 模型生成温度，0.0为确定性输出，值越高随机性越强，如果为None则使用模型的建议配置
        """
        # 初始化配置
        self.config = AgentConfig()
        self.config.max_iterations = max_iterations
        self.config.max_model_retries = max_model_retries
        
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
            
            while iteration < self.config.max_iterations:
                iteration += 1
                self.current_step += 1
                
                self.loggers['diagnosis'].info(f"第 {iteration} 轮推理开始...")
                
                if debug:
                    print(f"\n🔄 第 {iteration} 轮推理...")
                
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
                    
                    # 如果是早期错误（前3轮），尝试继续
                    if iteration <= 3:
                        continue_msg = "早期错误，尝试继续执行..."
                        self.loggers['diagnosis'].warning(continue_msg)
                        self.loggers['interaction'].warning(continue_msg)
                        continue
                    else:
                        break
            
            # 达到最大迭代次数或其他原因结束
            result_summary = {
                "status": "incomplete",
                "result": final_result,
                "steps": self.steps,
                "iterations": iteration,
                "reason": "达到最大迭代次数" if iteration >= self.config.max_iterations else "执行中断"
            }
            
            self.loggers['diagnosis'].warning(f"诊断未完成: {result_summary['reason']}")
            return result_summary
            
        except Exception as e:
            self.error_handler.log_error_with_context(e, "诊断单个案例", uuid, self.case_error_logger)
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
        print(f"🚀 开始处理故障案例")
        if debug:
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
            print(f"❌ 读取输入文件失败")
            self.loggers['summary'].error(error_msg)
            self.error_handler.log_error_with_context(e, "读取输入文件")
            return {"status": "error", "error": str(e)}
        
        print(f"📊 共 {len(cases)} 个案例")
        self.loggers['summary'].info(f"共发现 {len(cases)} 个故障案例")
        
        # 处理所有案例
        results = []
        successful_count = 0
        failed_count = 0
        
        for i, case in enumerate(cases):
            try:
                if debug:
                    print(f"\n{'='*80}")
                    print(f"进度: {i+1}/{len(cases)} - {(i+1)/len(cases)*100:.1f}%")
                else:
                    print(f"处理案例 {i+1}/{len(cases)}", end=" ", flush=True)
                
                self.loggers['summary'].info(f"处理案例 {i+1}/{len(cases)}: {case.get('uuid', 'unknown')}")
                
                # 诊断单个案例
                diagnosis_result = self.diagnose_single_case(case, debug=debug)
                
                if diagnosis_result["status"] == "completed" and diagnosis_result["result"]:
                    results.append(diagnosis_result["result"])
                    successful_count += 1
                    success_msg = f"案例 {case['uuid']} 诊断完成"
                    if debug:
                        print(f"✅ {success_msg}")
                    else:
                        print("✅")
                    self.loggers['summary'].info(success_msg)
                else:
                    failed_count += 1
                    fail_msg = f"案例 {case['uuid']} 诊断失败: {diagnosis_result.get('reason', '未知原因')}"
                    if debug:
                        print(f"❌ {fail_msg}")
                    else:
                        print("❌")
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
                if debug:
                    print(f"❌ {error_msg}")
                else:
                    print("❌")
                self.loggers['summary'].error(error_msg)
                self.loggers['interaction'].error(error_msg)  # 也记录到交互日志
                self.error_handler.log_error_with_context(e, f"处理案例 {case.get('uuid', 'unknown')}")
                failed_count += 1
                
                # 无论是否debug都记录完整异常信息到日志
                import traceback
                full_traceback = traceback.format_exc()
                self.loggers['interaction'].debug(f"处理案例异常堆栈:\n{full_traceback}")
                
                if debug:
                    traceback.print_exc()
        
        # 保存结果
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            save_msg = f"结果已保存到 {output_file}"
            if debug:
                print(f"\n✅ {save_msg}")
            else:
                print(f"\n✅ 已保存到 {output_file}")
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
            "output_file": output_file
        }
        
        if debug:
            print(f"\n{'='*80}")
            print(f"📊 处理完成统计:")
            print(f"总案例数: {summary['total_cases']}")
            print(f"成功案例: {summary['successful_cases']}")
            print(f"失败案例: {summary['failed_cases']}")
            print(f"成功率: {summary['success_rate']:.1f}%")
            print(f"{'='*80}")
        else:
            print(f"\n📊 完成: 成功{summary['successful_cases']}/{summary['total_cases']} ({summary['success_rate']:.1f}%)")
        
        # 记录最终统计信息
        self.loggers['summary'].info("=" * 80)
        self.loggers['summary'].info("处理完成统计:")
        self.loggers['summary'].info(f"总案例数: {summary['total_cases']}")
        self.loggers['summary'].info(f"成功案例: {summary['successful_cases']}")
        self.loggers['summary'].info(f"失败案例: {summary['failed_cases']}")
        self.loggers['summary'].info(f"成功率: {summary['success_rate']:.1f}%")
        self.loggers['summary'].info("=" * 80)
        
        return summary 