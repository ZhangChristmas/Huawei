# FastAPI应用入口
from fastapi import FastAPI
from .core.config import settings
from .routers import auth_router, user_router, device_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    # Add other metadata here
)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to SuivueTong Backend API"}

# 包含各个路由
app.include_router(auth_router.router, tags=["Authentication"], prefix="/api/auth")
app.include_router(user_router.router, tags=["Users"], prefix="/api/users")
app.include_router(device_router.router, tags=["Devices"], prefix="/api/devices")
