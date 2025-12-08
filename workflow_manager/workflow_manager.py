import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, Union

from constant import SEED_NODE_LIST

# 尝试导入 PyYAML，如果未安装则提示
try:
    import yaml
except ImportError:
    yaml = None

# 1. 配置 Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WorkflowManager:
    def __init__(self):
        self.MAX_SEED = 2**32 - 1  # 最大种子值
        self.seed_config_list = SEED_NODE_LIST if SEED_NODE_LIST else []

        pass

    def _load_file_content(self, file_path: Path) -> Dict:
        """读取 JSON 或 YAML 文件内容"""
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix.lower() in [".yaml", ".yml"]:
            if yaml is None:
                logger.error(
                    "检测到YAML文件，但未安装PyYAML库。请运行 `pip install pyyaml`"
                )
                raise ImportError("PyYAML is required for parsing yaml files.")
            return yaml.safe_load(file_path.read_text(encoding="utf-8"))

        elif file_path.suffix.lower() == ".json":
            return json.loads(file_path.read_text(encoding="utf-8"))

        else:
            logger.error("不支持的文件格式，仅支持 json 或 yaml")
            raise ValueError("Unsupported file format")

    def _resolve_value(self, value_config: Any) -> Any:
        """
        解析配置中的值，处理 random_range 和 random_choice
        如果值不是字典或者没有 type 字段，则直接返回原值
        """
        if not isinstance(value_config, dict) or "type" not in value_config:
            return value_config

        v_type = value_config.get("type")

        if v_type == "random_range":
            min_v = value_config.get("min", 0)
            max_v = value_config.get("max", 1)
            # 判断是浮点数还是整数
            if isinstance(min_v, float) or isinstance(max_v, float):
                val = random.uniform(min_v, max_v)
                # 可选：保留小数点后几位
                return round(val, 4)
            else:
                return random.randint(min_v, max_v)

        elif v_type == "random_choice":
            choices = value_config.get("choices", [])
            if not choices:
                return None
            return random.choice(choices)

        return value_config

    def modify_json_item(
        self, data: Dict, class_type: str, item_name: str, new_value: Any, index: int
    ) -> bool:
        """
        修改ComfyUI工作流JSON中指定class_type项目的值。
        """
        found_count = 0
        # ComfyUI的API格式通常是 {"id": {"class_type": "...", "inputs": {...}}}
        for key, item in data.items():
            if "class_type" in item and item["class_type"] == class_type:
                found_count += 1
                if found_count == index:
                    if "inputs" in item and item_name in item["inputs"]:
                        old_val = item["inputs"][item_name]
                        item["inputs"][item_name] = new_value
                        logger.info(
                            f"修改节点[{class_type}] (第{index}个) 的 '{item_name}': {old_val} -> {new_value}"
                        )
                        return True
                    else:
                        logger.warning(
                            f"在第{index}个[{class_type}]节点中未找到参数 '{item_name}'，跳过修改。"
                        )
                        return False

        logger.warning(f"未找到第{index}个 class_type 为 '{class_type}' 的节点。")
        return False

    def remove_preview_nodes(self, data: dict) -> dict:
        """
        移除所有class_type为"PreviewImage"的节点

        Args:
            data (dict): JSON文件的所读出的数据

        Returns:
            dict: 移除预览节点后的字典数据
        """
        # 收集所有需要移除的预览节点的键
        previews = []
        for number, info in data.items():
            if info.get("class_type") == "PreviewImage":
                previews.append(number)

        # 移除预览节点
        for number in previews:
            data.pop(number)

        # 返回处理后的数据
        return data

    def _randomize_seed_nodes(self, workflow_data: Dict, seed_config_list: list[Dict]):
        """
        遍历工作流，自动随机化指定的种子节点。

        :param workflow_data: 原始工作流数据
        :param seed_config_list: 种子节点配置列表，例如:
               [{"class_type": "KSampler", "item_name": "seed"}, ...]
        """
        if not seed_config_list:
            return

        count = 0
        # 遍历工作流中的每一个节点
        for node_id, node_info in workflow_data.items():
            if "class_type" not in node_info:
                continue

            node_class = node_info["class_type"]

            # 检查当前节点是否在种子配置列表中
            # 使用 next 查找匹配的配置，如果找不到返回 None
            matched_config = next(
                (item for item in seed_config_list if item["class_type"] == node_class),
                None,
            )

            if matched_config:
                param_name = matched_config.get("item_name", "seed")  # 默认为 "seed"

                # 确保该节点有对应的输入参数并且是数值类型
                if (
                    "inputs" in node_info
                    and param_name in node_info["inputs"]
                    and isinstance(
                        node_info["inputs"][param_name], (int, float, complex)
                    )
                ):
                    # 生成随机种子
                    new_seed = random.randint(0, self.MAX_SEED)
                    old_seed = node_info["inputs"][param_name]
                    node_info["inputs"][param_name] = new_seed
                    count += 1
                    logger.info(
                        f"随机化种子节点 [{node_class}] (ID:{node_id}): '{param_name}' {old_seed} -> {new_seed}"
                    )

        if count > 0:
            logger.info(f"共随机化了 {count} 个种子节点。")
        else:
            logger.info("未发现需要随机化的种子节点。")

    def get_workflow(
        self,
        config_file_path: Union[str, Path],
        random_init: bool = True,
        remove_previews: bool = True,
    ) -> Dict:
        """
        核心函数：读取配置，加载原始工作流，根据 random_init 决定是否修改。
        """
        config_path = Path(config_file_path)

        # 1. 读取配置文件 (Config)
        logger.info(f"正在加载配置文件: {config_path}")
        config_data = self._load_file_content(config_path)

        # 检查配置文件结构
        if "workflow_path" not in config_data:
            error_msg = "配置文件中缺少 'workflow_path' 字段，无法找到原始工作流模板。"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 2. 解析原始工作流路径
        # 处理相对路径：假设 workflow_path 是相对于 config 文件的
        raw_wf_path_str = config_data["workflow_path"]
        workflow_path = Path(raw_wf_path_str)

        if not workflow_path.is_absolute():
            # 如果是相对路径，则将其解析为相对于 config_file 所在的目录
            workflow_path = config_path.parent / workflow_path

        # 3. 读取原始工作流 (Template)
        logger.info(f"正在加载原始工作流模板: {workflow_path}")
        workflow_data = self._load_file_content(workflow_path)

        # 4. 可选：移除预览节点
        if remove_previews:
            logger.info("正在移除预览节点...")
            workflow_data = self.remove_preview_nodes(workflow_data)

        # 5. 根据 random_init 决定是否修改
        seed_nodes_config = self.seed_config_list if self.seed_config_list else []
        if seed_nodes_config:
            self._randomize_seed_nodes(workflow_data, seed_nodes_config)

        if not random_init:
            logger.info("random_init=False，直接返回原始工作流。")
            return workflow_data

        logger.info("random_init=True，开始根据配置修改工作流参数...")
        nodes_config = config_data.get("nodes", [])

        for node_cfg in nodes_config:
            class_type = node_cfg.get("class_type")
            param_name = node_cfg.get("item_name")
            raw_value = node_cfg.get("value")
            node_index = node_cfg.get("node_index", 1)  # 默认为找到的第一个

            # 解析可能存在的随机值配置
            final_value = self._resolve_value(raw_value)

            # 执行修改
            success = self.modify_json_item(
                data=workflow_data,
                class_type=class_type,
                item_name=param_name,
                new_value=final_value,
                index=node_index,
            )

            if not success:
                logger.warning(f"配置项修改失败: {node_cfg}")

        logger.info("工作流修改完成。")
        return workflow_data


