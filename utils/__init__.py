"""工具函数模块"""

from .file_utils import load_file_content, resolve_path
from .math_utils import *
from .xml_utils import *

__all__ = [
    "resolve_path",
    "load_file_content",
]

# 动态添加 math_utils 和 xml_utils 的 __all__ 到当前模块的 __all__
from . import math_utils
from . import xml_utils

__all__.extend(math_utils.__all__)
__all__.extend(xml_utils.__all__)
