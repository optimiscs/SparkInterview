"""
实时多模态分析配置文件
"""
import os
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class RealtimeAnalysisConfig:
    """实时分析配置类"""
    
    # WebSocket配置
    websocket_host: str = "0.0.0.0"
    websocket_port: int = 8000
    websocket_path: str = "/ws/multimodal-analysis"
    max_connections: int = 50
    connection_timeout: int = 300  # 5分钟
    heartbeat_interval: int = 30   # 心跳间隔（秒）
    
    # 视频分析配置
    video_fps: int = 2           # 视频分析帧率
    video_frame_width: int = 640
    video_frame_height: int = 480
    video_quality: float = 0.8   # JPEG压缩质量
    emotion_cache_duration: float = 2.0  # 情绪分析缓存时长（秒）
    
    # 音频分析配置
    audio_sample_rate: int = 16000    # 音频采样率
    audio_chunk_duration: int = 3000  # 音频片段时长（毫秒）
    audio_format: str = "webm"
    audio_cache_duration: float = 1.0  # 音频分析缓存时长（秒）
    
    # MediaPipe配置
    mediapipe_confidence: float = 0.5
    mediapipe_max_faces: int = 1
    mediapipe_refine_landmarks: bool = False  # 关闭以提高性能
    
    # DeepFace配置
    deepface_backend: str = "opencv"  # 'opencv', 'ssd', 'mtcnn', 'retinaface'
    deepface_model: str = "VGG-Face"  # 'VGG-Face', 'Facenet', 'OpenFace', 'DeepFace'
    deepface_detector: str = "opencv"
    deepface_enforce_detection: bool = False
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1  # 使用数据库1，避免与其他服务冲突
    redis_password: str = ""
    redis_ssl: bool = False
    redis_analysis_ttl: int = 3600  # 分析结果TTL（秒）
    
    # 性能配置
    max_workers: int = 4              # 线程池最大工作线程数
    processing_queue_size: int = 100  # 处理队列最大长度
    memory_limit_mb: int = 512        # 内存使用限制（MB）
    cpu_limit_percent: int = 80       # CPU使用限制（%）
    
    # 日志配置
    log_level: str = "INFO"
    log_analysis_performance: bool = True
    log_websocket_messages: bool = False  # 生产环境建议关闭
    
    # 安全配置
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 60
    max_frame_size_mb: int = 5        # 最大帧大小限制
    max_audio_size_mb: int = 10       # 最大音频大小限制
    
    # 功能开关
    enable_video_analysis: bool = True
    enable_audio_analysis: bool = True
    enable_emotion_detection: bool = True
    enable_gaze_tracking: bool = True
    enable_head_pose_estimation: bool = True
    enable_speech_emotion_analysis: bool = True
    
    @classmethod
    def from_env(cls) -> 'RealtimeAnalysisConfig':
        """从环境变量创建配置"""
        return cls(
            # WebSocket配置
            websocket_host=os.getenv("RT_WEBSOCKET_HOST", "0.0.0.0"),
            websocket_port=int(os.getenv("RT_WEBSOCKET_PORT", "8000")),
            max_connections=int(os.getenv("RT_MAX_CONNECTIONS", "50")),
            connection_timeout=int(os.getenv("RT_CONNECTION_TIMEOUT", "300")),
            
            # 视频配置
            video_fps=int(os.getenv("RT_VIDEO_FPS", "2")),
            video_frame_width=int(os.getenv("RT_FRAME_WIDTH", "640")),
            video_frame_height=int(os.getenv("RT_FRAME_HEIGHT", "480")),
            video_quality=float(os.getenv("RT_VIDEO_QUALITY", "0.8")),
            
            # 音频配置
            audio_sample_rate=int(os.getenv("RT_AUDIO_SAMPLE_RATE", "16000")),
            audio_chunk_duration=int(os.getenv("RT_AUDIO_CHUNK_DURATION", "3000")),
            
            # MediaPipe配置
            mediapipe_confidence=float(os.getenv("RT_MEDIAPIPE_CONFIDENCE", "0.5")),
            
            # DeepFace配置
            deepface_backend=os.getenv("RT_DEEPFACE_BACKEND", "opencv"),
            deepface_enforce_detection=os.getenv("RT_DEEPFACE_ENFORCE", "False").lower() == "true",
            
            # Redis配置
            redis_host=os.getenv("RT_REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("RT_REDIS_PORT", "6379")),
            redis_db=int(os.getenv("RT_REDIS_DB", "1")),
            redis_password=os.getenv("RT_REDIS_PASSWORD", ""),
            
            # 性能配置
            max_workers=int(os.getenv("RT_MAX_WORKERS", "4")),
            processing_queue_size=int(os.getenv("RT_QUEUE_SIZE", "100")),
            memory_limit_mb=int(os.getenv("RT_MEMORY_LIMIT_MB", "512")),
            cpu_limit_percent=int(os.getenv("RT_CPU_LIMIT_PERCENT", "80")),
            
            # 日志配置
            log_level=os.getenv("RT_LOG_LEVEL", "INFO"),
            log_analysis_performance=os.getenv("RT_LOG_PERFORMANCE", "True").lower() == "true",
            log_websocket_messages=os.getenv("RT_LOG_WEBSOCKET", "False").lower() == "true",
            
            # 安全配置
            enable_rate_limiting=os.getenv("RT_ENABLE_RATE_LIMIT", "True").lower() == "true",
            max_requests_per_minute=int(os.getenv("RT_MAX_REQUESTS_PER_MIN", "60")),
            max_frame_size_mb=int(os.getenv("RT_MAX_FRAME_SIZE_MB", "5")),
            max_audio_size_mb=int(os.getenv("RT_MAX_AUDIO_SIZE_MB", "10")),
            
            # 功能开关
            enable_video_analysis=os.getenv("RT_ENABLE_VIDEO", "True").lower() == "true",
            enable_audio_analysis=os.getenv("RT_ENABLE_AUDIO", "True").lower() == "true",
            enable_emotion_detection=os.getenv("RT_ENABLE_EMOTION", "True").lower() == "true",
            enable_gaze_tracking=os.getenv("RT_ENABLE_GAZE", "True").lower() == "true",
            enable_head_pose_estimation=os.getenv("RT_ENABLE_HEAD_POSE", "True").lower() == "true",
            enable_speech_emotion_analysis=os.getenv("RT_ENABLE_SPEECH_EMOTION", "True").lower() == "true",
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'websocket': {
                'host': self.websocket_host,
                'port': self.websocket_port,
                'path': self.websocket_path,
                'max_connections': self.max_connections,
                'timeout': self.connection_timeout,
                'heartbeat_interval': self.heartbeat_interval
            },
            'video': {
                'fps': self.video_fps,
                'width': self.video_frame_width,
                'height': self.video_frame_height,
                'quality': self.video_quality,
                'emotion_cache_duration': self.emotion_cache_duration
            },
            'audio': {
                'sample_rate': self.audio_sample_rate,
                'chunk_duration': self.audio_chunk_duration,
                'format': self.audio_format,
                'cache_duration': self.audio_cache_duration
            },
            'mediapipe': {
                'confidence': self.mediapipe_confidence,
                'max_faces': self.mediapipe_max_faces,
                'refine_landmarks': self.mediapipe_refine_landmarks
            },
            'deepface': {
                'backend': self.deepface_backend,
                'model': self.deepface_model,
                'detector': self.deepface_detector,
                'enforce_detection': self.deepface_enforce_detection
            },
            'redis': {
                'host': self.redis_host,
                'port': self.redis_port,
                'db': self.redis_db,
                'password': self.redis_password,
                'ssl': self.redis_ssl,
                'ttl': self.redis_analysis_ttl
            },
            'performance': {
                'max_workers': self.max_workers,
                'queue_size': self.processing_queue_size,
                'memory_limit_mb': self.memory_limit_mb,
                'cpu_limit_percent': self.cpu_limit_percent
            },
            'security': {
                'rate_limiting': self.enable_rate_limiting,
                'max_requests_per_minute': self.max_requests_per_minute,
                'max_frame_size_mb': self.max_frame_size_mb,
                'max_audio_size_mb': self.max_audio_size_mb
            },
            'features': {
                'video_analysis': self.enable_video_analysis,
                'audio_analysis': self.enable_audio_analysis,
                'emotion_detection': self.enable_emotion_detection,
                'gaze_tracking': self.enable_gaze_tracking,
                'head_pose_estimation': self.enable_head_pose_estimation,
                'speech_emotion_analysis': self.enable_speech_emotion_analysis
            }
        }
    
    def validate(self) -> bool:
        """验证配置有效性"""
        try:
            # 验证基本数值范围
            assert 1 <= self.video_fps <= 30, "video_fps must be between 1 and 30"
            assert 240 <= self.video_frame_width <= 1920, "video_frame_width must be between 240 and 1920"
            assert 180 <= self.video_frame_height <= 1080, "video_frame_height must be between 180 and 1080"
            assert 0.1 <= self.video_quality <= 1.0, "video_quality must be between 0.1 and 1.0"
            
            assert 8000 <= self.audio_sample_rate <= 48000, "audio_sample_rate must be between 8000 and 48000"
            assert 1000 <= self.audio_chunk_duration <= 10000, "audio_chunk_duration must be between 1000 and 10000"
            
            assert 0.1 <= self.mediapipe_confidence <= 1.0, "mediapipe_confidence must be between 0.1 and 1.0"
            
            assert 1 <= self.max_connections <= 1000, "max_connections must be between 1 and 1000"
            assert 1 <= self.max_workers <= 16, "max_workers must be between 1 and 16"
            assert 10 <= self.processing_queue_size <= 1000, "processing_queue_size must be between 10 and 1000"
            
            return True
        except AssertionError as e:
            raise ValueError(f"配置验证失败: {e}")


# 全局配置实例
realtime_config = RealtimeAnalysisConfig.from_env()

# 验证配置
try:
    realtime_config.validate()
    print("✅ 实时分析配置验证通过")
except ValueError as e:
    print(f"❌ 实时分析配置验证失败: {e}")
    # 使用默认配置
    realtime_config = RealtimeAnalysisConfig()


# 导出
__all__ = ['RealtimeAnalysisConfig', 'realtime_config'] 