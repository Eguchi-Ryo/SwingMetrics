"""
SwingMetrics 認証・セキュリティシステム
"""
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from functools import wraps
from passlib.context import CryptContext
import jwt
from src.config import get_settings

# パスワードハッシング設定
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)


class PasswordManager:
    """パスワード管理"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """パスワードをハッシュ化"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """パスワード検証"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """パスワード強度チェック"""
        if len(password) < 8:
            return False, "パスワードは8文字以上必要です"
        
        if not any(c.isupper() for c in password):
            return False, "大文字を含む必要があります"
        
        if not any(c.islower() for c in password):
            return False, "小文字を含む必要があります"
        
        if not any(c.isdigit() for c in password):
            return False, "数字を含む必要があります"
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "特殊文字を含む必要があります"
        
        return True, "OK"


class JWTManager:
    """JWT トークン管理"""
    
    @staticmethod
    def create_access_token(
        subject: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """アクセストークン生成"""
        settings = get_settings()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(subject: str) -> str:
        """リフレッシュトークン生成"""
        settings = get_settings()
        
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        to_encode = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> dict:
        """トークン検証"""
        settings = get_settings()
        
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("トークンが期限切れです")
        except jwt.InvalidTokenError:
            raise ValueError("無効なトークンです")
    
    @staticmethod
    def create_token_pair(subject: str) -> dict:
        """アクセストークンとリフレッシュトークンを生成"""
        return {
            "access_token": JWTManager.create_access_token(subject),
            "refresh_token": JWTManager.create_refresh_token(subject),
            "token_type": "bearer"
        }


class FileSecurityManager:
    """ファイルセキュリティ管理"""
    
    # ファイルシグネチャ（マジックナンバー）
    MAGIC_SIGNATURES = {
        b'\xFF\xD8\xFF': '.jpg',
        b'\x89PNG': '.png',
        b'GIF8': '.gif',
        b'\x00\x00\x00\x18ftypmp42': '.mp4',
        b'\x00\x00\x00\x20ftypmp42': '.mp4',
        b'RIFF': '.avi',
    }
    
    @staticmethod
    def validate_file_signature(file_path: str, allowed_extensions: set) -> bool:
        """ファイルシグネチャを検証"""
        try:
            with open(file_path, 'rb') as f:
                file_header = f.read(20)
            
            # ファイル拡張子を取得
            _, ext = os.path.splitext(file_path)
            
            # 拡張子が許可リストにあるか確認
            if ext.lower() not in allowed_extensions:
                return False
            
            # ファイルシグネチャを確認
            for signature, sig_ext in FileSecurityManager.MAGIC_SIGNATURES.items():
                if file_header.startswith(signature):
                    # 拡張子とシグネチャが一致
                    return sig_ext == ext.lower()
            
            return True  # シグネチャが不明な場合は通す（テキストファイルなど）
        
        except Exception:
            return False
    
    @staticmethod
    def generate_secure_filename(user_id: str, original_filename: str) -> str:
        """安全なファイル名を生成"""
        # ユーザーIDとタイムスタンプを含める
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        random_suffix = secrets.token_hex(8)
        
        # 元のファイル拡張子を保持
        _, ext = os.path.splitext(original_filename)
        
        return f"{user_id}_{timestamp}_{random_suffix}{ext}"
    
    @staticmethod
    def get_user_file_path(user_id: str, file_type: str = "video") -> str:
        """ユーザーのファイルパスを取得"""
        settings = get_settings()
        
        if file_type == "video":
            base_dir = settings.UPLOAD_DIR
        else:
            base_dir = settings.USER_DATA_DIR
        
        user_dir = os.path.join(base_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        
        return user_dir


class AccessControlManager:
    """アクセス制御マネージャー"""
    
    @staticmethod
    def check_user_owns_resource(user_id: str, resource_user_id: str) -> bool:
        """ユーザーがリソースを所有しているか確認"""
        return user_id == resource_user_id
    
    @staticmethod
    def check_user_owns_swing(user_id: str, swing_user_id: str) -> bool:
        """ユーザーがスイングを所有しているか確認"""
        return user_id == swing_user_id
    
    @staticmethod
    def check_user_owns_file(user_id: str, file_path: str) -> bool:
        """ユーザーがファイルを所有しているか確認"""
        settings = get_settings()
        user_data_dir = os.path.join(settings.USER_DATA_DIR, user_id)
        
        # ファイルパスが正規化されたユーザーディレクトリ配下にあるか確認
        real_path = os.path.realpath(file_path)
        real_user_dir = os.path.realpath(user_data_dir)
        
        return real_path.startswith(real_user_dir)


class AuditLogger:
    """監査ログ"""
    
    @staticmethod
    def log_access(user_id: str, action: str, resource: str, success: bool):
        """アクセスをログに記録"""
        timestamp = datetime.utcnow().isoformat()
        status = "SUCCESS" if success else "FAILED"
        print(f"[{timestamp}] [{status}] User: {user_id}, Action: {action}, Resource: {resource}")
    
    @staticmethod
    def log_auth_attempt(username: str, success: bool):
        """認証試行をログに記録"""
        timestamp = datetime.utcnow().isoformat()
        status = "SUCCESS" if success else "FAILED"
        print(f"[{timestamp}] [AUTH {status}] Username: {username}")
    
    @staticmethod
    def log_file_operation(user_id: str, operation: str, file_path: str):
        """ファイル操作をログに記録"""
        timestamp = datetime.utcnow().isoformat()
        print(f"[{timestamp}] [FILE] User: {user_id}, Operation: {operation}, File: {file_path}")
