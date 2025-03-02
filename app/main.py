from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
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
from app.utils.es_init import init_elasticsearch_indices
from app.api.routers.chat import router as chat_router
from app.api.routers.recommendations import router as recommendations_router
from app.utils.logger import configure_global_logging, qa_logger

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量用于追踪服务状态
running_services: Set[str] = set()
shutdown_event = asyncio.Event()

app = FastAPI(title="智能知识库助手", version="1.0.0")

# 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 配置模板
templates = Jinja2Templates(directory="app/templates")

# 日志配置
configure_global_logging()

# 注册路由
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(recommendations_router, prefix="/api", tags=["recommendations"])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """返回首页"""
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
async def startup_db_client():
    """服务启动事件"""
    qa_logger.log_info("应用服务启动...")
    
    # 检查Elasticsearch连接
    es_connected = await es_client.ping()
    if not es_connected:
        qa_logger.log_error("Elasticsearch 连接失败")
        raise HTTPException(status_code=500, detail="Elasticsearch 连接失败")
    else:
        qa_logger.log_info("Elasticsearch 连接成功")
    
    # 检查环境变量
    if not settings.DASHSCOPE_API_KEY:
        qa_logger.log_warning("未设置 DASHSCOPE_API_KEY 环境变量，使用测试密钥")
    else:
        qa_logger.log_info("DASHSCOPE_API_KEY 已配置")
    
    qa_logger.log_info("服务启动成功")

@app.on_event("shutdown")
async def shutdown_db_client():
    """服务关闭事件"""
    qa_logger.log_info("应用服务关闭...")
    
    # 这里可以添加清理资源的代码
    
    qa_logger.log_info("服务已完全关闭")

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

class CustomServer(uvicorn.Server):
    """自定义服务器类，用于处理优雅关闭"""
    def handle_exit(self, sig, frame):
        qa_logger.log_info(f"收到退出信号 {sig}...")
        # 标记服务器应该退出
        self.should_exit = True

def main():
    """主函数，用于启动服务"""
    try:
        # 设置信号处理
        setup_signal_handlers()
        
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 创建服务器实例
        server = CustomServer(
            uvicorn.Config(
                "app.main:app", 
                host=settings.HOST, 
                port=settings.PORT,
                log_level="info",
                reload=True
            )
        )
        
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
    qa_logger.log_info("启动服务器...")
    main() 