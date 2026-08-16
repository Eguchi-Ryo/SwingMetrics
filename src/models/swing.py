from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, DateTime, Float, Text
from datetime import datetime
from .database import Base

class Swing(Base):
    """スイング分析モデル"""
    __tablename__ = "swings"

    # 基本情報
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    
    # スイング情報
    sport_type = Column(String, nullable=False)  # Golf, Baseball, etc.
    camera_angle = Column(String, nullable=False)  # Side, Front, Rear
    handness = Column(String, nullable=False)  # Right, Left
    
    # ファイル情報
    video_url = Column(String, nullable=False)  # アップロードされた動画
    video_file_path = Column(String, nullable=False)  # サーバー上のパス
    annotated_video_url = Column(String, nullable=True)  # 骨格描画済み動画
    duration_ms = Column(Integer, nullable=True)
    
    # ベンチマーク
    compared_benchmark_id = Column(Integer, ForeignKey("benchmark_models.id"), nullable=True)
    is_comparison_active = Column(Boolean, default=True)
    
    # 分析結果
    overall_score = Column(Float, default=0.0)
    analysis_data = Column(JSON, nullable=True)  # フレームデータなど
    manual_annotations_json = Column(JSON, nullable=True)
    
    # 処理状態
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    processing_progress = Column(Float, default=0.0)  # 0-100%
    processing_error = Column(Text, nullable=True)
    
    # 公開設定
    is_public = Column(Boolean, default=False)  # 他ユーザーに見せるか（ベンチマークとして使用可能）
    is_shared = Column(Boolean, default=False)  # 特定ユーザーと共有するか
    
    # 管理情報
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    analyzed_at = Column(DateTime, nullable=True)
    
    def mark_processing(self):
        """処理中状態に設定"""
        self.processing_status = "processing"
        self.processing_progress = 0.0
    
    def mark_completed(self):
        """完了状態に設定"""
        self.processing_status = "completed"
        self.processing_progress = 100.0
        self.analyzed_at = datetime.utcnow()
    
    def mark_failed(self, error_message: str):
        """失敗状態に設定"""
        self.processing_status = "failed"
        self.processing_error = error_message
    
    def set_progress(self, progress: float):
        """処理進捗を更新"""
        self.processing_progress = min(100.0, max(0.0, progress))