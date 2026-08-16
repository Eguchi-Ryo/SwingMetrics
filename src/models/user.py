from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from datetime import datetime
from .database import Base
from src.security.auth import PasswordManager

class User(Base):
    """ユーザーモデル"""
    __tablename__ = "users"

    # 基本情報
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    
    # 認証
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # プロフィール
    bio = Column(Text, nullable=True)
    profile_image_url = Column(String, nullable=True)
    
    # 統計情報
    total_swings = Column(Integer, default=0)
    average_score = Column(Float, default=0.0)
    best_score = Column(Float, default=0.0)
    
    # セキュリティ
    last_login = Column(DateTime, nullable=True)
    last_password_change = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    
    # 管理
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def set_password(self, password: str):
        """パスワード設定"""
        self.hashed_password = PasswordManager.hash_password(password)
        self.last_password_change = datetime.utcnow()
    
    def verify_password(self, password: str) -> bool:
        """パスワード検証"""
        return PasswordManager.verify_password(password, self.hashed_password)
    
    def record_login(self):
        """ログイン記録"""
        self.last_login = datetime.utcnow()
        self.failed_login_attempts = 0
    
    def record_failed_login(self):
        """ログイン失敗記録"""
        self.failed_login_attempts += 1
    
    def is_locked(self, max_attempts: int = 5) -> bool:
        """ロックアウト状態チェック"""
        return self.failed_login_attempts >= max_attempts
    
    def unlock(self):
        """ロック解除"""
        self.failed_login_attempts = 0