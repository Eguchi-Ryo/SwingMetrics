"""
SwingMetrics 認証APIエンドポイント
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from src.models.database import get_db
from src.models.user import User
from src.security.auth import PasswordManager, JWTManager, AuditLogger
from src.security.decorators import get_current_user_id

router = APIRouter(prefix="/auth", tags=["auth"])


# ========================================
# Pydantic スキーマ
# ========================================

class UserRegister(BaseModel):
    """ユーザー登録リクエスト"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """ユーザーログインリクエスト"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """トークンレスポンス"""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class UserResponse(BaseModel):
    """ユーザーレスポンス"""
    id: int
    email: str
    username: str
    name: str
    bio: str
    is_verified: bool
    total_swings: int
    average_score: float
    created_at: datetime
    
    class Config:
        from_attributes = True


# ========================================
# エンドポイント
# ========================================

@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """新規ユーザー登録"""
    
    # メール重複チェック
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="メールアドレスは既に登録されています"
        )
    
    # ユーザー名重複チェック
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ユーザー名は既に使用されています"
        )
    
    # パスワード強度チェック
    is_valid, message = PasswordManager.validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # ユーザー作成
    user = User(
        email=user_data.email,
        username=user_data.username,
        name=user_data.name
    )
    user.set_password(user_data.password)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # ユーザー用ファイルディレクトリを作成
    from src.security.auth import FileSecurityManager
    FileSecurityManager.get_user_file_path(str(user.id), "video")
    
    # トークン生成
    tokens = JWTManager.create_token_pair(str(user.id))
    
    AuditLogger.log_auth_attempt(user_data.username, True)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=30 * 60  # 30 minutes
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """ユーザーログイン"""
    
    # レート制限チェック
    if not rate_limit_manager.check_rate_limit(
        login_data.username,
        max_attempts=5,
        window_minutes=15
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ログイン試行が多すぎます。しばらく待ってからやり直してください"
        )
    
    # ユーザー検索
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user:
        AuditLogger.log_auth_attempt(login_data.username, False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません"
        )
    
    # ロックアウト確認
    if user.is_locked():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="アカウントがロックされています。管理者に連絡してください"
        )
    
    # パスワード検証
    if not user.verify_password(login_data.password):
        user.record_failed_login()
        db.commit()
        AuditLogger.log_auth_attempt(login_data.username, False)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません"
        )
    
    # アクティブ状態確認
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このアカウントは無効です"
        )
    
    # ログイン記録
    user.record_login()
    db.commit()
    
    # トークン生成
    tokens = JWTManager.create_token_pair(str(user.id))
    
    AuditLogger.log_auth_attempt(login_data.username, True)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=30 * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """トークン更新"""
    
    try:
        payload = JWTManager.verify_token(refresh_token)
        
        # リフレッシュトークンか確認
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        
        user_id = payload.get("sub")
        
        # ユーザー存在確認
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise ValueError("User not found")
        
        # 新しいトークンペアを生成
        tokens = JWTManager.create_token_pair(user_id)
        
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=30 * 60
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """現在のユーザー情報を取得"""
    
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です"
        )
    
    user = db.query(User).filter(User.id == int(current_user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません"
        )
    
    return user


@router.post("/logout")
async def logout(current_user_id: str = Depends(get_current_user_id)):
    """ログアウト"""
    
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です"
        )
    
    # 注: JWTはステートレスなため、クライアント側でトークンを削除するだけで良い
    # 必要に応じて、トークンブラックリストを実装することも可能
    
    return {"message": "ログアウトしました"}


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """パスワード変更"""
    
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です"
        )
    
    user = db.query(User).filter(User.id == int(current_user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません"
        )
    
    # 現在のパスワード確認
    if not user.verify_password(old_password):
        AuditLogger.log_access(current_user_id, "invalid_password_change_attempt", "password", False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="現在のパスワードが正しくありません"
        )
    
    # 新しいパスワード強度チェック
    is_valid, message = PasswordManager.validate_password_strength(new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # パスワード更新
    user.set_password(new_password)
    db.commit()
    
    AuditLogger.log_access(current_user_id, "password_change", "password", True)
    
    return {"message": "パスワードを変更しました"}
