#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-28
@description: 模型客户端
"""

import os
import openai
import json
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field


class ModelClient:
    """OpenAI-API-Compatible 模型客户端"""
    
    def __init__(self):
        """初始化模型客户端，从环境变量获取配置"""
        self.api_key = os.getenv('OPENAI_API_TOKEN')
        self.base_url = os.getenv('BASE_URL')
        
        if not self.api_key:
            raise ValueError("环境变量 OPENAI_API_TOKEN 未设置")
        if not self.base_url:
            raise ValueError("环境变量 BASE_URL 未设置")
        
        # 初始化 OpenAI 客户端
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def chat(self, 
            messages: Union[List[Dict[str, str]], str],
            model: str = "deepseek-v3:671b",
            temperature: float = 0.5,
            max_tokens: Optional[int] = None,
            system_prompt: Optional[str] = None,
            debug: bool = False,
            return_full_response: bool = False,
            return_reasoning: bool = False) -> Union[str, Dict[str, Any], tuple[str, str]]:
        """
        简化的对话接口 - 主要使用函数，支持思考类型模型
        
        Args:
            messages: 消息列表或单个字符串（自动转为user消息）
            model: 模型名称
            temperature: 温度参数，控制随机性（R1类模型不支持）
            max_tokens: 最大token数（R1类模型含思考过程，建议设置更大值）
            system_prompt: 系统提示（可选，R1类模型不建议使用）
            debug: 是否显示调试信息
            return_full_response: 是否返回完整响应
            return_reasoning: 是否返回思考过程（仅R1类模型有效）
        
        Returns:
            - 默认: 模型回复文本
            - return_full_response=True: 完整API响应
            - return_reasoning=True: (思考过程, 最终回答) 元组
        """
        # 检测是否是思考类型模型（R1、qwen3等）
        is_reasoning_model = self.is_reasoning_model(model)
        
        # 处理输入格式
        if isinstance(messages, str):
            formatted_messages = [{"role": "user", "content": messages}]
        else:
            formatted_messages = messages.copy()
        
        # 添加系统提示（R1类模型不建议使用）
        if system_prompt:
            if is_reasoning_model and debug:
                print(f"[警告] {model} 不建议使用system_prompt，可能影响推理效果")
            formatted_messages.insert(0, {"role": "system", "content": system_prompt})
        
        # 调试信息
        if debug:
            print(f"[调试] 使用模型: {model}")
            print(f"[调试] 模型类型: {'思考类型模型' if is_reasoning_model else '常规模型'}")
            if is_reasoning_model:
                print(f"[调试] 温度: {temperature} (该模型可能忽略此参数)")
                if max_tokens:
                    print(f"[调试] 最大Token: {max_tokens} (包含思考过程)")
                else:
                    print(f"[调试] 最大Token: 32K (默认，包含思考过程)")
            else:
                print(f"[调试] 温度: {temperature}")
                print(f"[调试] 最大Token: {max_tokens or '默认'}")
            print(f"[调试] 消息数量: {len(formatted_messages)}")
            print(f"[调试] 请求消息:")
            print(json.dumps(formatted_messages, ensure_ascii=False, indent=2))
            print("-" * 50)
        
        try:
            start_time = time.time()
            
            # 为思考类型模型调整参数
            api_params = {
                "model": model,
                "messages": formatted_messages,
                "stream": False
            }
            
            # 只为非思考类型模型设置temperature等参数
            if not is_reasoning_model:
                api_params["temperature"] = temperature
            
            if max_tokens:
                api_params["max_tokens"] = max_tokens
            elif is_reasoning_model:
                # R1类模型建议设置更大的max_tokens，因为包含思考过程
                api_params["max_tokens"] = 32768
            
            response = self.client.chat.completions.create(**api_params)
            end_time = time.time()
            
            # 提取思考过程和回答内容
            reasoning_content = ""
            answer_content = ""
            
            if hasattr(response.choices[0].message, 'reasoning_content') and response.choices[0].message.reasoning_content:
                reasoning_content = response.choices[0].message.reasoning_content
            
            answer_content = response.choices[0].message.content or ""
            
            # 调试信息
            if debug:
                duration = end_time - start_time
                print(f"[调试] 响应时间: {duration:.2f}秒")
                if hasattr(response, 'usage'):
                    usage = response.usage
                    print(f"[调试] Token使用: {usage.total_tokens} (输入: {usage.prompt_tokens}, 输出: {usage.completion_tokens})")
                
                if reasoning_content and is_reasoning_model:
                    print(f"[调试] 思考过程长度: {len(reasoning_content)} 字符")
                    print(f"[调试] 思考过程预览: {reasoning_content[:100]}...")
                    print(f"[调试] 最终回答: {answer_content}")
                print("-" * 50)
            
            # 根据参数返回不同结果
            if return_full_response:
                return response
            elif return_reasoning and reasoning_content:
                return (reasoning_content, answer_content)
            else:
                return answer_content
                
        except Exception as e:
            if debug:
                print(f"[调试] API 调用失败: {e}")
            print(f"API 调用失败: {e}")
            raise

    def chat_completion(self, 
                       messages: List[Dict[str, str]], 
                       model: str = "deepseek-v3:671b",
                       temperature: float = 0.7,
                       max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        发送聊天完成请求（非流式）- 底层接口
        
        Args:
            messages: 消息列表，格式为 [{"role": "user/assistant/system", "content": "内容"}]
            model: 模型名称
            temperature: 温度参数，控制随机性
            max_tokens: 最大token数
        
        Returns:
            API响应结果
        """
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            return response
        except Exception as e:
            print(f"API 调用失败: {e}")
            raise
    
    def simple_query(self, prompt: str, model: str = "deepseek-v3:671b") -> str:
        """
        简单的单轮对话查询
        
        Args:
            prompt: 用户输入的提示
            model: 模型名称
        
        Returns:
            模型回复的文本内容
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.chat_completion(messages, model=model)
        return response.choices[0].message.content
    

    


    
    def extract_content(self, response: Dict[str, Any]) -> str:
        """
        从API响应中提取内容
        
        Args:
            response: API响应对象
        
        Returns:
            提取的文本内容
        """
        try:
            return response.choices[0].message.content
        except (AttributeError, IndexError, KeyError):
            return str(response)
    
    def add_to_conversation(self, conversation: List[Dict[str, str]], user_input: str, assistant_response: str) -> List[Dict[str, str]]:
        """
        向对话历史添加一轮对话，适配思考类型模型
        
        Args:
            conversation: 现有对话历史
            user_input: 用户输入
            assistant_response: 助手回复（注意：对于思考类型模型，这应该是content字段，不包含reasoning_content）
        
        Returns:
            更新后的对话历史
        """
        new_conversation = conversation.copy()
        new_conversation.append({"role": "user", "content": user_input})
        new_conversation.append({"role": "assistant", "content": assistant_response})
        return new_conversation
    
    def is_reasoning_model(self, model: str) -> bool:
        """
        检测是否是思考类型模型
        
        Args:
            model: 模型名称
        
        Returns:
            是否为思考类型模型
        """
        return any(keyword in model.lower() for keyword in ['r1', 'qwen3', 'reasoner'])
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取可用的模型列表
        
        Returns:
            模型列表，每个模型包含 id, object, created, owned_by 等信息
        """
        try:
            response = self.client.models.list()
            return response.data
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            raise
    
    def list_models(self) -> None:
        """
        打印可用模型列表（格式化输出）
        """
        try:
            models = self.get_available_models()
            print("=== 可用模型列表 ===")
            for i, model in enumerate(models, 1):
                model_id = model.get('id', 'Unknown')
                owned_by = model.get('owned_by', 'Unknown')
                created = model.get('created', 'Unknown')
                print(f"{i}. 模型ID: {model_id}")
                print(f"   提供方: {owned_by}")
                print(f"   创建时间: {created}")
                print()
        except Exception as e:
            print(f"列出模型失败: {e}")
    
    def get_model_names(self) -> List[str]:
        """
        获取所有模型的ID列表
        
        Returns:
            模型ID列表
        """
        try:
            models = self.get_available_models()
            return [model.get('id', '') for model in models]
        except Exception as e:
            print(f"获取模型名称列表失败: {e}")
            return []


