"""
SwingMetrics ファイル管理システム
"""
import os
import shutil
from typing import Optional, Tuple
from datetime import datetime
from src.config import get_settings
from src.security.auth import FileSecurityManager, AuditLogger


class FileManager:
    """ファイル管理クラス"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def upload_video(
        self,
        user_id: str,
        file_path: str,
        original_filename: str
    ) -> Tuple[bool, str, Optional[str]]:
        """動画ファイルをアップロード"""
        try:
            # ファイルサイズチェック
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > self.settings.MAX_VIDEO_SIZE_MB:
                AuditLogger.log_file_operation(user_id, "upload_failed_size", file_path)
                return False, f"ファイルサイズが大きすぎます（最大: {self.settings.MAX_VIDEO_SIZE_MB}MB）", None
            
            # ファイルシグネチャ検証
            if not FileSecurityManager.validate_file_signature(
                file_path,
                self.settings.ALLOWED_VIDEO_EXTENSIONS
            ):
                AuditLogger.log_file_operation(user_id, "upload_failed_signature", file_path)
                return False, "ファイル形式が無効です", None
            
            # 安全なファイル名を生成
            safe_filename = FileSecurityManager.generate_secure_filename(user_id, original_filename)
            
            # ユーザー専用ディレクトリにコピー
            user_upload_dir = FileSecurityManager.get_user_file_path(user_id, "video")
            destination_path = os.path.join(user_upload_dir, safe_filename)
            
            shutil.copy2(file_path, destination_path)
            
            AuditLogger.log_file_operation(user_id, "upload_success", destination_path)
            
            return True, "ファイルをアップロードしました", destination_path
        
        except Exception as e:
            AuditLogger.log_file_operation(user_id, "upload_error", str(e))
            return False, f"アップロードエラー: {str(e)}", None
    
    def delete_file(self, user_id: str, file_path: str) -> Tuple[bool, str]:
        """ファイルを削除"""
        try:
            # ユーザー所有確認
            if not FileSecurityManager.check_user_owns_file(user_id, file_path):
                AuditLogger.log_file_operation(user_id, "delete_unauthorized", file_path)
                return False, "このファイルを削除する権限がありません"
            
            # ファイル存在確認
            if not os.path.exists(file_path):
                return False, "ファイルが見つかりません"
            
            # 削除
            os.remove(file_path)
            AuditLogger.log_file_operation(user_id, "delete_success", file_path)
            
            return True, "ファイルを削除しました"
        
        except Exception as e:
            AuditLogger.log_file_operation(user_id, "delete_error", str(e))
            return False, f"削除エラー: {str(e)}"
    
    def get_user_files(self, user_id: str, file_type: str = "video"):
        """ユーザーのファイル一覧を取得"""
        try:
            user_dir = FileSecurityManager.get_user_file_path(user_id, file_type)
            
            files = []
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    files.append({
                        "filename": filename,
                        "path": file_path,
                        "size_mb": os.path.getsize(file_path) / (1024 * 1024),
                        "created": datetime.fromtimestamp(os.path.getctime(file_path)),
                        "modified": datetime.fromtimestamp(os.path.getmtime(file_path))
                    })
            
            return True, files
        
        except Exception as e:
            return False, []
    
    def cleanup_user_files(self, user_id: str, days_old: int = 30):
        """古いユーザーファイルを削除"""
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (days_old * 86400)
            
            for file_type in ["video", "data"]:
                user_dir = FileSecurityManager.get_user_file_path(user_id, file_type)
                
                for filename in os.listdir(user_dir):
                    file_path = os.path.join(user_dir, filename)
                    if os.path.isfile(file_path):
                        file_time = os.path.getmtime(file_path)
                        if file_time < cutoff_time:
                            os.remove(file_path)
                            AuditLogger.log_file_operation(user_id, "cleanup_old_file", file_path)
            
            return True, f"{days_old}日以上前のファイルを削除しました"
        
        except Exception as e:
            return False, str(e)


class CacheManager:
    """キャッシュ管理"""
    
    def __init__(self):
        self.settings = get_settings()
        self.cache_enabled = self.settings.CACHE_ENABLED
    
    def get_cache_path(self, cache_key: str) -> str:
        """キャッシュファイルのパスを取得"""
        cache_filename = f"{cache_key}.cache"
        return os.path.join(self.settings.CACHE_DIR, cache_filename)
    
    def get_cached_data(self, cache_key: str):
        """キャッシュからデータを取得"""
        if not self.cache_enabled:
            return None
        
        try:
            import json
            import time
            
            cache_path = self.get_cache_path(cache_key)
            
            if not os.path.exists(cache_path):
                return None
            
            # キャッシュ有効期限チェック
            file_time = os.path.getmtime(cache_path)
            if time.time() - file_time > self.settings.CACHE_TTL_SECONDS:
                os.remove(cache_path)
                return None
            
            with open(cache_path, 'r') as f:
                return json.load(f)
        
        except Exception:
            return None
    
    def set_cached_data(self, cache_key: str, data):
        """データをキャッシュに保存"""
        if not self.cache_enabled:
            return
        
        try:
            import json
            
            cache_path = self.get_cache_path(cache_key)
            
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        
        except Exception:
            pass
    
    def invalidate_cache(self, cache_key: str):
        """キャッシュを無効化"""
        try:
            cache_path = self.get_cache_path(cache_key)
            if os.path.exists(cache_path):
                os.remove(cache_path)
        
        except Exception:
            pass
    
    def clear_all_cache(self):
        """すべてのキャッシュをクリア"""
        try:
            for filename in os.listdir(self.settings.CACHE_DIR):
                if filename.endswith('.cache'):
                    cache_path = os.path.join(self.settings.CACHE_DIR, filename)
                    os.remove(cache_path)
        
        except Exception:
            pass


# グローバルインスタンス
file_manager = FileManager()
cache_manager = CacheManager()
