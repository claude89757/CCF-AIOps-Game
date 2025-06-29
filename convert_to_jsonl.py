#!/usr/bin/env python3

import json
import argparse

def convert_json_to_jsonl(input_file, output_file):
    """
    将JSON数组文件转换为JSONL格式文件
    
    Args:
        input_file (str): 输入的JSON文件路径
        output_file (str): 输出的JSONL文件路径
    """
    try:
        # 读取JSON数组文件
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 确保输入是一个列表
        if not isinstance(data, list):
            print(f"错误: {input_file} 不是一个JSON数组格式")
            return False
        
        # 写入JSONL文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in data:
                json.dump(item, f, ensure_ascii=False, separators=(',', ':'))
                f.write('\n')
        
        print(f"成功转换! 从 {input_file} 转换为 {output_file}")
        print(f"共转换了 {len(data)} 条记录")
        return True
        
    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_file}")
        return False
    except json.JSONDecodeError as e:
        print(f"错误: JSON格式有误 - {e}")
        return False
    except Exception as e:
        print(f"错误: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将JSON数组文件转换为JSONL格式")
    parser.add_argument('input_file', nargs='?', default='answer.json', 
                       help='输入的JSON文件路径 (默认: answer.json)')
    parser.add_argument('output_file', nargs='?', default='result.jsonl', 
                       help='输出的JSONL文件路径 (默认: result.jsonl)')
    
    args = parser.parse_args()
    
    convert_json_to_jsonl(args.input_file, args.output_file) 