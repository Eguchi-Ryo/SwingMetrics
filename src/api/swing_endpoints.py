"""
SwingMetrics スイング管理APIエンドポイント
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import os
import tempfile

from src.models.database import get_db
from src.models.swing import Swing
from src.models.user import User
from src.security.decorators import rate_limit, get_current_user_id
from src.security.auth import AccessControlManager, AuditLogger
from src.services.file_manager import file_manager

router = APIRouter(prefix="/swings", tags=["swings"])


# ========================================
# Pydantic スキーマ
# ========================================

class SwingCreate(BaseModel):
    """スイング作成リクエスト"""
    title: str = Field(..., min_length=1, max_length=200)
    sport_type: str = Field(..., description="Golf, Baseball, etc.")
    camera_angle: str = Field(..., description="Side, Front, Rear")
    handness: str = Field(..., description="Right, Left")
    compared_benchmark_id: Optional[int] = None


class SwingResponse(BaseModel):
    """スイングレスポンス"""
    id: int
    user_id: int
    title: str
    sport_type: str
    camera_angle: str
    handness: str
    overall_score: float
    processing_status: str
    created_at: datetime
    analyzed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class SwingDetailResponse(SwingResponse):
    """スイング詳細レスポンス"""
    duration_ms: Optional[int]
    is_public: bool
    is_shared: bool
    analysis_data: Optional[dict]


# ========================================
# エンドポイント
# ========================================

@router.get("/", response_model=List[SwingResponse])
async def list_swings(
    skip: int = 0,
    limit: int = 20,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """ユーザーのスイング一覧を取得（自分のものだけ）"""
    
    swings = db.query(Swing).filter(
        Swing.user_id == int(current_user_id)
    ).offset(skip).limit(limit).all()
    
    AuditLogger.log_access(current_user_id, "list_swings", "swings", True)
    
    return swings


@router.get("/{swing_id}", response_model=SwingDetailResponse)
async def get_swing(
    swing_id: int,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """スイング詳細を取得"""
    
    swing = db.query(Swing).filter(Swing.id == swing_id).first()
    
    if not swing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スイングが見つかりません"
        )
    
    # アクセス権限チェック
    if not AccessControlManager.check_user_owns_swing(current_user_id, str(swing.user_id)):
        # 公開スイングなら許可
        if not swing.is_public:
            AuditLogger.log_access(
                current_user_id,
                "unauthorized_swing_access",
                f"swing_{swing_id}",
                False
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="このスイングを閲覧する権限がありません"
            )
    
    AuditLogger.log_access(current_user_id, "get_swing", f"swing_{swing_id}", True)
    
    return swing


@router.post("/", response_model=SwingResponse)
@rate_limit(requests_per_minute=30)
async def create_swing(
    swing_data: SwingCreate,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """新規スイングを作成"""
    
    swing = Swing(
        user_id=int(current_user_id),
        title=swing_data.title,
        sport_type=swing_data.sport_type,
        camera_angle=swing_data.camera_angle,
        handness=swing_data.handness,
        compared_benchmark_id=swing_data.compared_benchmark_id,
        processing_status="pending",
        video_file_path=""  # 動画アップロード時に設定
    )
    
    db.add(swing)
    db.commit()
    db.refresh(swing)
    
    AuditLogger.log_access(current_user_id, "create_swing", f"swing_{swing.id}", True)
    
    return swing


@router.post("/{swing_id}/upload-video")
async def upload_video(
    swing_id: int,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """スイングに動画をアップロード"""
    
    swing = db.query(Swing).filter(Swing.id == swing_id).first()
    
    if not swing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スイングが見つかりません"
        )
    
    # オーナーシップ確認
    if not AccessControlManager.check_user_owns_swing(current_user_id, str(swing.user_id)):
        AuditLogger.log_access(
            current_user_id,
            "unauthorized_upload",
            f"swing_{swing_id}",
            False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このスイングに動画をアップロードする権限がありません"
        )
    
    # ファイル一時保存
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # ファイルをアップロード
        success, message, file_path = file_manager.upload_video(
            current_user_id,
            tmp_path,
            file.filename
        )
        
        if not success:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # スイングに動画パスを設定
        swing.video_file_path = file_path
        swing.processing_status = "processing"
        swing.mark_processing()
        db.commit()
        
        # 一時ファイルを削除
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        
        AuditLogger.log_access(
            current_user_id,
            "upload_video",
            f"swing_{swing_id}",
            True
        )
        
        return {
            "message": "動画をアップロードしました",
            "swing_id": swing_id,
            "status": "processing"
        }
    
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{swing_id}")
async def delete_swing(
    swing_id: int,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """スイングを削除"""
    
    swing = db.query(Swing).filter(Swing.id == swing_id).first()
    
    if not swing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スイングが見つかりません"
        )
    
    # オーナーシップ確認
    if not AccessControlManager.check_user_owns_swing(current_user_id, str(swing.user_id)):
        AuditLogger.log_access(
            current_user_id,
            "unauthorized_delete",
            f"swing_{swing_id}",
            False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このスイングを削除する権限がありません"
        )
    
    # ファイル削除
    if swing.video_file_path and os.path.exists(swing.video_file_path):
        file_manager.delete_file(current_user_id, swing.video_file_path)
    
    # DB削除
    db.delete(swing)
    db.commit()
    
    AuditLogger.log_access(current_user_id, "delete_swing", f"swing_{swing_id}", True)
    
    return {"message": "スイングを削除しました"}


@router.patch("/{swing_id}")
async def update_swing(
    swing_id: int,
    swing_data: SwingCreate,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """スイング情報を更新"""
    
    swing = db.query(Swing).filter(Swing.id == swing_id).first()
    
    if not swing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スイングが見つかりません"
        )
    
    # オーナーシップ確認
    if not AccessControlManager.check_user_owns_swing(current_user_id, str(swing.user_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このスイングを更新する権限がありません"
        )
    
    # 更新
    swing.title = swing_data.title
    swing.sport_type = swing_data.sport_type
    swing.camera_angle = swing_data.camera_angle
    swing.handness = swing_data.handness
    swing.compared_benchmark_id = swing_data.compared_benchmark_id
    swing.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(swing)
    
    AuditLogger.log_access(current_user_id, "update_swing", f"swing_{swing_id}", True)
    
    return swing