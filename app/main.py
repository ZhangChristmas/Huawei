# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware # 引入CORS中间件

from app.core.config import settings
from app.db.mongodb_utils import connect_to_mongo, close_mongo_connection, create_db_indexes # 引入创建索引函数
from app.routers import auth_router, device_router, notification_router # 引入我们的路由模块
from app.mqtt import mqtt_client # 引入MQTT客户端模块 (即使mqtt_client.py暂时为空)

# 使用 lifespan 管理应用生命周期事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("FastAPI application startup...")
    await connect_to_mongo()
    if settings.DEBUG: # 开发模式下可以尝试创建索引，生产环境通常手动或迁移工具管理
        await create_db_indexes()
    
    # 启动MQTT客户端 (确保mqtt_client.py中有相应的启动函数)
    # 这个函数需要设计成非阻塞的，或者在后台线程运行
    try:
        await mqtt_client.start_mqtt_client() # 假设mqtt_client.py中有这个异步函数
        print("MQTT client started successfully.")
    except Exception as e:
        print(f"Failed to start MQTT client: {e}")
        # 根据需求决定是否因为MQTT启动失败而阻止应用启动
        # raise # 如果MQTT是核心，则应该抛出异常

    yield
    # Shutdown
    print("FastAPI application shutdown...")
    try:
        await mqtt_client.stop_mqtt_client() # 假设mqtt_client.py中有这个异步函数
        print("MQTT client stopped.")
    except Exception as e:
        print(f"Error stopping MQTT client: {e}")
    
    await close_mongo_connection()
    print("FastAPI application shutdown complete.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" # API文档路径
)

# 配置 CORS (如果需要)
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS], # 接受字符串列表
        allow_credentials=True,
        allow_methods=["*"], # 允许所有方法
        allow_headers=["*"], # 允许所有头部
    )

# 根路径 (测试用)
@app.get("/", summary="Root Endpoint")
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}"}

# 引入API路由
app.include_router(auth_router.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(device_router.router, prefix=f"{settings.API_V1_STR}/devices", tags=["Devices & Management"])
app.include_router(notification_router.router, prefix=f"{settings.API_V1_STR}/notifications", tags=["Notifications"])

# 如果你有其他顶层路由，例如一个健康检查端点
@app.get("/health", summary="Health Check")
async def health_check():
    # 可以在这里添加更复杂的健康检查，如数据库连接、MQTT连接等
    return {"status": "healthy"}
