import logging
import sys


def setup_logger(
    name: str = "comfyui_exec", level: int = logging.INFO, log_file: str | None = None
) -> logging.Logger:
    """
    统一的日志配置函数

    Args:
        name: Logger名称
        level: 日志级别
        log_file: 可选的日志文件路径

    Returns:
        配置好的Logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 防止重复添加handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
