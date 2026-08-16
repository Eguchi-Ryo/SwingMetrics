from sqlalchemy import Column, Integer, String, JSON
from .database import Base

class BenchmarkModel(Base):
    __tablename__ = "benchmark_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    source_swing_id = Column(Integer, ForeignKey("swings.id"))
    name = Column(String)
    sport_type = Column(String)
    camera_angle = Column(String)
    handness = Column(String)
    video_url = Column(String)
    frames_json = Column(JSON)