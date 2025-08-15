from flask import Flask, request, jsonify, g
import os
import json
import traceback
import time
import socket
from executor import LanguageExecutor
from code_splicer import CodeSplicer
import datetime
from log import setup_logger
from code import CodeStore
from exec_outcome import ExecOutcome


# 创建日志记录器
logger = setup_logger()

app = Flask(__name__)

# 初始化CodeStore和LanguageExecutor
code_store = CodeStore()
executor = LanguageExecutor()
code_splicer = CodeSplicer()

# 获取出口IP
def get_egress_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# 初始化沙盒IP
SERVER_IP = get_egress_ip()


@app.teardown_request
def teardown_request(exception=None):
    """请求处理完成后的清理和上报函数"""
    try:
        # 检查环境变量是否启用CK上报
        enable_ck_report = os.environ.get('enable_ck_report', '0')
        if enable_ck_report == '0':
            return

        if hasattr(g, 'task_info'):
            from clickhouse_reporter import report_to_ck
            report_to_ck(task_info=g.task_info, server_ip=SERVER_IP, exception=exception)
    except Exception as e:
        logger.error(f"Teardown error: {e}")
        # traceback.print_exc()


@app.route('/splice_code', methods=['POST'])
def splice_code():
    """处理代码拼接请求
    Args:
        src_uid: 请求UID
        lang: 代码编程语言
        func_code: 函数代码
        main_code: 测试代码

    Returns:
        src_uid: 请求UID
        all_code: 完整的代码
    """
    try:
        data = request.json
        # 验证必要参数
        required_fields = ["src_uid", "lang", "func_code", "main_code"]
        for field in required_fields:
            if field not in data or not data[field]:
                logger.warning(f"传入参数{data.keys()}中缺少必要参数")
                return jsonify({
                    "src_uid": data.get("src_uid", ""),
                    "splice_outcome": ExecOutcome.ARGUMENT_ERROR.name,
                    "splice_message": f"Missing required field: {field}",
                }), 200
        spliced_code = code_splicer.splice_code(data["lang"], data["func_code"], data["main_code"]).get("spliced_code", "")
        response = {
            "src_uid": data["src_uid"],
            "all_code": spliced_code,
        }
        logger.info(f"{data.get('src_uid', '')}进行代码拼接请求已处理")
        return jsonify(response)

    except Exception as e:
        logger.error(f"代码拼接过程中发生异常: {str(e)}")
        return jsonify({
            "splice_outcome": ExecOutcome.INTERNAL_ERROR.name,
            "splice_message": f"服务器错误: {str(e)}",
        }), 500


