import os
import logging

# 固定日志目录
LOG_DIR = "/data/logs"

def setup_logger(name="sandbox", file_name=None):
    """设置并返回配置好的日志记录器
    
    Args:
        name (str): 日志记录器名称，默认为"sandbox"
        file_name (str): 日志文件名，如果为None则使用name.log
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    global LOG_DIR
    logger = logging.getLogger(name)
    
    # 如果记录器已经有处理器，直接返回
    if logger.handlers:
        return logger
    
    # 创建日志目录
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception as e:
        print(f"创建日志目录失败: {e}, 尝试使用当前目录")
        LOG_DIR = os.getcwd()
        os.makedirs(f"{LOG_DIR}/logs", exist_ok=True)

    # 设置日志文件路径
    if file_name is None:
        file_name = f"{name}.log"
    
    log_file = os.path.join(LOG_DIR, file_name)
    
    logger.setLevel(logging.INFO)

    # 创建文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 将处理器添加到记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 创建默认的日志记录器
logger = setup_logger("sandbox")
logger.info("日志系统初始化完成")
