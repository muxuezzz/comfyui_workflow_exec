import json
import logging
import random
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml
from constant import SEED_NODE_LIST
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ValueType(str, Enum):
    """配置文件 value.type 允许的类型（受控、可无限扩展）"""

    RANDOM_RANGE = "random_range"
    RANDOM_CHOICE = "random_choice"
    # 未来扩展只需在这里添加，例如：
    # RANDOM_INT = "random_int"
    # WEIGHTED_CHOICE = "weighted_choice"
    # NORMAL_DISTRIBUTION = "normal_distribution"


class WorkflowNodeConfig(BaseModel):
    """单个节点的修改配置"""

    class_type: str = Field(description="节点类型（字符串，无限制）")
    parameter_name: str = Field(description="要修改的参数名", alias="item_name")
    value: Any = Field(
        description="""
        支持格式：
        - 直接值：42、3.14、"hello"、true
        - 随机配置（必须包含 type 字段，且 type 必须在 ValueType 枚举中）：
          {
            "type": "random_range",
            "min": 0.0,
            "max": 100.0
          }
          {
            "type": "random_choice",
            "choices": ["a", "b", "c"]
          }
    """
    )
    node_index: int = Field(default=1, ge=1, description="第几个同类型节点（从1开始）")

    @field_validator("value")
    @classmethod
    def validate_value_structure(cls, v: Any) -> Any:
        if isinstance(v, dict) and "type" in v:
            try:
                value_type = ValueType(v["type"])
            except ValueError as e:
                raise ValueError(
                    f"value.type 必须是以下之一: {', '.join(t.value for t in ValueType)}"
                ) from e

            # 可选：对每种 type 做更细致的结构校验（推荐保留，防止配置错误）
            if value_type == ValueType.RANDOM_RANGE:
                if "min" not in v or "max" not in v:
                    raise ValueError("random_range 必须包含 min 和 max 字段")
            elif value_type == ValueType.RANDOM_CHOICE:
                if not isinstance(v.get("choices"), list) or len(v["choices"]) == 0:
                    raise ValueError("random_choice 必须包含非空 choices 列表")

        return v


class RootConfig(BaseModel):
    """配置文件完整结构校验"""

    workflow_path: str = Field(description="工作流模板路径")
    nodes: List[WorkflowNodeConfig] = Field(default=[], description="节点修改配置列表")


