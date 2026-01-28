import logging
import time
import uuid
from typing import Any

import requests

from config.comfy_schema import (
    APIHistory,
    APIQueueInfo,
    APIWorkflow,
    APIWorkflowTicket,
    PromptID,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ComfyUIClientBase:
    """
    ComfyUI客户端基础类，提供HTTP API接口和基础功能

    特性：
    - 支持HTTP API与ComfyUI服务器通信
    - 提供工作流提交、队列状态查询、结果获取等基础功能
    - 支持连接池和会话复用
    - 支持上下文管理器

    使用示例：
        client = ComfyUIClientBase(server_address="127.0.0.1:8188")
        prompt_id = client.queue_prompt(workflow)
    """

    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        timeout: int = 30,
        client_id: str | None = None,
    ):
        """
        初始化客户端基础类

        Args:
            server_address: ComfyUI 服务地址，例如 "127.0.0.1:8188" 或 "mydomain.com:8188"
            timeout: HTTP 超时时间（秒）
            client_id: 自定义客户端 ID，默认随机生成 UUID
        """
        self.client_id = str(uuid.uuid4()) if client_id is None else client_id
        self.server_address = server_address
        self.timeout = timeout
        # 创建 requests 会话，启用连接池
        self.session = requests.Session()
        self.base_url = f"http://{self.server_address}"
        self.logger = logger

    def get_queue_info(self) -> APIQueueInfo:
        """获取队列状态"""
        try:
            response = self.session.get(f"{self.base_url}/queue", timeout=self.timeout)
            response.raise_for_status()
            return APIQueueInfo(**response.json())  # 使用Pydantic验证
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"获取队列状态失败: {e}") from e

    def wait_for_queue_empty(
        self,
        check_interval: float = 1.0,
        max_wait: float | None = None,
        min_queue_num: int = 3,
    ):
        """
        智能等待队列空闲

        当队列中「运行中 + 等待中」任务总数 < min_queue_num 时即视为可执行。

        Args:
            check_interval: 轮询间隔（秒）
            max_wait: 最大等待时间（秒），超时抛出 TimeoutError
            min_queue_num: 执行队列加上等待队列长度小于此数量时认为空闲
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

                self.logger.debug(
                    f"队列状态 - 运行中: {running_count}, 等待中: {pending_count}, 总计: {total_count}"
                )

                time.sleep(check_interval)

            except Exception as e:
                self.logger.error(f"获取队列状态失败: {e}", exc_info=False)
                time.sleep(check_interval)

    def queue_prompt(
        self,
        prompt: APIWorkflow,  # 使用类型化的workflow
        prompt_id: PromptID | None = None,
        wait_for_queue: bool = False,
        check_interval: float = 1.0,
        max_wait: float | None = None,
        min_queue_num: int = 3,
    ) -> APIWorkflowTicket:  # 返回类型化的响应
        """
        提交工作流到执行队列

        Args:
            prompt: 工作流字典
            prompt_id: 任务ID，默认随机生成
            wait_for_queue: 是否等待队列空闲后再提交任务
            check_interval: 队列检查间隔（秒）
            max_wait: 最大等待时间（秒）
            min_queue_num: 执行队列加上等待队列长度小于此数量时认为空闲

        Returns:
            任务ID (prompt_id)
        """
        if prompt_id is None:
            prompt_id = str(uuid.uuid4())

        if wait_for_queue:
            self.wait_for_queue_empty(check_interval, max_wait, min_queue_num)

        payload = {
            "prompt": prompt.model_dump(by_alias=True),
            "client_id": self.client_id,
            "prompt_id": prompt_id,
        }

        try:
            self.logger.info(f"提交prompt到队列: {prompt_id}")
            response = self.session.post(
                f"{self.base_url}/prompt",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return APIWorkflowTicket(**response.json())  # 验证响应
            # self.logger.info(f"工作流已提交，任务ID: {prompt_id}")
            # return prompt_id

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"提交prompt失败: {e}") from e

    def get_history(self, prompt_id: PromptID) -> APIHistory:
        """获取执行历史"""
        try:
            response = self.session.get(
                f"{self.base_url}/history/{prompt_id}", timeout=self.timeout
            )
            response.raise_for_status()
            return APIHistory(**response.json())
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"获取历史记录失败: {e}") from e

    def get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        """下载生成的图片"""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}

        try:
            self.logger.debug(f"下载图片: {filename}")
            response = self.session.get(
                f"{self.base_url}/view",
                params=params,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"获取图片失败: {e}") from e

    def get_prompt_status(self) -> dict[str, Any]:
        """获取提示状态"""
        try:
            response = self.session.get(f"{self.base_url}/prompt", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to get prompt status: {e}")

    def test_connection(self) -> bool:
        """测试与ComfyUI的连接是否成功"""
        try:
            self.get_queue_info()
            return True
        except ConnectionError:
            return False

    def get_system_info(self) -> dict[str, Any]:
        """获取系统信息"""
        try:
            prompt_status = self.get_prompt_status()
            queue_status = self.get_queue_info()

            return {
                "prompt_status": prompt_status,
                "queue_status": queue_status,
                "connection_healthy": True,
            }
        except ConnectionError as e:
            return {"connection_healthy": False, "error": str(e)}

    def close(self):
        """关闭资源"""
        self.session.close()
        self.logger.info("HTTP会话已关闭")

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器"""
        self.close()


class ComfyUISimpleClient(ComfyUIClientBase):
    """
    简易版ComfyUI客户端，仅负责发送工作流请求，不处理返回信息和监控执行状态
    适用于只需要提交任务而无需等待结果的场景

    特性：
    - 继承基础类的所有HTTP功能
    - 简化接口，专注于任务提交
    - 轻量级，无WebSocket依赖

    使用示例：
        client = ComfyUISimpleClient(server_address="127.0.0.1:8188")
        prompt_id = client.queue_prompt(workflow, wait_queue=True)
    """

    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        timeout: int = 30,
        client_id: str | None = None,
    ):
        """
        初始化简易客户端

        Args:
            server_address: ComfyUI 服务地址
            timeout: HTTP 超时时间（秒）
            client_id: 自定义客户端 ID，默认随机生成 UUID
        """
        super().__init__(server_address, timeout, client_id)
        # 简化日志配置
        self.logger.setLevel(logging.INFO)

    def queue_prompt(
        self,
        prompt: dict[str, Any],
        prompt_id: str | None = None,
        wait_for_queue: bool = False,
        check_interval: float = 1.0,
        max_wait: float | None = None,
        min_queue_num: int = 3,
    ) -> str:
        """
        提交工作流到ComfyUI队列（简化版本）

        Args:
            prompt: 工作流字典数据
            prompt_id: 任务ID，默认随机生成
            wait_for_queue: 是否等待队列空闲后再提交任务
            check_interval: 队列检查间隔（秒）
            max_wait: 最大等待时间（秒）
            min_queue_num: 执行队列加上等待队列长度小于此数量时认为空闲

        Returns:
            生成的任务ID (prompt_id)
        """
        # 调用父类方法，但简化日志输出
        try:
            return super().queue_prompt(
                prompt,
                prompt_id,
                wait_for_queue,
                check_interval,
                max_wait,
                min_queue_num,
            )
        except Exception as e:
            self.logger.error(f"工作流提交失败: {str(e)}")
            raise
