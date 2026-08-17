"""
SwingMetrics バックエンド設定
"""
import os
from datetime import timedelta
from functools import lru_cache

class Settings:
    """アプリケーション設定"""
    
    # ================================
    # アプリケーション基本設定
    # ================================
    APP_NAME = "SwingMetrics API"
    APP_VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # ================================
    # セキュリティ設定
    # ================================
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # JWT設定
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))
    JWT_REFRESH_EXPIRATION_DAYS = int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", 7))
    
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # CORS設定
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:5001").split(",")
    
    # ================================
    # データベース設定
    # ================================
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/swingmetrics"
    )
    
    # ================================
    # ファイルアップロード設定
    # ================================
    # アップロードディレクトリ
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/swing_metrics/uploads")
    
    # ユーザーデータディレクトリ（ユーザーIDごと）
    USER_DATA_DIR = os.getenv("USER_DATA_DIR", "/tmp/swing_metrics/user_data")
    
    # キャッシュディレクトリ
    CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/swing_metrics/cache")
    
    # 許可されるファイル拡張子
    ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
    
    # ファイルサイズ制限 (MB)
    MAX_VIDEO_SIZE_MB = int(os.getenv("MAX_VIDEO_SIZE_MB", 500))
    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", 10))
    
    # ================================
    # ビデオ処理設定
    # ================================
    VIDEO_PROCESSING_TIMEOUT = 600  # 10分
    YOLO_MODEL = "yolov8n-pose.pt"
    DEVICE = os.getenv("DEVICE", "auto")  # auto, cpu, cuda:0
    
    # ================================
    # キャッシング設定
    # ================================
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 3600))
    
    # ================================
    # ログ設定
    # ================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "/tmp/swing_metrics/app.log")
    
    # ================================
    # 本番環境設定
    # ================================
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    IS_PRODUCTION = ENVIRONMENT == "production"
    
    def __init__(self):
        """初期化時にディレクトリ作成"""
        self._create_directories()
    
    def _create_directories(self):
        """必要なディレクトリを作成"""
        for directory in [self.UPLOAD_DIR, self.USER_DATA_DIR, self.CACHE_DIR]:
            os.makedirs(directory, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """設定をシングルトンで取得"""
    return Settings()


# セキュリティ設定
class SecurityConfig:
    """セキュリティ関連の設定"""
    
    # パスワード要件
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_NUMBERS = True
    REQUIRE_SPECIAL = True
    
    # レート制限
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_REQUESTS_PER_MINUTE = 60
    RATE_LIMIT_LOGIN_ATTEMPTS = 5
    
    # CSRF設定
    CSRF_ENABLED = True
    CSRF_TOKEN_EXPIRY_HOURS = 24
    
    # セッション設定
    SESSION_EXPIRY_MINUTES = 30
    SESSION_ABSOLUTE_TIMEOUT_HOURS = 24
    
    # ファイルアップロードセキュリティ
    SCAN_UPLOADED_FILES = True
    VERIFY_FILE_SIGNATURE = True
    QUARANTINE_SUSPICIOUS_FILES = True


# データベース設定
class DatabaseConfig:
    """データベース関連の設定"""
    
    # SQLAlchemy設定
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv("SQL_ECHO", "False").lower() == "true"
    
    # 接続プール
    POOL_SIZE = int(os.getenv("POOL_SIZE", 5))
    MAX_OVERFLOW = int(os.getenv("MAX_OVERFLOW", 10))
    POOL_RECYCLE = 3600  # 1時間


# API設定
class APIConfig:
    """API関連の設定"""
    
    # ページネーション
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # タイムアウト
    REQUEST_TIMEOUT_SECONDS = 30
    
    # バッチ処理
    BATCH_SIZE = 10


# 本番環境チェック
def validate_production_settings():
    """本番環境での設定妥当性チェック"""
    settings = get_settings()
    
    if settings.IS_PRODUCTION:
        issues = []
        
        # SECRET_KEYが変更されているか
        if settings.SECRET_KEY == "dev-secret-key-change-in-production":
            issues.append("SECRET_KEYが本番用に設定されていません")
        
        # ALLOWED_ORIGINSが適切に設定されているか
        if "localhost" in settings.ALLOWED_ORIGINS or "127.0.0.1" in settings.ALLOWED_ORIGINS:
            issues.append("ALLOWED_ORIGINSが本番用に設定されていません")
        
        # DATABASEが本番用になっているか
        if "sqlite" in settings.DATABASE_URL:
            issues.append("本番環境でSQLiteは推奨されません（PostgreSQL推奨）")
        
        if issues:
            print("⚠️ 本番環境設定の警告:")
            for issue in issues:
                print(f"  - {issue}")
        
        return len(issues) == 0
    
    return True
