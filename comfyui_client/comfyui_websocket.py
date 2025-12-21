import json
import logging
import struct
import uuid
from typing import Any, Callable, Dict, List, Optional

import websocket
from pydantic import ValidationError

from config.comfy_schema import (
    APIHistoryEntry,
    APINodeID,
    PromptID,  # 历史条目
    WSExecutingData,  # 执行数据
    WSMessage,  # WebSocket消息
)

from ..workflow_manager.exceptions import WorkflowConnectionError
from .comfyui_client import ComfyUIClientBase
from .message_config import BinaryMessageType, JsonMessageType, MessageHandlingPolicy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        # 可选：添加文件处理器
        # logging.FileHandler('comfyui_client.log', encoding='utf-8')
    ],
)
logger = logging.getLogger(__name__)


class ComfyUIWebSocketClient(ComfyUIClientBase):
    """
    基于 WebSocket 协议的 ComfyUI 客户端，用于与 ComfyUI 服务器建立双向通信，
    实现工作流提交、任务执行状态实时监控、执行结果（图片/数据）获取等核心能力。

    使用示例：
        with ComfyUIWebSocketClient(
            server_address="127.0.0.1:8188",
            production_mode=True     # 生产环境推荐开启
        ) as client:
            # 执行并监控所有图像生成过程，获取工作流程中的所有image
            images = client.execute_workflow(prompt)
            # 或者只执行不监控
            client.queue_prompt(prompt, prompt_id)

    生产模式（production_mode=True）特性：
        - 关闭所有 debug 级别的日志
        - 不显示节点执行细节、缓存列表、预览图、进度条等
        - 不处理二进制预览消息
        - 只输出关键信息：队列剩余、开始/完成、错误
        - 极大减少日志量，提升性能与可读性

    Attributes:
        server_address (str): ComfyUI 服务器地址，格式为 "host:port"（如 "127.0.0.1:8188"）
        timeout (int): WebSocket 连接超时时间（秒），默认 30 秒
        ws (Optional[websocket.WebSocket]): WebSocket 连接实例，连接成功后非 None
        is_connected (bool): 当前连接状态标识

    - 支持上下文管理器（with 语句）自动管理连接的建立与释放
    - 实时监听服务器推送的任务执行日志、进度、错误信息
    - 解析并返回工作流执行生成的图片二进制数据
    - 处理连接超时、断连重连（基础版）、任务中断等异常场景
    """

    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        timeout: int = 30,
        production_mode: bool = False,
        client_id: Optional[str] = None,
    ):
        """
        初始化WebSocket客户端

        Args:
            server_address: ComfyUI 服务地址
            timeout: HTTP 与 WebSocket 超时时间（秒）
            production_mode: 是否启用生产模式（强烈建议批量任务时开启）
            client_id: 自定义 WebSocket 客户端 ID，默认随机生成 UUID
        """
        super().__init__(server_address, timeout, client_id)
        self.ws: Optional[websocket.WebSocket] = None
        self.production_mode = production_mode
        self.message_policy = (
            MessageHandlingPolicy.PRODUCTION
            if production_mode
            else MessageHandlingPolicy.DEVELOPMENT
        )

    def connect(self):
        """建立WebSocket连接"""
        if self.ws and self.ws.connected:
            return

        ws_url = f"ws://{self.server_address}/ws?clientId={self.client_id}"
        self.logger.info(f"连接到WebSocket服务器: {ws_url}")
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(ws_url, timeout=self.timeout)
        except websocket.WebSocketException as e:
            raise WorkflowConnectionError(f"WebSocket连接失败: {str(e)}") from e
        except Exception as e:
            raise WorkflowConnectionError(f"WebSocket连接建立异常: {str(e)}") from e

    def execute_workflow(
        self,
        prompt: Dict[str, Any],
        wait_for_queue: bool = True,
        check_interval: float = 1.0,
        max_wait: Optional[float] = None,
    ) -> Dict[APINodeID, List[bytes]]:  # 类型化的返回
        """
        执行工作流并处理所有WebSocket消息

        :param prompt: 工作流字典
        :param wait_for_queue: 是否等待队列空闲后再提交任务
        :param check_interval: 队列检查间隔（秒）
        :param max_wait: 最大等待时间（秒）
        :return: 输出图片字典 {node_id: [image_bytes, ...]}
        """
        if wait_for_queue:
            self.wait_for_queue_empty(check_interval, max_wait)

        prompt_id = str(uuid.uuid4())
        ticket = self.queue_prompt(prompt, prompt_id, wait_for_queue=False)

        # 检查错误
        if ticket.node_errors:
            self.logger.error(f"工作流存在节点错误: {ticket.node_errors}")
            raise RuntimeError(f"工作流验证失败: {ticket.node_errors}")

        if ticket.error:
            self.logger.error(f"工作流提交错误: {ticket.error}")
            raise RuntimeError(f"工作流提交失败: {ticket.error}")

        output_images: Dict[str, List[bytes]] = {}

        try:
            while True:
                try:
                    # 设置WebSocket接收超时
                    out = self.ws.recv(timeout=self.timeout)
                except websocket.WebSocketTimeoutException:
                    if not self.production_mode:
                        self.logger.debug("WebSocket接收超时，继续等待...")
                    continue
                except websocket.WebSocketConnectionClosedException:
                    self.logger.warning("WebSocket连接已关闭，尝试重连...")
                    self.connect()
                    continue
                except Exception as e:
                    self.logger.error(f"WebSocket接收错误: {e}", exc_info=False)
                    break

                self._process_message(out, prompt_id, output_images)

                # 检查是否执行完成
                if self._is_execution_complete(out, prompt_id):
                    break

            # 获取最终输出
            history = self.get_history(prompt_id)
            if prompt_id not in history:
                raise ValueError(f"Prompt ID {prompt_id} 不存在于历史记录中")

            entry = history[prompt_id]
            self._process_history_outputs(entry, output_images)

            return output_images

        except Exception as e:
            self.logger.error(f"执行工作流失败: {e}", exc_info=True)
            raise

    def _process_message(
        self, message: Any, prompt_id: str, output_images: Dict[str, List[bytes]]
    ):
        """处理WebSocket消息"""
        # 处理JSON消息
        if isinstance(message, str):
            try:
                # 使用WSMessage解析
                ws_msg = WSMessage.model_validate_json(message)
                self._handle_ws_message(ws_msg, prompt_id)
            except ValidationError as e:
                self.logger.error(f"WebSocket消息解析错误: {e}", exc_info=False)
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析错误: {e}", exc_info=False)

        # 处理二进制消息 (预览图片)
        else:
            self._handle_binary_message(message)

    def _handle_ws_message(self, ws_msg: WSMessage, prompt_id: PromptID):
        """处理WebSocket消息对象"""
        if ws_msg.type == "executing":
            try:
                # 使用WSExecutingData解析数据
                executing_data = WSExecutingData(**ws_msg.data)
                if executing_data.prompt_id == prompt_id:
                    self._handle_executing(executing_data)
            except ValidationError as e:
                self.logger.warning(f"执行数据解析失败: {e}")

        elif ws_msg.type in ["execution_start", "execution_cached"]:
            # 处理其他消息类型
            data = ws_msg.data
            if data.get("prompt_id") == prompt_id:
                if ws_msg.type == "execution_start":
                    self._handle_execution_start(data)
                elif ws_msg.type == "execution_cached":
                    self._handle_execution_cached(data)

    def _handle_json_message(self, message: Dict[str, Any], prompt_id: str):
        """处理JSON格式的WebSocket消息"""
        msg_type_str = message.get("type")

        # 根据消息类型字符串获取对应的枚举值
        try:
            msg_type = JsonMessageType(msg_type_str)
        except ValueError:
            # 未知的消息类型
            if not self.production_mode:
                self.logger.debug(f"未处理的消息类型: {msg_type_str}")
            return

        # 检查当前策略是否需要处理此消息类型
        if msg_type not in self.message_policy.value:
            return

        # 构建消息处理器映射
        handlers: Dict[JsonMessageType, Callable] = {
            JsonMessageType.STATUS: self._handle_status_message,
            JsonMessageType.EXECUTION_START: self._handle_execution_start,
            JsonMessageType.EXECUTION_CACHED: lambda d: self._handle_execution_cached(
                d, prompt_id
            ),
            JsonMessageType.EXECUTING: lambda d: self._handle_executing(d),
            JsonMessageType.EXECUTED: lambda d: self._handle_executed(d, prompt_id),
            JsonMessageType.PROGRESS: self._handle_progress,
            JsonMessageType.PROGRESS_STATE: self._handle_progress_state,
            JsonMessageType.EXECUTION_ERROR: self._handle_execution_error,
            JsonMessageType.EXECUTION_INTERRUPTED: self._handle_execution_interrupted,
            JsonMessageType.EXECUTION_SUCCESS: self._handle_execution_success,
        }

        handler = handlers.get(msg_type)
        if handler:
            handler(message.get("data", {}))

    def _handle_status_message(self, data: Dict[str, Any]):
        """处理状态消息"""
        if "status" in data and "exec_info" in data["status"]:
            remaining = data["status"]["exec_info"].get("queue_remaining", 0)
            self.logger.info(f"队列中剩余任务: {remaining}")

    def _handle_execution_start(self, data: Dict[str, Any]):
        """处理执行开始消息"""
        self.logger.info(f"开始执行 prompt_id: {data.get('prompt_id')}")

    def _handle_execution_cached(self, data: Dict[str, Any], prompt_id: str):
        """处理缓存执行消息"""
        if data.get("prompt_id") == prompt_id:
            cached_nodes = data.get("nodes", [])
            self.logger.info(f"缓存的节点: {cached_nodes}")

    def _handle_executing(self, data: WSExecutingData):
        """处理执行中消息"""
        node = data.node
        if node is None:
            self.logger.info("执行完成!")
        else:
            self.logger.info(f"正在执行节点: {node}")

    def _handle_executed(self, data: Dict[str, Any], prompt_id: str):
        """处理节点执行完成消息"""
        if data.get("prompt_id") == prompt_id:
            node = data.get("node")
            output = data.get("output", {})
            display_node = data.get("display_node")

            log_msg = f"节点 {node} 执行完成"
            if display_node:
                log_msg += f" (显示节点ID: {display_node})"

            self.logger.info(log_msg)
            if not self.production_mode:
                self.logger.debug(f"节点 {node} 输出数据: {output}")

    def _handle_progress(self, data: Dict[str, Any]):
        """处理进度更新消息"""
        node = data.get("node")
        value = data.get("value", 0)
        max_val = data.get("max", 100)
        if not self.production_mode:
            self.logger.info(
                f"进度更新 - 节点 {node}: {value}/{max_val} ({value / max_val * 100:.1f}%)"
            )

    def _handle_progress_state(self, data: Dict[str, Any]):
        """处理进度状态消息"""
        if not self.production_mode:
            nodes = data.get("nodes", {})
            for node_id, node_state in nodes.items():
                self.logger.debug(f"节点 {node_id} 状态: {node_state}")

    def _handle_execution_error(self, data: Dict[str, Any]):
        """处理执行错误消息"""
        prompt_id = data.get("prompt_id")
        node_id = data.get("node_id")
        node_type = data.get("node_type")
        error_msg = data.get("exception_message")

        self.logger.error(
            f"""
            执行错误!
            Prompt ID: {prompt_id}
            节点ID: {node_id}
            节点类型: {node_type}
            错误消息: {error_msg}
        """.strip()
        )
        raise RuntimeError(f"工作流执行错误: {error_msg}")

    def _handle_execution_interrupted(self, data: Dict[str, Any]):
        """处理执行中断消息"""
        self.logger.error(
            f"执行被中断! Prompt ID: {data.get('prompt_id')}, 节点ID: {data.get('node_id')}"
        )
        raise RuntimeError("执行被中断")

    def _handle_execution_success(self, data: Dict[str, Any]):
        """处理执行成功消息"""
        self.logger.info(f"执行成功! Prompt ID: {data.get('prompt_id')}")

    def _handle_binary_message(self, message: bytes):
        """处理二进制消息"""
        if len(message) < 4:
            if not self.production_mode:
                self.logger.warning("二进制消息太短，无法解析")
            return

        event_type_value = struct.unpack(">I", message[:4])[0]

        try:
            # 使用枚举替代硬编码数字
            event_type = BinaryMessageType(event_type_value)

            # 生产环境下只处理关键的二进制消息
            if self.production_mode:
                return

            handlers = {
                BinaryMessageType.PREVIEW_IMAGE: self._handle_preview_image,
                BinaryMessageType.METADATA_PREVIEW_IMAGE: self._handle_metadata_preview_image,
                BinaryMessageType.TEXT_MESSAGE: self._handle_text_message,
            }

            handler = handlers.get(event_type)
            if handler:
                handler(message[4:])
            else:
                self.logger.warning(f"未知的二进制消息类型: {event_type}")

        except ValueError:
            if not self.production_mode:
                self.logger.warning(f"未知的二进制消息类型值: {event_type_value}")

    def _handle_preview_image(self, data: bytes):
        """处理预览图片消息"""
        if len(data) >= 4:
            image_type = struct.unpack(">I", data[:4])[0]
            self.logger.info(f"收到预览图片 (类型: {image_type})")

    def _handle_metadata_preview_image(self, data: bytes):
        """处理带元数据的预览图片消息"""
        if len(data) < 4:
            return

        metadata_len = struct.unpack(">I", data[:4])[0]
        if len(data) < 4 + metadata_len:
            self.logger.warning("元数据不完整")
            return

        try:
            metadata_json = data[4 : 4 + metadata_len].decode("utf-8")
            metadata = json.loads(metadata_json)
            self.logger.info(
                f"收到带元数据的预览图片 - 节点ID: {metadata.get('node_id')}, Prompt ID: {metadata.get('prompt_id')}"
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self.logger.error(f"解析元数据失败: {e}", exc_info=False)

    def _handle_text_message(self, data: bytes):
        """处理文本消息"""
        if len(data) < 4:
            return

        node_id_len = struct.unpack(">I", data[:4])[0]
        if len(data) < 4 + node_id_len:
            self.logger.warning("文本消息不完整")
            return

        try:
            node_id = data[4 : 4 + node_id_len].decode("utf-8")
            text = data[4 + node_id_len :].decode("utf-8")
            self.logger.info(f"节点 {node_id} 文本消息: {text}")
        except UnicodeDecodeError as e:
            self.logger.error(f"解析文本消息失败: {e}", exc_info=False)

    def _is_execution_complete(self, message: Any, prompt_id: str) -> bool:
        """检查执行是否完成"""
        if isinstance(message, str):
            try:
                msg = json.loads(message)
                if msg.get("type") == JsonMessageType.EXECUTING.value:
                    data = msg.get("data", {})
                    if data.get("prompt_id") == prompt_id and data.get("node") is None:
                        return True
            except json.JSONDecodeError:
                pass
        return False

    def _process_history_outputs(
        self,
        history: APIHistoryEntry,  # 类型化的历史条目
        output_images: Dict[APINodeID, List[bytes]],
    ):
        """处理历史记录中的输出图片"""
        outputs = history.get("outputs", {})

        for node_id, node_output in outputs.items():
            if not self.production_mode:
                self.logger.info(f"节点 {node_id} 最终输出:")

            # 处理图片输出
            if "images" in node_output:
                images_output = []
                for image_info in node_output["images"]:
                    try:
                        image_data = self.get_image(
                            image_info["filename"],
                            image_info["subfolder"],
                            image_info["type"],
                        )
                        images_output.append(image_data)
                        if not self.production_mode:
                            self.logger.info(f"  图片: {image_info['filename']}")
                    except Exception as e:
                        self.logger.error(f"  获取图片失败: {e}", exc_info=False)

                if images_output:
                    output_images[node_id] = images_output

            # 打印其他输出（仅在非生产模式下）
            if not self.production_mode:
                for key, value in node_output.items():
                    if key != "images":
                        self.logger.info(f"  {key}: {value}")

        # 打印执行状态
        status = history.get("status", {})
        if not self.production_mode:
            self.logger.info(f"执行状态: {status}")

    def close(self):
        """关闭连接和资源"""
        if self.ws:
            try:
                self.ws.close()
                self.logger.info("WebSocket连接已关闭")
            except Exception as e:
                self.logger.error(f"关闭WebSocket连接失败: {e}", exc_info=False)
            self.ws = None

        # 调用父类的close方法关闭HTTP会话
        super().close()

    def __enter__(self):
        """支持上下文管理器"""
        self.connect()
        return self


# 使用示例
if __name__ == "__main__":
    # 使用上下文管理器自动管理连接，设置production_mode=True启用生产环境模式
    with ComfyUIWebSocketClient(production_mode=True) as client:
        # 工作流定义
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 8,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 512, "height": 512, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "masterpiece best quality girl", "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "bad hands", "clip": ["4", 1]},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]},
            },
        }

        try:
            images = client.execute_workflow(workflow, max_wait=300)  # 最多等待5分钟
            logger.info(f"\n生成了 {len(images)} 个节点的输出")

            # 保存示例图片
            for node_id, image_list in images.items():
                for i, image_data in enumerate(image_list):
                    filename = f"output_{node_id}_{i}.png"
                    with open(filename, "wb") as f:
                        f.write(image_data)
                    logger.info(f"已保存图片: {filename}")

        except Exception as e:
            logger.error(f"执行失败: {e}", exc_info=True)