@app.route('/submit', methods=['POST'])
def submit():
    # 初始化请求信息
    now = datetime.datetime.now()
    now64 = now.replace(microsecond=(now.microsecond // 1000) * 1000)
    status = "unknown"
    g.task_info = {
        'task_created_at': now64,
        'status': status
    }

    response_extensions = {"server_ip": SERVER_IP}
    try:
        data = request.json
        # 记录请求基本信息
        g.task_info.update({
            'src_uid': data.get("src_uid", ""),
            'lang': data.get("lang", "")
        })
        is_spliced = False
        # 如果请求参数中没有source_code但是有 func_code 与 main_code，则进行代码拼接
        if "func_code" in data and "main_code" in data and "source_code" not in data:
            spliced_code = code_splicer.splice_code(data["lang"], data["func_code"], data["main_code"]).get("spliced_code", "")
            data["source_code"] = spliced_code
            is_spliced = True
            logger.info(f"{data.get('src_uid', '')}请求未传入source_code，已进行代码拼接")

        # 验证必要参数
        required_fields = ["src_uid", "lang", "source_code"]
        for field in required_fields:
            if field not in data or not data[field]:
                exec_outcome = ExecOutcome.ARGUMENT_ERROR.name
                g.task_info.update({
                    'exec_outcome': f"{exec_outcome}, missing required field: {field}",
                    'exec_runtime': 0
                })
                return jsonify({
                    "src_uid": data.get("src_uid", ""),
                    "all_code": data.get("source_code", "") if is_spliced else "",
                    "exec_cout": "",
                    "exec_outcome": exec_outcome,
                    "exec_compile_message": "",
                    "exec_runtime_message": f"Missing required field: {field}",
                    "response_extensions": response_extensions
                }), 200

        language_config = code_store.build_code_env(data)
        if language_config.get("syntax_error"):
            exec_outcome = ExecOutcome.SYNTAX_ERROR.name
            g.task_info.update({
                'exec_outcome': f"{exec_outcome}, 检测到语法错误",
                'exec_runtime': 0
            })
            logger.info(f"检测到语法错误: {language_config['lang']}")
            return jsonify({
                "src_uid": data.get("src_uid", ""),
                "all_code": data.get("source_code", "") if is_spliced else "",
                "exec_cout": "",
                "exec_outcome": exec_outcome,
                "exec_compile_message": "",
                "exec_runtime_message": "Syntax error detected",
                "response_extensions": response_extensions
            }), 200

        # 设置超时
        DEFAULT_TIMEOUT = 5
        timeout = data.get("request_extensions", {}).get("timeout", DEFAULT_TIMEOUT)
        if not isinstance(timeout, int):
            try:
                timeout = int(timeout)
            except:
                timeout = DEFAULT_TIMEOUT
        # 是否为debug模式
        debug = data.get("request_extensions", {}).get("debug", False)
        # 编译和执行代码
        show_log = data.get("show_log", True)
        exec_cout = ""
        exec_outcome = ExecOutcome.PASSED.name
        exec_compile_message = ""
        exec_runtime_message = ""

        try:
            # 使用已有的execute函数执行代码
            logger.info(f"src_uid: {language_config['src_uid']}, 开始执行代码: {language_config['code_path']}")
            start_time = time.time()
            result = executor.execute(language_config, timeout)
            end_time = time.time()
            exec_runtime = end_time - start_time
            logger.info(f"src_uid: {language_config['src_uid']}, 代码执行完成，耗时: {exec_runtime:.3f}秒")
            result["src_uid"] = language_config["src_uid"]
            logger.info(f"{json.dumps(result)}")
            exec_outcome = result["outcome"]
            exec_cout = result["stdout"]

            # 清理临时目录
            if not debug:
                code_store.destroy_code_env(language_config)
            response_extensions.update(result)
            response_extensions["exec_runtime"] = round(exec_runtime, 3)
            if result["outcome"] == ExecOutcome.PASSED.name:
                status = "succeed"
            else:
                status = "failed"
                if result["outcome"] == ExecOutcome.COMPILATION_ERROR.name:
                    exec_compile_message = result["stderr"]
                elif result["outcome"] == ExecOutcome.RUNTIME_ERROR.name:
                    exec_runtime_message = result["stderr"]
            # 记录执行结果
            g.task_info.update({
                'exec_outcome': exec_outcome,
                'exec_runtime': round(exec_runtime, 3),
                'status': status
            })
        except Exception as e:
            exec_outcome = ExecOutcome.INTERNAL_ERROR.name
            error_trace = traceback.format_exc()
            exec_runtime_message = f"执行异常: {str(e)}\n{error_trace}"
            logger.error(f"src_uid: {language_config['src_uid']}, 代码执行过程中发生异常: {str(e)}")
            logger.error(f"src_uid: {language_config['src_uid']}, 异常堆栈: {error_trace}")

            # 记录错误信息
            g.task_info.update({
                'exec_outcome': f"{exec_outcome}, {error_trace}",
                'exec_runtime': 0
            })

        # 构建响应
        response = {
            "src_uid": data["src_uid"],
            "all_code": data.get("source_code", "") if is_spliced else "",
            "exec_cout": exec_cout,
            "exec_outcome": exec_outcome,
            "exec_compile_message": exec_compile_message if show_log is True and exec_outcome != ExecOutcome.PASSED.name else "",
            "exec_runtime_message": exec_runtime_message if show_log is True and exec_outcome != ExecOutcome.PASSED.name else "",
            "response_extensions": response_extensions
        }

        return jsonify(response)
    except Exception as e:
        # 处理所有异常
        error_trace = traceback.format_exc()
        logger.error(f"请求处理过程中发生严重异常: {str(e)}")
        logger.error(f"异常堆栈: {error_trace}")
        exec_outcome = ExecOutcome.INTERNAL_ERROR.name
        g.task_info.update({
            'exec_outcome': f"{exec_outcome}, {error_trace}",
            'exec_runtime': 0,
        })
        return jsonify({
            "src_uid": request.json.get("src_uid", ""),
            "exec_cout": "",
            "exec_outcome": exec_outcome,
            "exec_compile_message": "",
            "exec_runtime_message": f"服务器错误: {str(e)}\n{error_trace}",
            "response_extensions": response_extensions
        }), 500


if __name__ == '__main__': 
    app.run(host='0.0.0.0', port=8080, debug=False)