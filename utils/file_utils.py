# workflow_manager/utils.py
import json
from pathlib import Path
from typing import Dict

import yaml


def resolve_path(config_path: Path, relative_path: str) -> Path:
    """解析相对路径为绝对路径"""
    path = Path(relative_path)
    return path if path.is_absolute() else (config_path.parent / path).resolve()


def load_file_content(file_path: Path) -> Dict:
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
