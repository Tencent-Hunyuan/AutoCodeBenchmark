import argparse
from utils import *


def get_prompt(template, item):
    prompt = template.replace("<<<code>>>", item['canonical_solution']).replace("<<<demo_test>>>", item['demo_test_func']).replace("<<<full_test>>>", item['full_test_func']).replace("<<<problem>>>", item['question'])
    return prompt


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw_code_file', type=str, default='python.jsonl')
    parser.add_argument('--raw_code_msg_file', type=str, default='python_solution_msg.jsonl')
    parser.add_argument('--source_lang', type=str, default='python', choices=['python', 'java', 'cpp', 'javascript', 'go', 'shell'])
    parser.add_argument('--target_lang', type=str, default='python')
    args = parser.parse_args()

    template_file = f"templates/translate_templates/{args.target_lang}.txt"
    template = read_file(template_file)

    dt = read_jsonl(args.raw_code_file)

    datas = []
    for i, item in enumerate(dt):
        prompt = get_prompt(template, item)
        item["messages"] = [
                {"role": "system", "content": ""},
                {"role":"user", "content": prompt}       
            ]
        item['language'] = args.target_lang
        if 'canonical_solution' in item: del item['canonical_solution']
        if 'demo_test_func' in item: del item['demo_test_func']
        if 'full_test_func' in item: del item['full_test_func']
        if 'question' in item: del item['question']
        datas.append(item)
    write_jsonl(datas, args.raw_code_msg_file, mode='w')
    
