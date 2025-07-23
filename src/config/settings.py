"""
系统配置管理
"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class SparkConfig(BaseSettings):
    """讯飞星火模型配置"""
    
    app_id: str = Field(default="mTqPOjsqrEIjoZytgSay", env="SPARK_APP_ID")
    api_secret: str = Field(default="rCmEOLLbGsTOoNxhAwFB", env="SPARK_API_SECRET")
    
    # 兼容性字段
    api_key: str = Field(default="", env="SPARK_API_KEY")
    base_url: str = Field(default="https://spark-api-open.xf-yun.com/v2/", env="SPARK_BASE_URL")
    
    # 模型配置
    model_name: str = "x1"
    
    class Config:
        env_file = "config.env"
        extra = "ignore"


class DatabaseConfig(BaseSettings):
    """数据库配置"""
    
    chroma_persist_dir: str = Field(
        "./data/chroma_db", 
        env="CHROMA_PERSIST_DIRECTORY"
    )
    
    redis_host: str = Field("localhost", env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_db: int = Field(0, env="REDIS_DB")
    
    class Config:
        env_file = "config.env"
        extra = "ignore"


class SystemConfig(BaseSettings):
    """系统配置"""
    
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("./logs/interview_agent.log", env="LOG_FILE")
    
    max_concurrent_interviews: int = Field(5, env="MAX_CONCURRENT_INTERVIEWS")
    analysis_timeout: int = Field(300, env="ANALYSIS_TIMEOUT")
    
    # 文件上传配置
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_video_formats: list = [".mp4", ".avi", ".mov", ".mkv"]
    allowed_document_formats: list = [".pdf", ".docx", ".doc"]
    
    class Config:
        env_file = "config.env"
        extra = "ignore"


class ModelConfig:
    """模型性能配置"""
    
    # 视觉分析配置
    MEDIAPIPE_CONFIDENCE = 0.5
    DEEPFACE_BACKEND = "opencv"
    
    # 音频分析配置  
    AUDIO_SAMPLE_RATE = 16000
    AUDIO_CHUNK_SIZE = 1024
    
    # 文本分析配置
    MAX_SEQUENCE_LENGTH = 512
    BERT_MODEL_NAME = "bert-base-chinese"


# 全局配置实例
spark_config = SparkConfig()
database_config = DatabaseConfig()
system_config = SystemConfig()
model_config = ModelConfig() 