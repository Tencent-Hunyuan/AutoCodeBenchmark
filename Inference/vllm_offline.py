import argparse
import os
from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
import json


def write_jsonl(output_file, data, append=True):
    mode = 'a' if append else 'w'
    with open(output_file, mode, encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')



class SelfServer:
    def __init__(self, args):
        if args.max_tokens >= 32768:
            rope_scaling = {
            "rope_type": "yarn",
            "factor": 4.0,
            "original_max_position_embeddings": 32768
        }
            self.llm = LLM(model=args.model_path, tokenizer=args.model_path, tensor_parallel_size=args.tp, rope_scaling=rope_scaling, trust_remote_code=True)
        else:
            self.llm = LLM(model=args.model_path, tokenizer=args.model_path, tensor_parallel_size=args.tp, trust_remote_code=True)
        self.tokenizer = AutoTokenizer.from_pretrained(args.model_path,trust_remote_code=True)

    def generate(self, prompts, sampling_params, enable_thinking):
        inputs_ = []
        for mes in prompts:
            if type(mes) is str:
                system_prompt = """You are an expert programmer. Your task is to provide a code solution within a single Markdown code block for the given programming problem. Do not include any direct execution commands, test cases, or usage examples within the code block."""
                mes = mes.split("<question>")[-1].split("</question>")[0].strip()
                mes = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": mes}
                ]
            text = self.tokenizer.apply_chat_template(
                    mes,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=enable_thinking
                )
            inputs_.append(text)

        outputs = self.llm.generate(prompts=inputs_, sampling_params=sampling_params)

        result_list = []
        result_with_think_list = []
        for output in outputs:
            result_list.append([o.text.split("</think>")[-1] for o in output.outputs])
            result_with_think_list.append([o.text for o in output.outputs])
        return result_list, result_with_think_list



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', type=str, default='autocodebench.jsonl')
    parser.add_argument('--output_file', type=str, default='output.json')
    parser.add_argument('--model_path', type=str, default='qwen3')
    parser.add_argument('--enable_thinking', action='store_true', help='reasoning mode')
    parser.add_argument('--greedy', action='store_true', help='greedy decoding')
    parser.add_argument('--tp', type=int, default=8)
    parser.add_argument('--n', type=int, default=10)
    parser.add_argument('--max_tokens', type=int, default=10)
    parser.add_argument('--batch_size', type=int, default=128)
    args = parser.parse_args()

    # 打印所有参数
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    print("=========")

    task_file = args.task
    
    dataset = []
    with open(task_file, encoding="utf8") as file:
        for line in file:
            d = json.loads(line)
            dataset.append(d)

    messages_key = "question"
    out_key = "output"
    out_with_think_key = out_key + "_with_think"

    print(len(dataset))

    # # 过滤已有数据
    if os.path.exists(args.output_file):
        with open(args.output_file, 'r',encoding='utf-8') as file:
            existed_data = [json.loads(line) for line in file]
            existed_ids = set([item['question'].strip() for item in existed_data])
        datas = [item for item in dataset if item['question'].strip() not in existed_ids]

    if args.enable_thinking:
        sampling_params = SamplingParams(n=args.n, temperature=0.6, top_p=0.95, top_k=20, max_tokens=args.max_tokens)
    elif args.greedy:
        sampling_params = SamplingParams(n=args.n, temperature=0, max_tokens=args.max_tokens)
    
    model_server = SelfServer(args)

    # vllm
    example_groups = [dataset[i:i+args.batch_size] for i in range(0, len(dataset), args.batch_size)]

    for i, example_group in enumerate(example_groups):
        print(i, "/", len(example_groups))
        prompts = [example[messages_key] for example in example_group]
        responses, responses_with_think = model_server.generate(prompts, sampling_params, args.enable_thinking)
        for response, response_with_think, example in zip(responses, responses_with_think, example_group):
            for res, rest in zip(response, response_with_think):
                example[out_key] = res
                write_jsonl(args.output_file, example, append=True)
