from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import signal
import sys
import asyncio
from typing import Set
from app.config.settings import settings
from app.utils.es_client import es_client

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量用于追踪服务状态
running_services: Set[str] = set()
shutdown_event = asyncio.Event()

app = FastAPI(title="智能知识库助手")

# 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 配置模板
templates = Jinja2Templates(directory="templates")

# 导入路由
from app.api.routers import chat

# 注册路由
app.include_router(chat.router, prefix="/api")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def cleanup_service(service_name: str) -> None:
    """清理特定服务的资源"""
    try:
        if service_name == "elasticsearch":
            # 关闭 Elasticsearch 客户端连接
            await es_client.close()
            logger.info("Elasticsearch 客户端已关闭")
        # 可以在这里添加其他服务的清理逻辑
        running_services.remove(service_name)
        logger.info(f"{service_name} 服务已清理完成")
    except Exception as e:
        logger.error(f"清理 {service_name} 服务时出错: {str(e)}")

async def cleanup_all_services():
    """按照合理的顺序清理所有服务"""
    # 定义服务关闭顺序
    cleanup_order = ["fastapi", "elasticsearch"]
    
    for service in cleanup_order:
        if service in running_services:
            await cleanup_service(service)
    
    logger.info("所有服务已清理完成")

@app.on_event("startup")
async def startup_event():
    """服务启动时的初始化操作"""
    try:
        # 检查 Elasticsearch 连接
        if not await es_client.ping():
            logger.error("无法连接到 Elasticsearch")
            raise Exception("Elasticsearch 连接失败")
        running_services.add("elasticsearch")
        logger.info("Elasticsearch 连接成功")

        # 检查必要的环境变量
        if not settings.DASHSCOPE_API_KEY:
            logger.error("未设置 DASHSCOPE_API_KEY")
            raise Exception("缺少必要的环境变量: DASHSCOPE_API_KEY")
        
        running_services.add("fastapi")
        logger.info("所有初始化检查完成")
    except Exception as e:
        logger.error(f"服务启动初始化失败: {str(e)}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时的清理操作"""
    try:
        await cleanup_all_services()
    except Exception as e:
        logger.error(f"服务关闭清理失败: {str(e)}")

def signal_handler(signum, frame):
    """处理系统信号"""
    logger.info(f"收到信号: {signal.Signals(signum).name}")
    # 设置关闭事件
    if not shutdown_event.is_set():
        shutdown_event.set()
        logger.info("正在优雅地关闭服务...")

def setup_signal_handlers():
    """设置信号处理器"""
    # 处理 CTRL+C
    signal.signal(signal.SIGINT, signal_handler)
    # 处理终端关闭
    signal.signal(signal.SIGTERM, signal_handler)

class UvicornServer:
    """Uvicorn 服务器封装类"""
    def __init__(self, app, host="0.0.0.0", port=8000):
        self.config = uvicorn.Config(
            app,
            host=host,
            port=port,
            reload=True,
            log_level="debug"
        )
        self.server = uvicorn.Server(self.config)
    
    async def run(self):
        """运行服务器"""
        try:
            await self.server.serve()
        except Exception as e:
            logger.error(f"服务器运行出错: {str(e)}")
        finally:
            await cleanup_all_services()

def main():
    """主函数，用于启动服务"""
    try:
        # 设置信号处理
        setup_signal_handlers()
        
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 创建服务器实例
        server = UvicornServer("app.main:app")
        
        # 运行服务器
        loop.run_until_complete(server.run())
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
    finally:
        # 关闭事件循环
        loop.close()
        logger.info("服务已完全关闭")
        sys.exit(0)

if __name__ == "__main__":
    main() 