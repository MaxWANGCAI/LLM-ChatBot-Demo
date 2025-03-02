#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试运行脚本
用于运行项目的测试用例
"""

import sys
import os
import argparse
import logging
import importlib
import traceback
from pathlib import Path

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def discover_test_modules():
    """发现所有测试模块"""
    test_dir = root_dir / "app" / "tests"
    test_modules = []
    
    if not test_dir.exists():
        logger.warning(f"测试目录不存在: {test_dir}")
        return test_modules
    
    for file_path in test_dir.glob("test_*.py"):
        module_name = f"app.tests.{file_path.stem}"
        test_modules.append(module_name)
    
    return test_modules

def run_test_module(module_name, test_case=None, report_path=None):
    """运行指定的测试模块"""
    try:
        logger.info(f"正在加载测试模块: {module_name}")
        module = importlib.import_module(module_name)
        
        # 查找测试类
        test_classes = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr_name.startswith("Test"):
                test_classes.append(attr)
        
        if not test_classes:
            logger.warning(f"在模块 {module_name} 中未找到测试类")
            return False
        
        success = True
        for test_class in test_classes:
            logger.info(f"正在初始化测试类: {test_class.__name__}")
            test_instance = test_class()
            
            # 如果指定了测试用例，只运行该测试用例
            if test_case:
                if hasattr(test_instance, test_case):
                    logger.info(f"正在运行测试用例: {test_case}")
                    test_method = getattr(test_instance, test_case)
                    if callable(test_method):
                        if report_path:
                            test_instance.report_path = report_path
                        test_method()
                    else:
                        logger.warning(f"{test_case} 不是一个可调用的方法")
                        success = False
                else:
                    logger.warning(f"测试类 {test_class.__name__} 中未找到测试用例 {test_case}")
                    success = False
            else:
                # 运行所有以 test_ 开头的方法
                test_methods = [method for method in dir(test_instance) if method.startswith("test_") and callable(getattr(test_instance, method))]
                
                if not test_methods:
                    logger.warning(f"在测试类 {test_class.__name__} 中未找到测试方法")
                    continue
                
                logger.info(f"找到 {len(test_methods)} 个测试方法")
                
                # 设置报告路径
                if report_path:
                    test_instance.report_path = report_path
                
                # 如果有 run_all_tests 方法，优先使用它
                if hasattr(test_instance, "run_all_tests") and callable(getattr(test_instance, "run_all_tests")):
                    logger.info("使用 run_all_tests 方法运行所有测试")
                    getattr(test_instance, "run_all_tests")()
                else:
                    # 否则，逐个运行测试方法
                    for method_name in test_methods:
                        logger.info(f"正在运行测试方法: {method_name}")
                        try:
                            getattr(test_instance, method_name)()
                        except Exception as e:
                            logger.error(f"测试方法 {method_name} 执行失败: {str(e)}")
                            traceback.print_exc()
                            success = False
        
        return success
    except Exception as e:
        logger.error(f"运行测试模块 {module_name} 时出错: {str(e)}")
        traceback.print_exc()
        return False

def run_tests(test_case=None, report_path=None):
    """运行所有测试"""
    test_modules = discover_test_modules()
    
    if not test_modules:
        logger.error("未找到测试模块")
        return False
    
    logger.info(f"找到 {len(test_modules)} 个测试模块: {', '.join(test_modules)}")
    
    all_success = True
    for module_name in test_modules:
        success = run_test_module(module_name, test_case, report_path)
        all_success = all_success and success
    
    return all_success

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试运行工具")
    parser.add_argument("--test-case", help="指定要运行的测试用例")
    parser.add_argument("--report-path", help="测试报告输出路径")
    
    args = parser.parse_args()
    
    success = run_tests(args.test_case, args.report_path)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())