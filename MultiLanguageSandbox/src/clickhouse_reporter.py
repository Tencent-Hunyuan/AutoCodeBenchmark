from clickhouse_driver import Client
from log import setup_logger
import os
import uuid
import datetime
import traceback

# 创建日志记录器
logger = setup_logger()


def report_to_ck(task_info, server_ip, exception=None):
    """上报数据到 ClickHouse

    Args:
        exception: 如果请求处理过程中发生异常，这里会包含异常信息
    """
    try:
        sandbox_type = "multi_language"
        # 保证上报数据准确，需要部署时新增以下环境变量
        env = os.environ.get('env', '')
        password = os.environ.get('password', '')
        host = os.environ.get('host', '')
        task_type = os.environ.get('task_type', 'unknown')

        # 以下环境变量不设置会使用默认值
        try:
            port = int(os.environ.get('port', '9000'))
        except ValueError:
            logger.warning("Invalid port value in environment variable, using default 9000")
            port = 9000
        user = os.environ.get('user', 'chat_ops_system')
        database = os.environ.get('database', 'evaluation')

        logger.info(f"准备上报数据到ClickHouse, 环境: {env}, CK地址: {host}")

        client = Client(host=host, port=port, user=user, password=password, database=database)

        # 计算任务执行时间（毫秒）
        task_id = uuid.uuid4().hex
        task_created_at = task_info.get('task_created_at', 0)
        result_created_at = datetime.datetime.now()
        task_execute_duration = int((result_created_at - task_created_at).total_seconds() * 1000)
        # task_execute_duration = int(g.task_info.get('exec_runtime', 0) * 1000)  # 转换为毫秒
        status = task_info.get('status', 'unknown')
        reason = task_info.get('exec_outcome', 'unknown')

        # 准备插入数据
        insert_data = [
            (
                task_id,                                  # task_id
                task_type,                                # task_type
                sandbox_type,                             # sandbox_type
                task_created_at,                               # task_created_at
                result_created_at,                        # result_created_at
                task_execute_duration,                    # task_execute_duration
                task_info.get('lang', ''),              # code_language
                '',                                       # agentless_run_id
                '',                                       # dataset_name
                '',                                       # split
                str(task_info.get('src_uid', '')),      # instance_id
                '',                                       # patch
                status,      # status
                0.00,                                     # score
                reason,      # reason
                server_ip,                                # instance_report
                ''                                        # task_report
            )
        ]

        # 执行插入
        client.execute(
            """
            INSERT INTO task_result 
            (
                task_id, task_type, sandbox_type, task_created_at, result_created_at, 
                task_execute_duration, code_language, agentless_run_id, dataset_name, split, 
                instance_id, patch, status, score, reason, instance_report, task_report
            ) VALUES
            """,
            insert_data
        )
        logger.info("数据成功上报到ClickHouse")
    except Exception as e:
        logger.error(f"Error reporting to ClickHouse: {e}, insert_data: {insert_data}")
        traceback.print_exc()