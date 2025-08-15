import argparse
from utils import *
import re

def extract_code_blocks(text):
    # 正则表达式匹配以 ```{language} 和 ``` 包裹的代码块
    pattern = r'```(\w+)\s([\s\S]*?)```'
    matches = re.findall(pattern, text)
    code_blocks = []
    try:
        for match in matches:
            language, code = match
            code_blocks.append((language, code.strip()))
        assert len(code_blocks) == 2
        return code_blocks
    except:
        return None


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default='python.jsonl')
    parser.add_argument('--output', type=str, default='python_solution_msg.jsonl')
    args = parser.parse_args()

    dt = read_jsonl(args.input)

    datas = []
    for i, item in enumerate(dt):
        if not item['success']: continue
        item = item['original_data']
        if '_absolute_line_number' in item:
            del item['_absolute_line_number']
        if '_relative_line_number' in item:
            del item['_relative_line_number']
        if 'extracted_code' in item:
            del item['extracted_code']
        datas.append(item)
    write_jsonl(datas, args.output, mode='w')
    