# ================= 使用示例 =================

if __name__ == "__main__":
    # 为了演示，我们需要先创建临时的配置文件和工作流文件
    # 在实际使用中，这些文件是已经存在的

    # 1. 创建模拟的原始工作流 (workflow_api.json)
    template_workflow = {
        "10": {"class_type": "Class1", "inputs": {"param1": 0}},
        "11": {"class_type": "Class2", "inputs": {"param2": 50.0}},
        "12": {"class_type": "Class3", "inputs": {"param3": "default"}},
        "14": {"class_type": "KSampler", "inputs": {"seed": 12312321}},
    }
    Path("workflow_template.json").write_text(
        json.dumps(template_workflow, indent=2, ensure_ascii=False)
    )

    # 2. 创建包含 workflow_path 的新配置文件 (config.json)
    # 注意：这里增加了 "workflow_path" 字段
    config_content = {
        "workflow_path": "./workflow_template.json",
        "nodes": [
            {
                "class_type": "Class1",
                "item_name": "param1",
                "value": 42,
                "node_index": 1,
            },
            {
                "class_type": "Class2",
                "item_name": "param2",
                "value": {"type": "random_range", "min": 0.5, "max": 10.5},
                "node_index": 1,
            },
            {
                "class_type": "Class3",
                "item_name": "param3",
                "value": {
                    "type": "random_choice",
                    "choices": ["apple", "banana", "orange"],
                },
                "node_index": 1,
            },
        ],
    }
    Path("my_config.json").write_text(json.dumps(config_content, indent=2))

    # 3. 调用函数
    manager = WorkflowManager()

    print("\n--- 测试 1: random_init = True ---")
    new_workflow = manager.get_workflow("my_config.json", random_init=True)
    print("生成的 workflow 片段:", json.dumps(new_workflow, indent=2))

    print("\n--- 测试 2: random_init = False ---")
    original_workflow = manager.get_workflow("my_config.json", random_init=False)
    # 应该保持原样
