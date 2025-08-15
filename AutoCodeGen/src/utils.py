import json
import os
from tqdm import tqdm


def read_file(file_path):
    with open(file_path, "r", encoding='utf8') as f:
        return f.read()

def read_jsonl(jsonl_file_path):
    s = []
    with open(jsonl_file_path, "r", encoding='utf8') as f:
        # lines = f.readlines()
        for line in tqdm(f, desc="Reading JSONL file"):
            linex = line.strip()
            if linex == "":
                continue
            s.append(json.loads(linex))
    return s

def write_jsonl(data, jsonl_file_path, mode="w"):
    # data is a list, each of the item is json-serializable
    assert isinstance(data, list)
    if len(data) == 0:
        return
    if not os.path.exists(os.path.dirname(jsonl_file_path)):
        print(f"create dir {os.path.dirname(jsonl_file_path)}")
        os.makedirs(os.path.dirname(jsonl_file_path))
    with open(jsonl_file_path, mode, encoding='utf8') as f:
        for item in tqdm(data, desc="Writing JSONL file"):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
