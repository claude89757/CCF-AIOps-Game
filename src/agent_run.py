#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author: claude89757
@date: 2025-06-29
@description: CCF AIOps挑战赛 React模式故障诊断智能体（模块化重构版本）
"""

# 导入重构后的模块化智能体
import sys
import os

# 处理相对导入问题
if __name__ == "__main__":
    # 当直接运行时，添加父目录到路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.agent.core import AIOpsReactAgent, AgentStep
    from src.agent.tool_executor import ToolCall
else:
    # 当作为模块导入时，使用相对导入
    from .agent.core import AIOpsReactAgent, AgentStep
    from .agent.tool_executor import ToolCall

# 保持向后兼容性，重新导出主要类
__all__ = ['AIOpsReactAgent', 'AgentStep', 'ToolCall']


def main():
    """主函数 - 比赛模式"""
    import argparse
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='CCF AIOps挑战赛故障诊断智能体')
    parser.add_argument('--model', '-m', 
                       choices=['deepseek-v3:671b', 'qwen3:235b', 'deepseek-r1:671b-0528'],
                       default='deepseek-v3:671b',
                       help='指定使用的模型 (默认: deepseek-v3:671b)')
    parser.add_argument('--iterations', '-i', type=int, default=30,
                       help='最大迭代次数 (默认: 30)')
    parser.add_argument('--retries', '-r', type=int, default=5,
                       help='模型调用最大重试次数 (默认: 5)')
    parser.add_argument('--input', default='input.json',
                       help='输入文件路径 (默认: input.json)')
    parser.add_argument('--output', default='answer.jsonl',
                       help='输出文件路径 (默认: answer.jsonl)')
    parser.add_argument('--debug', action='store_true',
                       help='开启调试模式')
    parser.add_argument('--context-length', type=int,
                       help='手动指定最大上下文长度')
    parser.add_argument('--temperature', type=float,
                       help='手动指定模型温度')
    parser.add_argument('--concurrency', '-c', type=int, default=10,
                       help='并发处理数量 (默认: 10, 设置为1表示串行处理)')
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='限制处理的案例数量 (默认: None, 表示处理所有案例)')
    
    args = parser.parse_args()
    
    # 根据输出文件扩展名自动检测输出格式
    if args.output.endswith('.jsonl'):
        output_format = 'jsonl'
    else:
        output_format = 'json'
    
    # 创建智能体，使用命令行参数配置
    agent_kwargs = {
        'model_name': args.model,
        'max_iterations': args.iterations,
        'max_model_retries': args.retries,
        'concurrency': args.concurrency,
    }
    
    if args.context_length is not None:
        agent_kwargs['max_context_length'] = args.context_length
    if args.temperature is not None:
        agent_kwargs['temperature'] = args.temperature
    
    agent = AIOpsReactAgent(**agent_kwargs)
    
    print("🏆 CCF AIOps挑战赛故障诊断智能体（模块化版本）")
    print("=" * 80)
    print(f"🤖 使用模型: {args.model}")
    print(f"🔄 最大迭代次数: {args.iterations}")
    print(f"🔁 最大重试次数: {args.retries}")
    print(f"⚡ 并发数量: {args.concurrency}")
    print(f"🔧 处理模式: {'串行' if args.concurrency == 1 else '并行'}")
    print(f"📄 输出格式: {output_format.upper()}")
    print(f"🔢 案例限制: {'全量处理' if args.limit is None else f'限制处理前{args.limit}个案例'}")
    print(f"🐛 调试模式: {'开启' if args.debug else '关闭'}")
    print("=" * 80)

    # 处理所有故障案例
    result = agent.process_input_json(
        input_file=args.input,
        output_file=args.output, 
        debug=args.debug,
        concurrency=args.concurrency,
        output_format=output_format,
        limit=args.limit
    )
    
    if result["status"] == "completed":
        print(f"\n🎉 比赛提交文件已生成!")
        print(f"📁 文件位置: {result['output_file']}")
        print(f"📄 输出格式: {result.get('output_format', 'JSON').upper()}")
        print(f"📈 成功率: {result['success_rate']:.1f}%")
        print(f"🎉 完成! 成功率: {result['success_rate']:.1f}%")
    else:
        print(f"\n❌ 处理失败: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main() 