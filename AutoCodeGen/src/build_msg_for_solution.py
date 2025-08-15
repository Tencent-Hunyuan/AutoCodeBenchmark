import argparse
from utils import *


def get_prompt(template, item, mode):
    if mode == "gen_code_solution":
        prompt = template.replace("<<<<code>>>>", item['text'])
    else:
        raise ValueError(f"Invalid mode: {mode}")
    return prompt


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw_code_file', type=str, default='python.jsonl')
    parser.add_argument('--raw_code_msg_file', type=str, default='python_solution_msg.jsonl')
    parser.add_argument('--lang', type=str, default='python', choices=['python', 'java', 'cpp', 'javascript', 'go', 'shell'])
    parser.add_argument('--mode', type=str, default='gen_code_solution', help='Mode of operation')
    args = parser.parse_args()

    template_file = f"templates/{args.mode}_templates/{args.lang}.txt"
    template = read_file(template_file)

    dt = read_jsonl(args.raw_code_file)

    datas = []
    for i, item in enumerate(tqdm(dt, desc="Processing data")):
        prompt = get_prompt(template, item, args.mode)
        data = {
            "messages":[
                {"role": "system", "content": ""},
                {"role":"user", "content": prompt}       
            ],
            "index": i,
            "lang": args.lang,
            "seed": item['text']
        }
        datas.append(data)
    write_jsonl(datas, args.raw_code_msg_file, mode='w')
    
