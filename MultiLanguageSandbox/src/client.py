import json
import uuid
import time
import requests
import os
import argparse
from polaris.api.consumer import create_consumer_by_default_config_file
from polaris.pkg.model.service import GetOneInstanceRequest, GetInstancesRequest, ServiceCallResult

# service_name：北极星服务名
# service_uri：服务请求路径
server = {
    "multi_language": {
        "service_name": "hunyuan-multi-language-sandbox",
        "service_uri": "/submit"
    }
}

g_consumer_api = None


def get_consumer_api():
    global g_consumer_api
    if not g_consumer_api:
        g_consumer_api = create_consumer_by_default_config_file()
    return g_consumer_api


def get_url(lang: str, env: str = "Production") -> str:
    server_info = server.get("multi_language")
    if not server_info:
        raise ValueError(f"lang is not supported: {lang}")
    service_name = server_info["service_name"]
    request = GetOneInstanceRequest(
        namespace=env,
        service=service_name,
    )
    print(server_info)
    try:
        instance = get_consumer_api().get_one_instance(request)
        host = instance.get_host()
        port = instance.get_port()
        uri = server_info["service_uri"]
        if uri.startswith("/"):
            return f"http://{host}:{port}{uri}"
        return f"http://{host}:{port}/{uri}"
    except Exception as e:
        print("Get instance error: ", e)


def execute(lang: str, source_code: str, sandbox_type: str = "General", compile_cmd: str = None, execute_cmd: str = None, show_log: bool = True) -> json:
    request_body = {
        "src_uid": uuid.uuid4().hex,
        "sandbox_type": sandbox_type,
        "lang": lang,
        "source_code": source_code,
        "show_log": show_log,
        "request_extensions": {
            "target": "test",
            "timeout": 1.0,
            "debug": False,
        }
    }
    if compile_cmd:
        request_body["compile_cmd"] = compile_cmd
    if execute_cmd:
        request_body["execute_cmd"] = execute_cmd
    url = get_url(lang=lang.lower(), env="Production")
    # print(json.dumps(request_body, ensure_ascii=False))
    response = requests.post(url=url, json=request_body, headers={"Content-Type": "application/json"})
    if response.status_code != 200:
        raise Exception(f"请求失败（{response.status_code}）: {url} request_body: {json.dumps(request_body, ensure_ascii=False)}")
    return response.json()

def test_code_files(code_dir="test/samples", language=None):
    print("语言\t代码名\t预期结果\t实际结果\t是否通过\t执行时间(s)")
    if not os.path.exists(code_dir):
        print(f"代码目录不存在: {code_dir}")
        return
    for file in os.listdir(code_dir):
        file_language = file.split(".")[-1]
        # 如果指定了语言，只处理该语言的测试文件
        if language and file_language != language:
            continue
        expected_result = file.split(".")[-2]
        if expected_result != "passed" and expected_result != "wrong_answer":
            expected_result = "passed"
        with open(os.path.join(code_dir, file), "r") as f:
            code_content = f.read()
            start_time = time.time()
            actual_result = execute(lang=file_language, source_code=code_content)
            end_time = time.time()
            # print(actual_result["exec_runtime_message"])
            print(file_language, file, expected_result, actual_result["exec_outcome"].lower(), actual_result["exec_outcome"].lower() == expected_result, round(end_time - start_time, 2), sep="\t")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='测试代码文件')
    parser.add_argument('--code_dir', default='test/samples', help='代码目录路径，默认为 test/samples')
    parser.add_argument('--language', help='要测试的编程语言，不指定则测试所有语言')

    args = parser.parse_args()
    test_code_files(args.code_dir, args.language)