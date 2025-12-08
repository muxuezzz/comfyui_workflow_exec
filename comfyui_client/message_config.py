from enum import Enum


class BinaryMessageType(Enum):
    """二进制消息类型枚举"""

    PREVIEW_IMAGE = 1
    METADATA_PREVIEW_IMAGE = 2
    TEXT_MESSAGE = 3


class JsonMessageType(Enum):
    """JSON消息类型枚举"""

    STATUS = "status"
    EXECUTION_START = "execution_start"
    EXECUTION_CACHED = "execution_cached"
    EXECUTING = "executing"
    EXECUTED = "executed"
    PROGRESS = "progress"
    PROGRESS_STATE = "progress_state"
    EXECUTION_ERROR = "execution_error"
    EXECUTION_INTERRUPTED = "execution_interrupted"
    EXECUTION_SUCCESS = "execution_success"


class MessageHandlingPolicy(Enum):
    """消息处理策略枚举"""

    # 生产环境：只处理关键消息
    PRODUCTION = [
        JsonMessageType.EXECUTION_ERROR,
        JsonMessageType.EXECUTION_INTERRUPTED,
        JsonMessageType.EXECUTION_SUCCESS,
        JsonMessageType.EXECUTING,
    ]

    # 开发环境：处理所有消息
    DEVELOPMENT = list(JsonMessageType)
