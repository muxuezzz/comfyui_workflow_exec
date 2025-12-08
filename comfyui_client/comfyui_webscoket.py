import json
import logging
import struct
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import requests
import websocket

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


class ComfyUIWebSocketClient:
    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        timeout: int = 30,
        production_mode: bool = False,
    ):
        self.ws: Optional[websocket.WebSocket] = None
        self.client_id = str(uuid.uuid4())
        self.server_address = server_address
        self.timeout = timeout
        self.production_mode = production_mode  # 生产环境模式开关
        self.message_policy = (
            MessageHandlingPolicy.PRODUCTION
            if production_mode
            else MessageHandlingPolicy.DEVELOPMENT
        )
        # 创建 requests 会话，启用连接池
        self.session = requests.Session()
        self.base_url = f"http://{self.server_address}"
        self.logger = logger  # 实例化logger

    def connect(self):
        """连接到WebSocket服务器"""
        if self.ws and self.ws.connected:
            return

        ws_url = f"ws://{self.server_address}/ws?clientId={self.client_id}"
        self.logger.info(f"连接到WebSocket服务器: {ws_url}")
        self.ws = websocket.WebSocket()
        self.ws.connect(ws_url, timeout=self.timeout)

    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列状态"""
        try:
            response = self.session.get(f"{self.base_url}/queue", timeout=self.timeout)
            response.raise_for_status()  # 抛出HTTP错误
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"获取队列状态失败: {e}") from e

    def wait_for_queue_empty(
        self,
        check_interval: float = 1.0,
        max_wait: Optional[float] = None,
        min_queue_num: int = 3,  # 新增参数：当队列总任务数 < 此值时即视为空闲（默认1，和原来完全等价）
    ):
        """
        等待队列空闲（运行中 + 等待中任务数 < min_queue_num 时视为空闲）

        :param check_interval: 检查间隔时间（秒）
        :param max_wait: 最大等待时间（秒），None表示无限等待
        :param min_queue_num: 总任务数小于此值时视为空闲（默认1，保持原行为）
        """
        self.logger.info(f"正在等待队列任务数 < {min_queue_num} ...")
        start_time = time.time()

        while True:
            try:
                queue_status = self.get_queue_info()

                # 安全获取列表，防止None
                running = queue_status.get("queue_running") or []
                pending = queue_status.get("queue_pending") or []

                running_count = len(running)
                pending_count = len(pending)
                total_count = running_count + pending_count

                if total_count < min_queue_num:
                    self.logger.info(
                        f"队列已空闲（总任务 {total_count} < {min_queue_num}，"
                        f"运行中: {running_count}，等待中: {pending_count}），准备执行..."
                    )
                    break

                # 检查是否超时
                if max_wait and (time.time() - start_time) > max_wait:
                    raise TimeoutError(f"等待队列空闲超时（{max_wait}秒）")

                if not self.production_mode:
                    # 非生产环境才输出详细状态
                    self.logger.debug(
                        f"队列状态 - 运行中: {running_count}, 等待中: {pending_count}, 总计: {total_count}"
                    )

                time.sleep(check_interval)

            except Exception as e:
                self.logger.error(f"获取队列状态失败: {e}", exc_info=False)
                time.sleep(check_interval)

    def queue_prompt(
        self, prompt: Dict[str, Any], prompt_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """提交工作流到执行队列"""
        if prompt_id is None:
            prompt_id = str(uuid.uuid4())

        payload = {
            "prompt": prompt,
            "client_id": self.client_id,
            "prompt_id": prompt_id,
        }

        try:
            self.logger.info(f"提交prompt到队列: {prompt_id}")
            response = self.session.post(
                f"{self.base_url}/prompt",
                json=payload,  # 自动序列化并设置Content-Type
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"提交prompt失败: {e}") from e

    def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """获取执行历史"""
        try:
            response = self.session.get(
                f"{self.base_url}/history/{prompt_id}", timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"获取历史记录失败: {e}") from e

    def get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        """下载生成的图片"""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}

        try:
            if not self.production_mode:  # 生产环境不输出下载日志
                self.logger.debug(f"下载图片: {filename}")
            response = self.session.get(
                f"{self.base_url}/view",
                params=params,  # 自动编码URL参数
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"获取图片失败: {e}") from e

    def execute_workflow(
        self,
        prompt: Dict[str, Any],
        wait_for_queue: bool = True,
        check_interval: float = 1.0,
        max_wait: Optional[float] = None,
    ) -> Dict[str, List[bytes]]:
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
        self.queue_prompt(prompt, prompt_id)

        output_images: Dict[str, List[bytes]] = {}

        try:
            while True:
                try:
                    # 设置WebSocket接收超时
                    out = self.ws.recv(timeout=self.timeout)
                except websocket.WebSocketTimeoutException:
                    if not self.production_mode:  # 生产环境不输出超时日志
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

            self._process_history_outputs(history[prompt_id], output_images)

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
                msg = json.loads(message)
                self._handle_json_message(msg, prompt_id)
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析错误: {e}", exc_info=False)

        # 处理二进制消息 (预览图片)
        else:
            self._handle_binary_message(message)

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
            JsonMessageType.EXECUTING: lambda d: self._handle_executing(d, prompt_id),
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

    def _handle_executing(self, data: Dict[str, Any], prompt_id: str):
        """处理执行中消息"""
        if data.get("prompt_id") == prompt_id:
            node = data.get("node")
            if node is None:
                self.logger.info("执行完成!")
            else:
                display_node = data.get("display_node")
                if display_node:
                    self.logger.info(
                        f"正在执行节点: {node} (显示节点ID: {display_node})"
                    )
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
            self.logger.debug(f"节点 {node} 输出数据: {output}")

    def _handle_progress(self, data: Dict[str, Any]):
        """处理进度更新消息"""
        node = data.get("node")
        value = data.get("value", 0)
        max_val = data.get("max", 100)
        self.logger.info(
            f"进度更新 - 节点 {node}: {value}/{max_val} ({value / max_val * 100:.1f}%)"
        )

    def _handle_progress_state(self, data: Dict[str, Any]):
        """处理进度状态消息"""
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
        raise RuntimeError(f"执行错误: {error_msg}")

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
            if not self.production_mode:  # 生产环境不输出短消息警告
                self.logger.warning("二进制消息太短，无法解析")
            return

        event_type_value = struct.unpack(">I", message[:4])[0]

        try:
            # 使用枚举替代硬编码数字
            event_type = BinaryMessageType(event_type_value)

            # 生产环境下只处理关键的二进制消息（这里根据需要调整）
            if self.production_mode:
                # 生产环境可以选择不处理任何二进制消息，或者只处理特定类型
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
            if not self.production_mode:  # 生产环境忽略未知类型值
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
        self, history: Dict[str, Any], output_images: Dict[str, List[bytes]]
    ):
        """处理历史记录中的输出图片"""
        outputs = history.get("outputs", {})

        for node_id, node_output in outputs.items():
            if not self.production_mode:  # 生产环境不输出详细输出信息
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
                        if not self.production_mode:  # 生产环境不输出图片信息
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

        # 关闭requests会话
        self.session.close()
        self.logger.info("HTTP会话已关闭")

    def __enter__(self):
        """支持上下文管理器"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器"""
        self.close()


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
