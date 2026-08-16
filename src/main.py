"""
SwingMetrics FastAPI メインアプリケーション
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

from src.config import get_settings
from src.models.database import Base, engine
from src.api import auth_endpoints, swing_endpoints, user_endpoints, benchmark_model_endpoints

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 設定取得
settings = get_settings()

# FastAPIアプリケーション初期化
app = FastAPI(
    title="SwingMetrics API",
    description="ゴルフ・野球スイング分析API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# データベーステーブル作成
Base.metadata.create_all(bind=engine)

# ========================================
# ミドルウェア設定
# ========================================

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    max_age=3600
)

# トラストホスト設定
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# ========================================
# カスタムエラーハンドラー
# ========================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """グローバルエラーハンドラー"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTPエラーハンドラー"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# ========================================
# ロータ登録
# ========================================

# 認証エンドポイント
app.include_router(auth_endpoints.router, prefix="/api")

# スイングエンドポイント
app.include_router(swing_endpoints.router, prefix="/api")

# ユーザーエンドポイント
app.include_router(user_endpoints.router, prefix="/api")

# ベンチマークモデルエンドポイント
app.include_router(benchmark_model_endpoints.router, prefix="/api")

# ========================================
# ヘルスチェック
# ========================================

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.ENVIRONMENT
    }


@app.get("/api/health")
async def api_health_check():
    """API ヘルスチェック"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# ========================================
# ルート
# ========================================

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "SwingMetrics API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "redoc": "/api/redoc"
    }


# ========================================
# スタートアップ・シャットダウン
# ========================================

@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    logger.info("SwingMetrics API starting up...")
    
    # ディレクトリ作成
    import os
    for directory in [
        settings.UPLOAD_DIR,
        settings.USER_DATA_DIR,
        settings.CACHE_DIR
    ]:
        os.makedirs(directory, exist_ok=True)
    
    logger.info("Directories created successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    logger.info("SwingMetrics API shutting down...")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
