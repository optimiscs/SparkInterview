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

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    logging.warning("DeepFace not available, using fallback emotion analysis")

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
        
        try:
            if frame is None or frame.size == 0:
                return self._get_default_result()
            
            # 转换颜色空间
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            
            # MediaPipe面部检测
            results = self.face_mesh.process(rgb_frame)
            
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'processing_time': 0,
                'face_detected': False,
                'head_pose_stability': 0.7,
                'gaze_direction': {'x': 0, 'y': 0},
                'dominant_emotion': 'neutral',
                'emotion_confidence': 0.7,
                'emotion_stability': 0.8,
                'eye_contact_ratio': 0.7
            }
            
            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0]
                analysis_result['face_detected'] = True
                
                # 头部姿态分析（轻量级）
                head_pose = self._analyze_head_pose_light(face_landmarks, (w, h))
                if head_pose:
                    analysis_result.update(head_pose)
                
                # 视线方向分析（简化版）
                gaze = self._analyze_gaze_light(face_landmarks, (w, h))
                if gaze:
                    analysis_result['gaze_direction'] = gaze
                
                # 情绪分析（带缓存）
                emotion = self._analyze_emotion_cached(frame)
                if emotion:
                    analysis_result.update(emotion)
            
            # 记录处理时间
            processing_time = time.time() - start_time
            analysis_result['processing_time'] = round(processing_time * 1000, 2)  # 毫秒
            
            logger.debug(f"🎥 视频帧分析完成，耗时: {processing_time:.3f}s")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 视频帧分析失败: {e}")
            return self._get_default_result()
    
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
            logger.debug(f"头部姿态分析失败: {e}")
            return {'head_pose_stability': 0.7}
    
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
            logger.debug(f"视线分析失败: {e}")
            return {'x': 0, 'y': 0}
    
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
            return self._get_fallback_emotion()
        
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
            dominant_emotion = max(emotions.items(), key=lambda x: x[1])
            
            return {
                'dominant_emotion': dominant_emotion[0],
                'emotion_confidence': round(dominant_emotion[1] / 100, 3),
                'emotion_distribution': {k: round(v/100, 3) for k, v in emotions.items()}
            }
            
        except Exception as e:
            logger.debug(f"情绪分析失败: {e}")
            return self._get_fallback_emotion()
    
    def _get_fallback_emotion(self) -> Dict[str, Any]:
        """备用情绪结果"""
        return {
            'dominant_emotion': 'neutral',
            'emotion_confidence': 0.7,
            'emotion_distribution': {
                'neutral': 0.7,
                'happy': 0.1,
                'focused': 0.1,
                'surprised': 0.05,
                'sad': 0.05
            }
        }
    
    def _get_default_result(self) -> Dict[str, Any]:
        """默认分析结果"""
        return {
            'timestamp': datetime.now().isoformat(),
            'processing_time': 0,
            'face_detected': False,
            'head_pose_stability': 0.7,
            'gaze_direction': {'x': 0, 'y': 0},
            'dominant_emotion': 'neutral',
            'emotion_confidence': 0.7,
            'emotion_stability': 0.8,
            'eye_contact_ratio': 0.7,
            'error': True
        }


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
        
        try:
            # 将音频字节转换为numpy array
            audio_data = self._bytes_to_audio(audio_bytes)
            
            if audio_data is None or len(audio_data) == 0:
                return self._get_default_audio_result()
            
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'processing_time': 0,
                'audio_detected': True,
                'speech_rate': 120,
                'pitch_mean': 150,
                'pitch_variance': 20,
                'volume_mean': 0.5,
                'clarity_score': 0.8,
                'emotion': 'calm',
                'emotion_confidence': 0.7
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
            return self._get_default_audio_result()
    
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
            logger.debug(f"音频转换失败: {e}")
            return None
    
    def _analyze_audio_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """分析基础音频特征"""
        try:
            # 语速估算（基于零交叉率）
            zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
            speech_rate = np.mean(zcr) * 1000  # 转换为BPM估算
            
            # 音高分析（简化版）
            pitches, magnitudes = librosa.piptrack(y=audio_data, sr=self.sample_rate)
            pitch_values = pitches[magnitudes > np.max(magnitudes) * 0.1]
            
            if len(pitch_values) > 0:
                pitch_mean = np.mean(pitch_values[pitch_values > 0])
                pitch_variance = np.var(pitch_values[pitch_values > 0])
            else:
                pitch_mean = 150
                pitch_variance = 20
            
            # 音量分析
            rms = librosa.feature.rms(y=audio_data)[0]
            volume_mean = np.mean(rms)
            
            # 清晰度评估（基于频谱重心）
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=self.sample_rate)[0]
            clarity_score = min(1.0, np.mean(spectral_centroids) / 2000)
            
            return {
                'speech_rate': round(speech_rate, 1),
                'pitch_mean': round(pitch_mean, 1),
                'pitch_variance': round(pitch_variance, 1),
                'volume_mean': round(volume_mean, 3),
                'clarity_score': round(clarity_score, 3)
            }
            
        except Exception as e:
            logger.debug(f"音频特征分析失败: {e}")
            return {
                'speech_rate': 120,
                'pitch_mean': 150,
                'pitch_variance': 20,
                'volume_mean': 0.5,
                'clarity_score': 0.8
            }
    
    def _analyze_audio_emotion(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """音频情感分析（简化版）"""
        try:
            # 基于音频特征的简单情感判断
            rms = librosa.feature.rms(y=audio_data)[0]
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
            logger.debug(f"音频情感分析失败: {e}")
            return {
                'emotion': 'calm',
                'emotion_confidence': 0.7
            }
    
    def _get_default_audio_result(self) -> Dict[str, Any]:
        """默认音频分析结果"""
        return {
            'timestamp': datetime.now().isoformat(),
            'processing_time': 0,
            'audio_detected': False,
            'speech_rate': 120,
            'pitch_mean': 150,
            'pitch_variance': 20,
            'volume_mean': 0.5,
            'clarity_score': 0.8,
            'emotion': 'calm',
            'emotion_confidence': 0.7,
            'error': True
        }


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
            'start_time': time.time()
        }
        
        logger.info("✅ 实时多模态处理器初始化完成")
    
    def analyze_video_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """分析视频帧"""
        start_time = time.time()
        
        result = self.video_analyzer.analyze_frame(frame)
        
        # 更新性能统计
        processing_time = time.time() - start_time
        self.performance_stats['video_analysis_count'] += 1
        count = self.performance_stats['video_analysis_count']
        self.performance_stats['avg_video_time'] = (
            (self.performance_stats['avg_video_time'] * (count - 1) + processing_time) / count
        )
        
        return result
    
    def analyze_audio_chunk(self, audio_bytes: bytes) -> Dict[str, Any]:
        """分析音频片段"""
        start_time = time.time()
        
        result = self.audio_analyzer.analyze_chunk(audio_bytes)
        
        # 更新性能统计
        processing_time = time.time() - start_time
        self.performance_stats['audio_analysis_count'] += 1
        count = self.performance_stats['audio_analysis_count']
        self.performance_stats['avg_audio_time'] = (
            (self.performance_stats['avg_audio_time'] * (count - 1) + processing_time) / count
        )
        
        return result
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        runtime = time.time() - self.performance_stats['start_time']
        
        return {
            'runtime_seconds': round(runtime, 2),
            'video_analyses': self.performance_stats['video_analysis_count'],
            'audio_analyses': self.performance_stats['audio_analysis_count'],
            'avg_video_processing_ms': round(self.performance_stats['avg_video_time'] * 1000, 2),
            'avg_audio_processing_ms': round(self.performance_stats['avg_audio_time'] * 1000, 2),
            'video_fps': round(self.performance_stats['video_analysis_count'] / runtime, 2) if runtime > 0 else 0,
            'audio_chunks_per_second': round(self.performance_stats['audio_analysis_count'] / runtime, 2) if runtime > 0 else 0
        }
    
    def reset_stats(self):
        """重置性能统计"""
        self.performance_stats = {
            'video_analysis_count': 0,
            'audio_analysis_count': 0,
            'avg_video_time': 0,
            'avg_audio_time': 0,
            'start_time': time.time()
        }
        logger.info("📊 性能统计已重置")


# 创建全局实例
def create_realtime_processor() -> RealtimeMultimodalProcessor:
    """创建实时多模态处理器实例"""
    return RealtimeMultimodalProcessor()


# 导出
__all__ = ['RealtimeMultimodalProcessor', 'create_realtime_processor'] 