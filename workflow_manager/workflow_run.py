import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..comfyui_client.comfyui_webscoket import ComfyUIWebSocketClient
from .workflow_manager import WorkflowManager

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WorkflowRunner:
    def __init__(
        self,
        config_path: str,
        comfyui_client: ComfyUIWebSocketClient = ComfyUIWebSocketClient(
            server_address="localhost:8188"
        ),
    ):
        self.config_path = Path(config_path)
        self.workflow_manager = WorkflowManager()
        self.client = comfyui_client

        # 回调函数
        self.preprocess_callback: Optional[Callable] = None
        self.postprocess_callback: Optional[Callable] = None
        self.workflow_modify_callback: Optional[Callable[[Dict], Dict]] = None

    def set_preprocess_callback(self, callback: Callable):
        """设置前处理回调函数"""
        self.preprocess_callback = callback

    def set_postprocess_callback(
        self, callback: Callable[[Dict[str, list[bytes]]], Any]
    ):
        """设置后处理回调函数"""
        self.postprocess_callback = callback

    def set_workflow_modify_callback(self, callback: Callable[[Dict], Dict]):
        """设置工作流修改回调函数"""
        self.workflow_modify_callback = callback

    def run(self, random_init: bool = True, remove_previews: bool = True) -> Any:
        """执行工作流的完整流程"""
        try:
            # 1. 前处理
            logger.info("开始前处理...")
            if self.preprocess_callback:
                self.preprocess_callback()

            # 2. 初始化工作流（读取配置，生成随机值）
            logger.info("初始化工作流...")
            workflow_data = self.workflow_manager.get_workflow(
                self.config_path,
                random_init=random_init,
                remove_previews=remove_previews,
            )

            # 3. 检查是否有工作流修改的回调
            if self.workflow_modify_callback:
                logger.info("应用工作流修改回调...")
                workflow_data = self.workflow_modify_callback(workflow_data)

            # 4. 工作流执行
            logger.info("连接到ComfyUI服务器并执行工作流...")
            with self.client:
                output_images = self.client.execute_workflow(workflow_data)

            # 5. 后处理
            logger.info("开始后处理...")
            if self.postprocess_callback:
                return self.postprocess_callback(output_images)
            return output_images

        except Exception as e:
            logger.error(f"工作流执行失败: {str(e)}", exc_info=True)
            raise