class WorkflowManager:
    def __init__(self):
        self.MAX_SEED = 2**32 - 1
        self.seed_config_list = SEED_NODE_LIST if SEED_NODE_LIST else []

    def _load_file_content(self, file_path: Path) -> Dict:
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        suffix = file_path.suffix.lower()
        content = file_path.read_text(encoding="utf-8")

        if suffix in [".yaml", ".yml"]:
            if yaml is None:
                raise ImportError("请安装 PyYAML: pip install pyyaml")
            return yaml.safe_load(content)
        elif suffix == ".json":
            return json.loads(content)
        else:
            raise ValueError("仅支持 .json / .yaml / .yml")

    def _handle_random_range(self, config: dict) -> Any:
        min_v = config.get("min", 0)
        max_v = config.get("max", 1)
        if isinstance(min_v, float) or isinstance(max_v, float):
            return round(random.uniform(min_v, max_v), 6)
        else:
            return random.randint(min_v, max_v)

    def _handle_random_choice(self, config: dict) -> Any:
        choices = config.get("choices", [])
        return random.choice(choices) if choices else None

    # 可无限升级的核心解析器（推荐扩展方式）
    _VALUE_HANDLERS = {
        ValueType.RANDOM_RANGE: _handle_random_range,
        ValueType.RANDOM_CHOICE: _handle_random_choice,
        # 未来扩展示例：
        # ValueType.NORMAL_DISTRIBUTION: _handle_normal_distribution,
    }

    def _resolve_value(self, raw_value: Any) -> Any:
        """极简、可无限迭代升级的值解析器"""
        # 不是带 type 的配置 → 直接返回（支持 42、"text"、true 等）
        if not isinstance(raw_value, dict) or "type" not in raw_value:
            return raw_value

        try:
            v_type = ValueType(raw_value["type"])
        except ValueError:
            logger.warning(f"未知的 value.type: {raw_value['type']}，原样返回")
            return raw_value

        handler = self._VALUE_HANDLERS.get(v_type)
        if handler:
            return handler(self, raw_value)  # 传入 self 以便访问实例方法
        else:
            logger.warning(f"暂未实现对 {v_type.value} 的处理，原样返回配置")
            return raw_value

    def modify_json_item(
        self,
        data: Dict,
        class_type: str,
        parameter_name: str,
        new_value: Any,
        index: int,
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
                    if "inputs" in item and parameter_name in item["inputs"]:
                        old_val = item["inputs"][parameter_name]
                        item["inputs"][parameter_name] = new_value
                        logger.info(
                            f"修改 [{class_type}] 第{index}个 '{parameter_name}': {old_val} → {new_value}"
                        )
                        return True
                    else:
                        logger.warning(f"节点中未找到参数 '{parameter_name}'")
                        return False
        logger.warning(f"未找到第{index}个 {class_type} 节点")
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
        previews = [k for k, v in data.items() if v.get("class_type") == "PreviewImage"]
        for k in previews:
            data.pop(k)
        return data

    def _randomize_seed_nodes(self, workflow_data: Dict):
        if not self.seed_config_list:
            return

        count = 0
        for node_id, node_info in workflow_data.items():
            node_class = node_info.get("class_type")
            if not node_class:
                continue

            matched = next(
                (c for c in self.seed_config_list if c["class_type"] == node_class),
                None,
            )
            if not matched:
                continue

            param_name = matched.get("parameter_name", "seed")
            if param_name not in node_info.get("inputs", {}):
                continue

            current = node_info["inputs"][param_name]
            if not isinstance(current, (int, float)):
                continue

            new_seed = random.randint(0, self.MAX_SEED)
            node_info["inputs"][param_name] = new_seed
            count += 1
            logger.info(
                f"自动随机化种子 [{node_class}] (ID:{node_id}) {param_name}: {current} → {new_seed}"
            )

        if count:
            logger.info(f"自动随机化完成，共 {count} 个种子节点")

    def get_workflow(
        self,
        config_file_path: Union[str, Path],
        random_init: bool = True,
        remove_previews: bool = True,
    ) -> Dict:
        config_path = Path(config_file_path)

        logger.info(f"加载配置文件: {config_path}")
        config_raw = self._load_file_content(config_path)

        try:
            config = RootConfig.model_validate(config_raw)
        except Exception as e:
            logger.error(f"配置文件校验失败: {e}")
            raise

        workflow_path = Path(config.workflow_path)
        if not workflow_path.is_absolute():
            workflow_path = (config_path.parent / workflow_path).resolve()

        logger.info(f"加载工作流模板: {workflow_path}")
        workflow_data = self._load_file_content(workflow_path)

        if remove_previews:
            workflow_data = self.remove_preview_nodes(workflow_data)

        self._randomize_seed_nodes(workflow_data)

        if not random_init or not config.nodes:
            return workflow_data

        logger.info(f"应用 {len(config.nodes)} 条手动配置...")
        for node_cfg in config.nodes:
            final_value = self._resolve_value(node_cfg.value)
            self.modify_json_item(
                data=workflow_data,
                class_type=node_cfg.class_type,
                parameter_name=node_cfg.parameter_name,
                new_value=final_value,
                index=node_cfg.node_index,
            )

        logger.info("工作流处理完成")
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
    config_Path = Path(__file__).parent.parent / "config"

    Path(config_Path / "workflow_template.json").write_text(
        json.dumps(template_workflow, indent=2, ensure_ascii=False)
    )

    # 2. 创建包含 workflow_path 的新配置文件 (config.json)
    # 注意：这里增加了 "workflow_path" 字段
    config_content = {
        "workflow_path": str(Path(config_Path / "workflow_template.json")),
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
    Path(config_Path / "my_config.json").write_text(
        json.dumps(config_content, indent=2)
    )

    my_config_path = config_Path / "my_config.json"

    # 3. 调用函数
    manager = WorkflowManager()

    print("\n--- 测试 1: random_init = True ---")
    new_workflow = manager.get_workflow(my_config_path, random_init=True)
    print("生成的 workflow 片段:", json.dumps(new_workflow, indent=2))

    print("\n--- 测试 2: random_init = False ---")
    original_workflow = manager.get_workflow(my_config_path, random_init=False)
    # 应该保持原样
