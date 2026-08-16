from pydantic import BaseModel, HttpUrl
from typing import Optional

class SwingBase(BaseModel):
    title: str
    sport_type: str
    camera_angle: str
    handness: Optional[str] = "right"
    video_url: HttpUrl
    annotated_video_url: Optional[HttpUrl] = None
    compared_benchmark_id: Optional[int] = None
    is_comparison_active: bool = True
    manual_annotations_json: Optional[dict] = None

class SwingCreate(SwingBase):
    pass

class Swing(SwingBase):
    id: int

    class Config:
        orm_mode = True