import logging
import time
import uuid
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ComfyUISimpleClient:
    """
    简易版ComfyUI客户端，仅负责发送工作流请求，不处理返回信息和监控执行状态
    适用于只需要提交任务而无需等待结果的场景
    """

    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        timeout: int = 30,
        client_id: str | None = None,
    ):
        self.server_address = server_address
        self.timeout = timeout
        self.client_id = client_id or str(uuid.uuid4())
        self.base_url = f"http://{self.server_address}"
        self.session = requests.Session()  # 复用连接池提升效率

    def queue_prompt(self, prompt: dict, wait_queue=True) -> str:
        """
        提交工作流到ComfyUI队列

        Args:
            prompt: 工作流字典数据

        Returns:
            生成的任务ID (prompt_id)
        """
        prompt_id = str(uuid.uuid4())
        payload = {
            "prompt": prompt,
            "client_id": self.client_id,
            "prompt_id": prompt_id,
        }

        if wait_queue:
            self.wait_for_queue_empty()

        try:
            response = self.session.post(f"{self.base_url}/prompt", json=payload, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"工作流已提交，任务ID: {prompt_id}")
            return prompt_id
        except requests.exceptions.RequestException as e:
            logger.error(f"提交工作流失败: {str(e)}")
            raise

    def wait_for_queue_empty(
        self,
        check_interval: float = 1.0,
        max_wait: float | None = None,
        min_queue_num: int = 3,
    ):
        """等待队列空闲（可选）"""
        start_time = time.time()
        logger.info(f"等待队列任务数 < {min_queue_num}...")

        while True:
            try:
                response = self.session.get(f"{self.base_url}/queue", timeout=self.timeout)
                queue_info = response.json()

                running = len(queue_info.get("queue_running", []))
                pending = len(queue_info.get("queue_pending", []))
                total = running + pending

                if total < min_queue_num:
                    logger.info(f"队列已空闲（总任务数: {total}）")
                    break

                if max_wait and (time.time() - start_time) > max_wait:
                    raise TimeoutError(f"等待队列超时（{max_wait}秒）")

                time.sleep(check_interval)

            except Exception as e:
                logger.warning(f"获取队列状态失败: {e}，将重试...")
                time.sleep(check_interval)

    def get_prompt_status(self) -> dict[str, Any]:
        """
        获取提示状态

        Returns:
            状态信息字典
        """
        try:
            response = requests.get(f"{self.base_url}/prompt", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to get prompt status: {e}")

    def get_queue_status(self) -> dict[str, Any]:
        """
        获取队列状态

        Returns:
            队列状态信息字典
        """
        try:
            response = requests.get(f"{self.base_url}/queue", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to get queue status: {e}")

    def test_connection(self) -> bool:
        """
        测试与ComfyUI的连接

        Returns:
            连接是否成功
        """
        try:
            self.get_queue_status()
            return True
        except ConnectionError:
            return False

    def get_system_info(self) -> dict[str, Any]:
        """
        获取系统信息

        Returns:
            系统信息字典
        """
        try:
            prompt_status = self.get_prompt_status()
            queue_status = self.get_queue_status()

            return {
                "prompt_status": prompt_status,
                "queue_status": queue_status,
                "connection_healthy": True,
            }
        except ConnectionError as e:
            return {"connection_healthy": False, "error": str(e)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        logger.info("连接已关闭")
