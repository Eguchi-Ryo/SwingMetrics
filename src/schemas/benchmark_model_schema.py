from pydantic import BaseModel, HttpUrl
from typing import Optional

class BenchmarkModelBase(BaseModel):
    user_id: Optional[int] = None
    source_swing_id: Optional[int] = None
    name: str
    sport_type: str
    camera_angle: str
    handness: Optional[str] = "right"
    video_url: HttpUrl
    frames_json: dict

class BenchmarkModelCreate(BenchmarkModelBase):
    pass

class BenchmarkModel(BenchmarkModelBase):
    id: int

    class Config:
        orm_mode = True