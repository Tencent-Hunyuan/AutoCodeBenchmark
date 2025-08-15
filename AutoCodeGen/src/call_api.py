# This script is adapted from https://github.com/hkust-nlp/CodeIO/blob/master/src/batched_api_inference.py

try:
    from openai import OpenAI
except:
    pass
import datetime
import json
import multiprocessing
from argparse import ArgumentParser
import os
import time
from tqdm import tqdm

from multiprocessing import Process, Queue, Lock, Value
import concurrent
from concurrent.futures import ThreadPoolExecutor

###############################################
max_try_one_call = 3
SYSTEM = None
###############################################

def get_client():
    assert model.startswith("gpt") or model.startswith("deepseek")
    params = {
                "api_key": key, 
                "timeout":10000.0
            }
    if model.startswith("deepseek"):
        params["base_url"] = "https://api.deepseek.com"

    client = OpenAI(
        **params
    )
    return client

def timer(func):
    def format_time(time_delta):
        hours, remainder = divmod(time_delta.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    def wrapper(*args, **kwargs):
        start_time = datetime.datetime.now()
        print("开始时间：", start_time.strftime("%Y-%m-%d %H:%M:%S"))
        result = func(*args, **kwargs)
        end_time = datetime.datetime.now()
        print("结束时间：", end_time.strftime("%Y-%m-%d %H:%M:%S"))
        elapsed_time = end_time - start_time
        print("执行时间：", format_time(elapsed_time))
        return result
    return wrapper

def load_jsonl_yield(path):
    with open(path) as f:
        for row, line in enumerate(f):
            try:
                line = json.loads(line)
                yield line
            except:
                pass

def check_exists(line):
    if "output" in line and line["output"] is not None:
        return True
    return False

def process_line(js, good_cnt, bad_cnt, lock, output_path):
    messages = js['messages']
    response = None
    finish_reason = None
    for i in range(max_try_one_call): # retry if failed 
        try:
            client = get_client()
            chat_completion = client.chat.completions.create(
                model = model,
                messages = messages,
                max_tokens = max_tokens,
                temperature = temperature,
                timeout=10000.0
            )
            if model == "deepseek-reasoner":
                reasoning = chat_completion.choices[0].message.reasoning_content
            else:
                reasoning = None
            response = chat_completion.choices[0].message.content
            finish_reason = chat_completion.choices[0].finish_reason
            break
        except Exception as e:
            if i<max_try_one_call-1:
                time.sleep(5)

    if response is not None and (finish_reason == 'stop' or finish_reason == 'end_turn'):
        js['output'] = response
        # js['model'] = model
        # js['reasoning'] = reasoning
        json_output = json.dumps(js, ensure_ascii=False)
        with good_cnt.get_lock():
            good_cnt.value += 1
        with lock:
            with open(output_path, 'a', encoding='utf-8', errors='ignore') as f:
                f.write(json_output+'\n')
    else:
        with bad_cnt.get_lock():
            bad_cnt.value += 1
    del js

def counter_proc_main(good_cnt, bad_cnt, should_stop):
    while not should_stop.value:
        with good_cnt.get_lock():
            with bad_cnt.get_lock():
                print(f"good: {good_cnt.value}, bad: {bad_cnt.value}")
        time.sleep(10.0)

def proc_main(data, good_cnt, bad_cnt, num_process, num_thread, process_i, file_lock, output_path):
    with ThreadPoolExecutor(max_workers=num_thread) as executor:
        futures = []
        for i in range(process_i, len(data), num_process):
            future = executor.submit(process_line, data[i], good_cnt, bad_cnt, file_lock, output_path)
            time.sleep(0.1)
            futures.append(future)
        for future in concurrent.futures.as_completed(futures):
            future.result()
    print("proc_main exit")

@timer
def process_file(input_file_path, output_file_path, args):
    print(f'The calling model is {model}')
    inlines = load_jsonl_yield(input_file_path)

    exist = set()
    if os.path.exists(output_file_path):
        with open(output_file_path) as f:
            for line in f:
                line = json.loads(line)
                if check_exists(line):
                    exist.add(line['index']) # index be the id in input_file

    data = []
    good_cnt = Value('i', 0)
    bad_cnt = Value('i', 0)
    should_stop = Value('i', 0)
    file_lock = Lock()
    valid = 0

    for index, js in tqdm(enumerate(inlines)):
        if index in exist:
            continue

        js['index'] = index

        if js['messages'] is not None: 
            data.append(js)
            valid += 1

    manager = multiprocessing.Manager()
    data = manager.list(data)

    print("Total Lines To Generate (remove existing): ", valid)

    procs = []
    for i in range(args.num_process):
        proc = Process(target=proc_main, args=(data, good_cnt, bad_cnt, args.num_process, args.num_thread, i, file_lock, output_file_path))
        proc.start()
        procs.append(proc)

    counter_proc = Process(target=counter_proc_main, args=(good_cnt, bad_cnt, should_stop))
    counter_proc.start()
    for proc in procs:
        proc.join()
    should_stop.value = 1
    counter_proc.join()

    print("all finished")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--input",  default="xx", type=str)
    parser.add_argument("--output", default="xx", type=str)
    parser.add_argument("--model", default="deepseek-chat", type=str)
    parser.add_argument("--num_process",  default=10, type=int)
    parser.add_argument("--num_thread",  default=10, type=int)
    parser.add_argument("--key",  default="xx", type=str)
    parser.add_argument("--temperature",  default=0.0, type=float)
    parser.add_argument("--max_tokens",  default=4096, type=int)

    args = parser.parse_args()
    args.output = args.output.format(args.model)

    model = args.model
    temperature = args.temperature
    max_tokens = args.max_tokens
    key = args.key

    num_process = args.num_process
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    process_file(args.input, args.output, args)
    