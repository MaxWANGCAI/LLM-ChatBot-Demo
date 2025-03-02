#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
项目管理脚本
提供项目的启动、停止、状态检查、数据导入等功能
"""

import sys
import os
import argparse
import logging
import subprocess
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

def run_script(script_name, args=None):
    """运行指定的脚本"""
    script_path = current_dir / f"{script_name}.py"
    
    if not script_path.exists():
        logger.error(f"脚本 {script_name}.py 不存在")
        return False
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    logger.info(f"正在执行: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 输出脚本的输出
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        if result.returncode != 0:
            logger.error(f"脚本执行失败，退出码: {result.returncode}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"执行脚本时出错: {str(e)}")
        return False

def start_server(args):
    """启动服务器"""
    return run_script("start_server")

def stop_server(args):
    """停止服务器"""
    return run_script("stop_server")

def check_status(args):
    """检查服务状态"""
    return run_script("check_status")

def import_data(args):
    """导入数据"""
    return run_script("import_data", args.file_path)

def run_tests(args):
    """运行测试"""
    test_args = []
    if args.test_case:
        test_args.append("--test-case")
        test_args.append(args.test_case)
    
    if args.report_path:
        test_args.append("--report-path")
        test_args.append(args.report_path)
    
    return run_script("run_tests", test_args)

def setup_parser():
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(description="项目管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 启动服务器
    start_parser = subparsers.add_parser("start", help="启动服务器")
    start_parser.set_defaults(func=start_server)
    
    # 停止服务器
    stop_parser = subparsers.add_parser("stop", help="停止服务器")
    stop_parser.set_defaults(func=stop_server)
    
    # 检查状态
    status_parser = subparsers.add_parser("status", help="检查服务状态")
    status_parser.set_defaults(func=check_status)
    
    # 导入数据
    import_parser = subparsers.add_parser("import", help="导入数据")
    import_parser.add_argument("file_path", nargs="*", help="要导入的数据文件路径")
    import_parser.set_defaults(func=import_data)
    
    # 运行测试
    test_parser = subparsers.add_parser("test", help="运行测试")
    test_parser.add_argument("--test-case", help="指定要运行的测试用例")
    test_parser.add_argument("--report-path", help="测试报告输出路径")
    test_parser.set_defaults(func=run_tests)
    
    return parser

def main():
    """主函数"""
    parser = setup_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    success = args.func(args)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 