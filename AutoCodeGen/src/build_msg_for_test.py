import argparse
from utils import *


def formatting_test_input_and_output(datas):
    res = []
    for item in datas:
        if not item['success']: continue
        dic = item['original_data']
        dic['demo_test_input'] = item['original_data']['demo_test_func']
        dic['demo_test_output'] = item['demo_test_result']['response']['exec_cout']
        dic['full_test_input'] = item['original_data']['full_test_func']
        dic['full_test_output'] = item['full_test_result']['response']['exec_cout']
        if 'demo_test_func' in dic: del dic['demo_test_func']
        if 'full_test_func' in dic: del dic['full_test_func']
        if '_absolute_line_number' in dic: del dic['_absolute_line_number']
        if '_relative_line_number' in dic: del dic['_relative_line_number']
        if 'extracted_code' in dic: del dic['extracted_code']
        res.append(dic)
    return res


def get_prompt(template, item, mode):
    if mode == "gen_test_function":
        prompt = template.replace("<<<<code>>>>", item['canonical_solution']).replace("<<<<test cases>>>>", item['demo_test_input']).replace("<<<<test case results>>>>", item['demo_test_output']).replace("<<<<test cases2>>>>", item['full_test_input']).replace("<<<<test case results2>>>>", item['full_test_output'])
    else:
        raise ValueError(f"Invalid mode: {mode}")
    return prompt


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw_code_file', type=str, default='python.jsonl')
    parser.add_argument('--raw_code_msg_file', type=str, default='python_solution_msg.jsonl')
    parser.add_argument('--lang', type=str, default='python', choices=['python', 'java', 'cpp', 'javascript', 'go', 'shell'])
    parser.add_argument('--mode', type=str, default='gen_test_function', help='Mode of operation')
    args = parser.parse_args()

    template_file = f"templates/{args.mode}_templates/{args.lang}.txt"
    template = read_file(template_file)

    dt = read_jsonl(args.raw_code_file)


    prev_len = len(dt)
    dt = formatting_test_input_and_output(dt)
    print(f"根据沙盒结果，过滤掉失败的数据共{prev_len - len(dt)}条，剩余{len(dt)}条")

    datas = []
    for i, item in enumerate(tqdm(dt, desc="Processing data")):
        prompt = get_prompt(template, item, args.mode)
        item["messages"] = [
                {"role": "system", "content": ""},
                {"role":"user", "content": prompt}       
            ]
        datas.append(item)
    write_jsonl(datas, args.raw_code_msg_file, mode='w')
    