def create_model_client() -> ModelClient:
    """创建模型客户端实例"""
    return ModelClient()


# 示例使用
if __name__ == "__main__":
    try:
        # 创建客户端
        client = create_model_client()
        
        # 查看可用模型
        client.list_models()
        model_names = client.get_model_names()
        selected_model = model_names[0] if model_names else "deepseek-v3:671b"
        print(f"使用模型: {selected_model}\n")
        
        # 多轮对话示例 - 根据模型类型选择不同演示
        print("=== 多轮对话示例 ===")
        
        # 检测是否是思考类型模型
        if client.is_reasoning_model(selected_model):
            print(f"检测到思考类型模型: {selected_model}")
            print("演示思考过程功能...\n")
            
            # 第一轮 - 展示思考过程
            print("--- 第一轮：数学推理题 ---")
            reasoning, answer = client.chat(
                "9.9和9.11哪个更大？请详细解释",
                model=selected_model,
                return_reasoning=True
            )
            print("思考过程:")
            print(reasoning[:200] + "..." if len(reasoning) > 200 else reasoning)
            print(f"\n最终回答: {answer}\n")
            
            # 第二轮 - 多轮对话（注意：只添加content到历史，不添加reasoning）
            print("--- 第二轮：继续对话 ---")
            conversation = []
            # 使用辅助方法添加对话历史
            conversation = client.add_to_conversation(conversation, "9.9和9.11哪个更大？", answer)
            conversation.append({"role": "user", "content": "那0.9和0.11呢？"})
            
            reply2 = client.chat(conversation, model=selected_model, debug=True)
            print(f"第二轮回复: {reply2}\n")
            
        else:
            print(f"使用常规模型: {selected_model}")
            # 开始对话
            conversation = [{"role": "system", "content": "你是一个编程助手"}]
            
            # 第一轮
            conversation.append({"role": "user", "content": "如何学习Python？"})
            reply1 = client.chat(conversation, model=selected_model)
            print(f"第一轮回复: {reply1}\n")
            conversation.append({"role": "assistant", "content": reply1})
            
            # 第二轮  
            conversation.append({"role": "user", "content": "推荐一些学习资源"})
            reply2 = client.chat(conversation, model=selected_model)
            print(f"第二轮回复: {reply2}\n")
            conversation.append({"role": "assistant", "content": reply2})
            
            # 第三轮 - 带调试
            conversation.append({"role": "user", "content": "给我一个简单的代码例子"})
            reply3 = client.chat(conversation, model=selected_model, debug=True)
            print(f"第三轮回复: {reply3}\n")
        
    except Exception as e:
        print(f"运行出错: {e}")
        print("请确保环境变量 OPENAI_API_TOKEN 和 BASE_URL 已正确设置")
