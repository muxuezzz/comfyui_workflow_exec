# workflow_manager/exceptions.py
class WorkflowError(Exception):
    """项目基础异常类"""

    pass


class ConfigValidationError(WorkflowError):
    """配置文件验证失败"""

    pass


class WorkflowConnectionError(WorkflowError):
    """ComfyUI连接相关错误"""

    pass


class WorkflowExecutionError(WorkflowError):
    """工作流执行错误"""

    pass


class FileNotFoundError(WorkflowError):
    """文件未找到（覆盖内置但保持一致性）"""

    pass
