"""
实时多模态分析处理器
专为WebSocket实时传输优化的轻量级分析模块
"""
import cv2
import numpy as np
import mediapipe as mp
import librosa
import io
import tempfile
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import time
import traceback

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    logging.error("❌ DeepFace not available, emotion analysis will fail")

logger = logging.getLogger(__name__)


class RealtimeVideoAnalyzer:
    """实时视频分析器 - 优化版"""
    
    def __init__(self):
        # 初始化MediaPipe (轻量级配置)
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,  # 关闭精细化以提高速度
            min_detection_confidence=0.5,  # 降低阈值以提高速度
            min_tracking_confidence=0.5
        )
        
        # 面部关键点索引（简化版）
        self.key_landmarks = {
            'nose_tip': 1,
            'chin': 175,
            'left_eye': 33,
            'right_eye': 263,
            'mouth_center': 13
        }
        
        # 情绪分析配置
        self.emotion_cache = {}
        self.emotion_cache_duration = 2.0  # 缓存2秒
        
        logger.info("✅ 实时视频分析器初始化完成")
    
    def analyze_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """分析单帧视频"""
        start_time = time.time()
        
        if frame is None or frame.size == 0:
            error_msg = "输入视频帧为空或无效"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            # 转换颜色空间
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            
            # MediaPipe面部检测
            results = self.face_mesh.process(rgb_frame)
            
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'processing_time': 0,
                'face_detected': False
            }
            
            if not results.multi_face_landmarks:
                error_msg = "视频帧中未检测到人脸"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            face_landmarks = results.multi_face_landmarks[0]
            analysis_result['face_detected'] = True
            
            # 头部姿态分析（轻量级）
            head_pose = self._analyze_head_pose_light(face_landmarks, (w, h))
            analysis_result.update(head_pose)
            
            # 视线方向分析（简化版）
            gaze = self._analyze_gaze_light(face_landmarks, (w, h))
            analysis_result['gaze_direction'] = gaze
            
            # 情绪分析（带缓存）
            emotion = self._analyze_emotion_cached(frame)
            analysis_result.update(emotion)
            
            # 记录处理时间
            processing_time = time.time() - start_time
            analysis_result['processing_time'] = round(processing_time * 1000, 2)  # 毫秒
            
            logger.debug(f"🎥 视频帧分析完成，耗时: {processing_time:.3f}s")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 视频帧分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_head_pose_light(self, landmarks, frame_shape) -> Dict[str, float]:
        """轻量级头部姿态分析"""
        try:
            w, h = frame_shape
            
            # 获取关键点
            nose = landmarks.landmark[self.key_landmarks['nose_tip']]
            chin = landmarks.landmark[self.key_landmarks['chin']]
            left_eye = landmarks.landmark[self.key_landmarks['left_eye']]
            right_eye = landmarks.landmark[self.key_landmarks['right_eye']]
            
            # 转换为像素坐标
            nose_px = (nose.x * w, nose.y * h)
            chin_px = (chin.x * w, chin.y * h)
            left_eye_px = (left_eye.x * w, left_eye.y * h)
            right_eye_px = (right_eye.x * w, right_eye.y * h)
            
            # 计算头部倾斜角度（简化计算）
            eye_center_x = (left_eye_px[0] + right_eye_px[0]) / 2
            eye_center_y = (left_eye_px[1] + right_eye_px[1]) / 2
            
            # 头部垂直偏移
            face_center_x = (nose_px[0] + chin_px[0]) / 2
            horizontal_deviation = abs(face_center_x - w/2) / (w/2)
            
            # 头部稳定性评分
            stability = max(0.0, 1.0 - horizontal_deviation)
            
            return {
                'head_pose_stability': round(stability, 3),
                'horizontal_deviation': round(horizontal_deviation, 3)
            }
            
        except Exception as e:
            logger.error(f"❌ 头部姿态分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_gaze_light(self, landmarks, frame_shape) -> Dict[str, float]:
        """轻量级视线方向分析"""
        try:
            w, h = frame_shape
            
            # 获取眼部关键点
            left_eye = landmarks.landmark[self.key_landmarks['left_eye']]
            right_eye = landmarks.landmark[self.key_landmarks['right_eye']]
            nose = landmarks.landmark[self.key_landmarks['nose_tip']]
            
            # 计算眼部中心
            eye_center_x = (left_eye.x + right_eye.x) / 2
            eye_center_y = (left_eye.y + right_eye.y) / 2
            
            # 与鼻尖的相对位置
            gaze_x = eye_center_x - nose.x
            gaze_y = eye_center_y - nose.y
            
            return {
                'x': round(gaze_x * 100, 2),  # 标准化到-100到100
                'y': round(gaze_y * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ 视线分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_emotion_cached(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """带缓存的情绪分析"""
        current_time = time.time()
        
        # 检查缓存
        if 'last_analysis' in self.emotion_cache:
            last_time = self.emotion_cache['last_analysis']
            if current_time - last_time < self.emotion_cache_duration:
                return self.emotion_cache.get('result')
        
        # 执行新的情绪分析
        emotion_result = self._analyze_emotion_fast(frame)
        
        # 更新缓存
        self.emotion_cache = {
            'last_analysis': current_time,
            'result': emotion_result
        }
        
        return emotion_result
    
    def _analyze_emotion_fast(self, frame: np.ndarray) -> Dict[str, Any]:
        """快速情绪分析"""
        if not DEEPFACE_AVAILABLE:
            error_msg = "DeepFace不可用，无法进行情绪分析"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        try:
            # 缩小图片以提高速度
            small_frame = cv2.resize(frame, (224, 224))
            
            result = DeepFace.analyze(
                small_frame,
                actions=['emotion'],
                enforce_detection=False,
                detector_backend='opencv'  # 使用最快的检测器
            )
            
            if isinstance(result, list):
                result = result[0]
            
            emotions = result.get('emotion', {})
            
            if not emotions:
                error_msg = "DeepFace返回空的情绪结果"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            dominant_emotion = max(emotions.items(), key=lambda x: x[1])
            
            return {
                'dominant_emotion': dominant_emotion[0],
                'emotion_confidence': round(dominant_emotion[1] / 100, 3),
                'emotion_distribution': {k: round(v/100, 3) for k, v in emotions.items()}
            }
            
        except Exception as e:
            logger.error(f"❌ 情绪分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise


class RealtimeAudioAnalyzer:
    """实时音频分析器 - 优化版"""
    
    def __init__(self):
        self.sample_rate = 16000  # 降低采样率以提高速度
        self.analysis_cache = {}
        self.cache_duration = 1.0  # 缓存1秒
        
        logger.info("✅ 实时音频分析器初始化完成")
    
    def analyze_chunk(self, audio_bytes: bytes) -> Dict[str, Any]:
        """分析音频片段"""
        start_time = time.time()
        
        if not audio_bytes or len(audio_bytes) == 0:
            error_msg = "输入音频数据为空"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            # 将音频字节转换为numpy array
            audio_data = self._bytes_to_audio(audio_bytes)
            
            if audio_data is None or len(audio_data) == 0:
                error_msg = "音频数据转换失败或为空"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'processing_time': 0,
                'audio_detected': True
            }
            
            # 基础音频特征分析
            audio_features = self._analyze_audio_features(audio_data)
            analysis_result.update(audio_features)
            
            # 语音情感分析（简化版）
            emotion_result = self._analyze_audio_emotion(audio_data)
            analysis_result.update(emotion_result)
            
            # 记录处理时间
            processing_time = time.time() - start_time
            analysis_result['processing_time'] = round(processing_time * 1000, 2)
            
            logger.debug(f"🎵 音频片段分析完成，耗时: {processing_time:.3f}s")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 音频分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _bytes_to_audio(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """将音频字节转换为numpy数组"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file.flush()
                
                # 使用librosa加载音频
                y, sr = librosa.load(temp_file.name, sr=self.sample_rate)
                return y
                
        except Exception as e:
            logger.error(f"❌ 音频转换失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_audio_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """分析基础音频特征"""
        try:
            # 语速估算（基于零交叉率）
            zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
            if len(zcr) == 0:
                error_msg = "零交叉率计算失败"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            speech_rate = np.mean(zcr) * 1000  # 转换为BPM估算
            
            # 音高分析（简化版）
            pitches, magnitudes = librosa.piptrack(y=audio_data, sr=self.sample_rate)
            pitch_values = pitches[magnitudes > np.max(magnitudes) * 0.1]
            
            if len(pitch_values) == 0:
                error_msg = "音高分析失败：未检测到有效音高"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
                
            valid_pitches = pitch_values[pitch_values > 0]
            if len(valid_pitches) == 0:
                error_msg = "音高分析失败：所有音高值无效"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
                
            pitch_mean = np.mean(valid_pitches)
            pitch_variance = np.var(valid_pitches)
            
            # 音量分析
            rms = librosa.feature.rms(y=audio_data)[0]
            if len(rms) == 0:
                error_msg = "音量分析失败：RMS计算结果为空"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            volume_mean = np.mean(rms)
            
            # 清晰度评估（基于频谱重心）
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=self.sample_rate)[0]
            if len(spectral_centroids) == 0:
                error_msg = "清晰度分析失败：频谱重心计算结果为空"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            clarity_score = min(1.0, np.mean(spectral_centroids) / 2000)
            
            return {
                'speech_rate': round(speech_rate, 1),
                'pitch_mean': round(pitch_mean, 1),
                'pitch_variance': round(pitch_variance, 1),
                'volume_mean': round(volume_mean, 3),
                'clarity_score': round(clarity_score, 3)
            }
            
        except Exception as e:
            logger.error(f"❌ 音频特征分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_audio_emotion(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """音频情感分析（简化版）"""
        try:
            # 基于音频特征的简单情感判断
            rms = librosa.feature.rms(y=audio_data)[0]
            if len(rms) == 0:
                error_msg = "情感分析失败：无法计算音量特征"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
                
            volume_level = np.mean(rms)
            
            # 基于音量和频率变化推断情感
            if volume_level > 0.7:
                emotion = 'excited'
                confidence = 0.8
            elif volume_level > 0.4:
                emotion = 'confident'
                confidence = 0.7
            elif volume_level > 0.2:
                emotion = 'calm'
                confidence = 0.8
            else:
                emotion = 'uncertain'
                confidence = 0.6
            
            return {
                'emotion': emotion,
                'emotion_confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"❌ 音频情感分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise


class RealtimeMultimodalProcessor:
    """实时多模态处理器 - 主控制器"""
    
    def __init__(self):
        self.video_analyzer = RealtimeVideoAnalyzer()
        self.audio_analyzer = RealtimeAudioAnalyzer()
        
        # 性能监控
        self.performance_stats = {
            'video_analysis_count': 0,
            'audio_analysis_count': 0,
            'avg_video_time': 0,
            'avg_audio_time': 0,
            'start_time': time.time(),
            'video_errors': 0,
            'audio_errors': 0
        }
        
        logger.info("✅ 实时多模态处理器初始化完成")
    
    def analyze_video_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """分析视频帧"""
        start_time = time.time()
        
        # 记录分析开始
        frame_info = f"帧大小: {frame.shape}" if frame is not None else "空帧"
        logger.debug(f"🎥 [分析器] 开始视频帧分析 ({frame_info})")
        
        try:
            result = self.video_analyzer.analyze_frame(frame)
            
            # 更新性能统计
            processing_time = time.time() - start_time
            self.performance_stats['video_analysis_count'] += 1
            count = self.performance_stats['video_analysis_count']
            self.performance_stats['avg_video_time'] = (
                (self.performance_stats['avg_video_time'] * (count - 1) + processing_time) / count
            )
            
            # 记录分析完成和详细信息
            logger.debug(f"✅ [分析器] 视频帧分析完成:")
            logger.debug(f"   - 处理时间: {processing_time*1000:.1f}ms")
            logger.debug(f"   - 累计分析: {count} 帧")
            logger.debug(f"   - 平均耗时: {self.performance_stats['avg_video_time']*1000:.1f}ms")
            logger.debug(f"   - 实时FPS: {1/processing_time:.1f}")
            
            return result
            
        except Exception as e:
            self.performance_stats['video_errors'] += 1
            logger.error(f"❌ [分析器] 视频帧分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def analyze_audio_chunk(self, audio_bytes: bytes) -> Dict[str, Any]:
        """分析音频片段"""
        start_time = time.time()
        
        # 记录分析开始
        audio_info = f"音频大小: {len(audio_bytes)} bytes" if audio_bytes else "空音频"
        logger.debug(f"🎵 [分析器] 开始音频片段分析 ({audio_info})")
        
        try:
            result = self.audio_analyzer.analyze_chunk(audio_bytes)
            
            # 更新性能统计
            processing_time = time.time() - start_time
            self.performance_stats['audio_analysis_count'] += 1
            count = self.performance_stats['audio_analysis_count']
            self.performance_stats['avg_audio_time'] = (
                (self.performance_stats['avg_audio_time'] * (count - 1) + processing_time) / count
            )
            
            # 记录分析完成和详细信息
            logger.debug(f"✅ [分析器] 音频片段分析完成:")
            logger.debug(f"   - 处理时间: {processing_time*1000:.1f}ms")
            logger.debug(f"   - 累计分析: {count} 个片段")
            logger.debug(f"   - 平均耗时: {self.performance_stats['avg_audio_time']*1000:.1f}ms")
            # 假设音频片段通常为3秒，计算实时比例
            real_time_ratio = 3000 / (processing_time * 1000) if processing_time > 0 else 0
            logger.debug(f"   - 实时比例: {real_time_ratio:.1f}x")
            
            return result
            
        except Exception as e:
            self.performance_stats['audio_errors'] += 1
            logger.error(f"❌ [分析器] 音频片段分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        runtime = time.time() - self.performance_stats['start_time']
        
        return {
            'runtime_seconds': round(runtime, 2),
            'video_analyses': self.performance_stats['video_analysis_count'],
            'audio_analyses': self.performance_stats['audio_analysis_count'],
            'video_errors': self.performance_stats['video_errors'],
            'audio_errors': self.performance_stats['audio_errors'],
            'avg_video_processing_ms': round(self.performance_stats['avg_video_time'] * 1000, 2),
            'avg_audio_processing_ms': round(self.performance_stats['avg_audio_time'] * 1000, 2),
            'video_fps': round(self.performance_stats['video_analysis_count'] / runtime, 2) if runtime > 0 else 0,
            'audio_chunks_per_second': round(self.performance_stats['audio_analysis_count'] / runtime, 2) if runtime > 0 else 0,
            'video_error_rate': round(self.performance_stats['video_errors'] / max(1, self.performance_stats['video_analysis_count']), 3),
            'audio_error_rate': round(self.performance_stats['audio_errors'] / max(1, self.performance_stats['audio_analysis_count']), 3)
        }
    
    def print_performance_summary(self):
        """打印性能摘要"""
        stats = self.get_performance_stats()
        
        logger.info("📊 === 实时多模态分析性能摘要 ===")
        logger.info(f"   🕐 运行时间: {stats['runtime_seconds']} 秒")
        logger.info(f"   🎥 视频分析: {stats['video_analyses']} 帧 | 平均: {stats['avg_video_processing_ms']}ms | FPS: {stats['video_fps']} | 错误率: {stats['video_error_rate']*100:.1f}%")
        logger.info(f"   🎵 音频分析: {stats['audio_analyses']} 片段 | 平均: {stats['avg_audio_processing_ms']}ms | 片段/秒: {stats['audio_chunks_per_second']} | 错误率: {stats['audio_error_rate']*100:.1f}%")
        
        # 性能评估
        if stats['avg_video_processing_ms'] < 100 and stats['video_error_rate'] < 0.1:
            video_perf = "优秀"
        elif stats['avg_video_processing_ms'] < 200 and stats['video_error_rate'] < 0.2:
            video_perf = "良好"  
        else:
            video_perf = "需要优化"
            
        if stats['avg_audio_processing_ms'] < 500 and stats['audio_error_rate'] < 0.1:
            audio_perf = "优秀"
        elif stats['avg_audio_processing_ms'] < 1000 and stats['audio_error_rate'] < 0.2:
            audio_perf = "良好"
        else:
            audio_perf = "需要优化"
        
        logger.info(f"   💯 性能评估: 视频-{video_perf} | 音频-{audio_perf}")
        logger.info("="*50)
    
    def reset_stats(self):
        """重置性能统计"""
        self.performance_stats = {
            'video_analysis_count': 0,
            'audio_analysis_count': 0,
            'avg_video_time': 0,
            'avg_audio_time': 0,
            'start_time': time.time(),
            'video_errors': 0,
            'audio_errors': 0
        }
        logger.info("📊 性能统计已重置")


# 创建全局实例
def create_realtime_processor() -> RealtimeMultimodalProcessor:
    """创建实时多模态处理器实例"""
    return RealtimeMultimodalProcessor()


# 导出
__all__ = ['RealtimeMultimodalProcessor', 'create_realtime_processor'] 