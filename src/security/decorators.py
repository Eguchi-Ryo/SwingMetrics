"""
SwingMetrics セキュリティデコレータ
"""
from functools import wraps
from typing import Optional
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from src.security.auth import JWTManager, AccessControlManager, AuditLogger

security = HTTPBearer()


async def get_current_user_id(credentials: HTTPAuthCredentials = Depends(security)) -> str:
    """現在のユーザーIDを取得（FastAPI依存関数）"""
    try:
        token = credentials.credentials
        payload = JWTManager.verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # トークンタイプ確認
        token_type = payload.get("type")
        if token_type == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cannot use refresh token for access"
            )
        
        return user_id
    
    except ValueError as e:
        AuditLogger.log_auth_attempt("unknown", False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


# FastAPI依存関数として使用
require_auth = Depends(get_current_user_id)


def require_owner(resource_param: str = "owner_id"):
    """リソース所有者の確認デコレータ"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user_id: str, **kwargs):
            resource_owner_id = kwargs.get(resource_param)
            
            if not AccessControlManager.check_user_owns_resource(
                current_user_id,
                resource_owner_id
            ):
                AuditLogger.log_access(
                    current_user_id,
                    "unauthorized_access_attempt",
                    resource_param,
                    False
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access this resource"
                )
            
            return await func(*args, current_user_id=current_user_id, **kwargs)
        
        return wrapper
    
    return decorator


def rate_limit(requests_per_minute: int = 60):
    """レート制限デコレータ"""
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    user_requests = defaultdict(list)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user_id: str = None, **kwargs):
            if not current_user_id:
                return await func(*args, **kwargs)
            
            now = datetime.utcnow()
            one_minute_ago = now - timedelta(minutes=1)
            
            # 古いリクエストを削除
            user_requests[current_user_id] = [
                req_time for req_time in user_requests[current_user_id]
                if req_time > one_minute_ago
            ]
            
            # リクエスト数チェック
            if len(user_requests[current_user_id]) >= requests_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
            
            # リクエストを記録
            user_requests[current_user_id].append(now)
            
            return await func(*args, current_user_id=current_user_id, **kwargs)
        
        return wrapper
    
    return decorator


def audit_log(action: str, resource_type: str = "resource"):
    """監査ログデコレータ"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user_id: str = None, **kwargs):
            try:
                result = await func(*args, current_user_id=current_user_id, **kwargs)
                
                if current_user_id:
                    AuditLogger.log_access(
                        current_user_id,
                        action,
                        resource_type,
                        True
                    )
                
                return result
            
            except Exception as e:
                if current_user_id:
                    AuditLogger.log_access(
                        current_user_id,
                        action,
                        resource_type,
                        False
                    )
                raise
        
        return wrapper
    
    return decorator


class RateLimitManager:
    """レート制限マネージャー"""
    
    def __init__(self):
        self.attempts = {}
    
    def check_rate_limit(
        self,
        identifier: str,
        max_attempts: int = 5,
        window_minutes: int = 15
    ) -> bool:
        """レート制限チェック"""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        
        # 時間枠を超えたリクエストを削除
        cutoff_time = now - timedelta(minutes=window_minutes)
        self.attempts[identifier] = [
            attempt_time for attempt_time in self.attempts[identifier]
            if attempt_time > cutoff_time
        ]
        
        # 試行回数をチェック
        if len(self.attempts[identifier]) >= max_attempts:
            return False
        
        # 試行を記録
        self.attempts[identifier].append(now)
        
        return True


# グローバルレート制限マネージャー
rate_limit_manager = RateLimitManager()

