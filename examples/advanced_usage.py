import os
from pathlib import Path
from typing import Any

from comfyui_workflow_exec import ComfyUIWebSocketClient, execute_workflow_task
from comfyui_workflow_exec.utils.logger import setup_logger

logger = setup_logger(__name__)

# --- 自定义回调函数 ---

def my_preprocess_callback():
    """
    前处理回调：在工作流执行前调用
    可以用于：资源检查、清理临时文件、记录开始时间等
    """
    logger.info(">>> [回调] 执行前处理：正在检查环境资源...")
    # 模拟一些检查
    # if not check_gpu_memory(): raise Exception("显存不足")
    pass

def my_workflow_modify_callback(workflow_data: dict) -> dict:
    """
    工作流修改回调：在加载配置后、发送给ComfyUI前调用
    可以用于：根据运行时状态动态修改节点参数
    """
    logger.info(">>> [回调] 执行动态修改：正在调整采样步数...")
    
    # 示例：遍历所有 KSampler 节点并强制将 steps 设置为 25
    for node_id, node_info in workflow_data.items():
        if node_info.get("class_type") == "KSampler":
            if "inputs" in node_info:
                old_steps = node_info["inputs"].get("steps")
                node_info["inputs"]["steps"] = 25
                logger.info(f"    节点 {node_id} (KSampler): steps {old_steps} -> 25")
    
    return workflow_data

def my_postprocess_callback(output_images: dict[str, list[bytes]]) -> Any:
    """
    后处理回调：在工作流执行完成并获取结果后调用
    可以用于：保存图片、上传云存储、后续图像处理等
    """
    logger.info(">>> [回调] 执行后处理：正在保存结果...")
    
    output_dir = Path("output_images_advanced")
    output_dir.mkdir(exist_ok=True)
    
    saved_count = 0
    for node_id, images in output_images.items():
        for i, image_data in enumerate(images):
            filename = output_dir / f"advanced_result_node{node_id}_{i}.png"
            filename.write_bytes(image_data)
            logger.info(f"    已保存: {filename}")
            saved_count += 1
            
    return {"saved_count": saved_count, "output_dir": str(output_dir)}

# --- 主逻辑 ---

def main():
    # 示例配置路径
    current_dir = Path(__file__).parent
    config_path = current_dir / "config" / "my_config.json"
    
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return

    server_address = os.getenv("COMFYUI_BACKED_URL", "http://localhost:8188")
    
    logger.info("=== 开始高级示例 ===")

    try:
        with ComfyUIWebSocketClient(server_address=server_address, production_mode=False) as client:
            
            # 执行任务，传入所有回调函数
            results = execute_workflow_task(
                config_file=str(config_path),
                comfyui_client=client,
                random_init=True,
                
                # 注入回调
                preprocess_callback=my_preprocess_callback,
                workflow_modify_callback=my_workflow_modify_callback,
                postprocess_callback=my_postprocess_callback
            )
            
            if results:
                logger.info(f"高级任务流程结束，后处理返回值: {results}")
            else:
                logger.warning("任务未返回结果或执行失败")

    except Exception as e:
        logger.error(f"发生未捕获异常: {e}")

if __name__ == "__main__":
    main()
