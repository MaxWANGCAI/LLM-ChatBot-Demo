#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
知识库数据导入脚本
用于将示例数据导入到 Elasticsearch
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

from app.utils.data_import import import_all_data

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 导入所有数据
    print("开始导入知识库数据...")
    if import_all_data():
        print("所有数据导入成功")
    else:
        print("部分或全部数据导入失败，请检查日志") 