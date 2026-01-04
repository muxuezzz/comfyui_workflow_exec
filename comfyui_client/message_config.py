from enum import Enum
from typing import Optional, Type

from pydantic import BaseModel

from config.comfy_schema import APIHistoryEntryStatus, WSExecutingData


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

    # 使用类型注解定义消息数据结构的类型
    @staticmethod
    def get_data_model(msg_type: "JsonMessageType") -> Optional[Type[BaseModel]]:
        """获取对应消息类型的数据模型"""
        mapping = {
            JsonMessageType.EXECUTING: WSExecutingData,
            JsonMessageType.STATUS: APIHistoryEntryStatus,
            # 可以继续添加其他映射
        }
        return mapping.get(msg_type)


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
