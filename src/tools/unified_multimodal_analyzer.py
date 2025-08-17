"""
统一多模态分析器
整合视频、音频分析功能，充分利用DeepFace性能，优先保证检测准确率
"""
import cv2
import numpy as np
import librosa
import mediapipe as mp
from typing import Dict, Any, List, Optional, Tuple
import logging
from pathlib import Path
import sys
import traceback
from datetime import datetime
import time
import json
import io
import tempfile
from concurrent.futures import ThreadPoolExecutor
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DeepFace初始化
DEEPFACE_AVAILABLE = False
DEEPFACE_ERROR = None
DeepFace = None

def initialize_deepface():
    """初始化DeepFace，优先保证性能"""
    global DEEPFACE_AVAILABLE, DEEPFACE_ERROR, DeepFace
    
    try:
        logger.info("🔍 初始化DeepFace (高性能模式)...")
        from deepface import DeepFace
        
        # 使用高质量的检测器和识别模型
        test_image = np.zeros((224, 224, 3), dtype=np.uint8)
        test_image[50:174, 50:174] = [128, 128, 128]  # 灰色方块
        
        # 测试多种分析功能确保完整性
        result = DeepFace.analyze(
            test_image,
            actions=['emotion', 'age', 'gender'],
            detector_backend='retinaface',  # 使用最准确的检测器
            enforce_detection=False,
            silent=True
        )
        
        DEEPFACE_AVAILABLE = True
        logger.info("✅ DeepFace初始化成功 (高性能模式)")
        logger.info(f"   支持的分析功能: emotion, age, gender")
        logger.info(f"   检测器: retinaface (高精度)")
        return True
        
    except ImportError as e:
        DEEPFACE_ERROR = f"DeepFace未安装: {str(e)}"
        logger.error(f"❌ {DEEPFACE_ERROR}")
        return False
    except Exception as e:
        # 降级到opencv检测器
        try:
            result = DeepFace.analyze(
                test_image,
                actions=['emotion'],
                detector_backend='opencv',
                enforce_detection=False,
                silent=True
            )
            DEEPFACE_AVAILABLE = True
            logger.warning("⚠️ DeepFace降级到opencv检测器")
            return True
        except:
            DEEPFACE_ERROR = f"DeepFace初始化失败: {str(e)}"
            logger.error(f"❌ {DEEPFACE_ERROR}")
            return False

# 初始化DeepFace
initialize_deepface()

try:
    from ..config.settings import model_config
except ImportError:
    logger.warning("⚠️ 使用默认配置")
    class DefaultConfig:
        MEDIAPIPE_CONFIDENCE = 0.7  # 提高置信度阈值保证准确率
        DEEPFACE_BACKEND = 'retinaface'  # 使用高精度检测器
        AUDIO_SAMPLE_RATE = 22050
        ENABLE_FACE_LANDMARKS_REFINEMENT = True  # 启用精细化
    model_config = DefaultConfig()


class UnifiedVideoAnalyzer:
    """统一视频分析器 - 高精度模式"""
    
    def __init__(self):
        # 高精度MediaPipe配置
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,  # 启用精细化提高准确率
            min_detection_confidence=model_config.MEDIAPIPE_CONFIDENCE,
            min_tracking_confidence=model_config.MEDIAPIPE_CONFIDENCE
        )
        
        # 完整的面部关键点索引
        self.face_landmarks_indexes = {
            'nose_tip': 1,
            'chin': 175,
            'left_eye_corner': 33,
            'right_eye_corner': 263,
            'left_iris': 468,
            'right_iris': 473,
            'mouth_left': 61,
            'mouth_right': 291,
            'forehead': 10,
            'left_cheek': 116,
            'right_cheek': 345
        }
        
        # 3D面部模型点 (用于精确的PnP算法)
        self.model_points = np.array([
            (0.0, 0.0, 0.0),          # 鼻尖
            (0.0, -330.0, -65.0),     # 下巴
            (-225.0, 170.0, -135.0),  # 左眼角
            (225.0, 170.0, -135.0),   # 右眼角
            (-150.0, -150.0, -125.0), # 左嘴角
            (150.0, -150.0, -125.0)   # 右嘴角
        ], dtype=np.float64)
        
        # 情绪分析缓存 (适度缓存保证准确率)
        self.emotion_cache = {}
        self.emotion_cache_duration = 1.0  # 减少缓存时间提高实时性
        
        # 帧保存配置
        self.save_dir = Path("data/analysis_frames")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 性能统计
        self.stats = {
            'frames_analyzed': 0,
            'emotions_detected': 0,
            'head_poses_calculated': 0,
            'processing_times': [],
            'error_count': 0
        }
        
        logger.info("✅ 统一视频分析器初始化完成 (高精度模式)")
    
    def analyze_frame(self, frame: np.ndarray, save_frame: bool = False, 
                     frame_count: int = 0, timestamp: float = 0.0) -> Dict[str, Any]:
        """分析单帧视频 - 高精度模式"""
        start_time = time.time()
        self.stats['frames_analyzed'] += 1
        
        if frame is None or frame.size == 0:
            raise ValueError("输入视频帧为空或无效")
        
        try:
            # 高质量颜色空间转换
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            
            # MediaPipe面部检测
            results = self.face_mesh.process(rgb_frame)
            
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'processing_time': 0,
                'face_detected': False,
                'frame_size': {'width': w, 'height': h},
                'analysis_mode': 'high_precision'
            }
            
            if not results.multi_face_landmarks:
                logger.debug("未检测到人脸")
                analysis_result['error'] = "no_face_detected"
                return analysis_result
            
            face_landmarks = results.multi_face_landmarks[0]
            analysis_result['face_detected'] = True
            
            # 高精度头部姿态分析
            head_pose = self._analyze_head_pose_precise(face_landmarks, (w, h))
            if head_pose:
                analysis_result.update(head_pose)
                self.stats['head_poses_calculated'] += 1
            
            # 精确视线方向分析
            gaze = self._analyze_gaze_precise(face_landmarks, (w, h))
            analysis_result['gaze_direction'] = gaze
            
            # 高质量情绪分析
            emotion = self._analyze_emotion_enhanced(frame)
            if emotion:
                analysis_result.update(emotion)
                self.stats['emotions_detected'] += 1
            
            # 面部表情特征分析
            facial_features = self._analyze_facial_features(face_landmarks, (w, h))
            analysis_result['facial_features'] = facial_features
            
            # 保存关键帧
            if save_frame:
                saved_path = self._save_analysis_frame(
                    frame, frame_count, timestamp, analysis_result
                )
                analysis_result['saved_frame_path'] = saved_path
            
            # 记录处理时间
            processing_time = time.time() - start_time
            analysis_result['processing_time'] = round(processing_time * 1000, 2)
            self.stats['processing_times'].append(processing_time)
            
            logger.debug(f"🎥 高精度帧分析完成: {processing_time:.3f}s")
            return analysis_result
            
        except Exception as e:
            self.stats['error_count'] += 1
            logger.error(f"❌ 帧分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_head_pose_precise(self, landmarks, frame_shape) -> Dict[str, float]:
        """精确头部姿态分析"""
        try:
            w, h = frame_shape
            
            # 提取高精度关键点
            landmark_points = []
            key_indices = [1, 175, 33, 263, 61, 291]  # 鼻尖、下巴、眼角、嘴角
            
            for idx in key_indices:
                if idx < len(landmarks.landmark):
                    lm = landmarks.landmark[idx]
                    landmark_points.append([lm.x * w, lm.y * h])
            
            if len(landmark_points) < 6:
                raise Exception("关键点数量不足")
            
            image_points = np.array(landmark_points, dtype=np.float64)
            
            # 精确相机参数
            focal_length = max(w, h)  # 更准确的焦距估算
            center = (w/2, h/2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)
            
            # 考虑镜头畸变
            dist_coeffs = np.array([0.1, -0.2, 0, 0, 0], dtype=np.float64)
            
            # 高精度PnP算法
            success, rotation_vector, translation_vector = cv2.solvePnP(
                self.model_points, image_points, camera_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE  # 使用迭代算法提高精度
            )
            
            if not success:
                raise Exception("PnP算法求解失败")
            
            # 转换为欧拉角
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            angles = self._rotation_matrix_to_euler(rotation_matrix)
            
            # 计算头部稳定性
            stability = self._calculate_head_stability(angles)
            
            return {
                'pitch': float(angles[0]),
                'yaw': float(angles[1]),
                'roll': float(angles[2]),
                'head_pose_stability': stability,
                'rotation_magnitude': float(np.linalg.norm(angles))
            }
            
        except Exception as e:
            logger.error(f"❌ 精确头部姿态分析失败: {e}")
            raise
    
    def _analyze_gaze_precise(self, landmarks, frame_shape) -> Dict[str, float]:
        """精确视线方向分析"""
        try:
            w, h = frame_shape
            
            # 获取虹膜和眼部关键点
            if len(landmarks.landmark) > 473:  # 确保有虹膜数据
                left_iris = landmarks.landmark[468]
                right_iris = landmarks.landmark[473]
                left_eye_corner = landmarks.landmark[33]
                right_eye_corner = landmarks.landmark[263]
                
                # 计算精确视线向量
                left_gaze_x = (left_iris.x - left_eye_corner.x) * w
                left_gaze_y = (left_iris.y - left_eye_corner.y) * h
                right_gaze_x = (right_iris.x - right_eye_corner.x) * w
                right_gaze_y = (right_iris.y - right_eye_corner.y) * h
                
                # 双眼平均
                avg_gaze_x = (left_gaze_x + right_gaze_x) / 2
                avg_gaze_y = (left_gaze_y + right_gaze_y) / 2
                
                # 计算视线稳定性
                gaze_magnitude = np.sqrt(avg_gaze_x**2 + avg_gaze_y**2)
                eye_contact_score = max(0.0, 1.0 - gaze_magnitude / 50.0)
                
                return {
                    'x': float(avg_gaze_x),
                    'y': float(avg_gaze_y),
                    'magnitude': float(gaze_magnitude),
                    'eye_contact_score': float(eye_contact_score)
                }
            else:
                # 降级到基础眼部分析
                return self._analyze_gaze_basic(landmarks, frame_shape)
                
        except Exception as e:
            logger.error(f"❌ 精确视线分析失败: {e}")
            return self._analyze_gaze_basic(landmarks, frame_shape)
    
    def _analyze_gaze_basic(self, landmarks, frame_shape) -> Dict[str, float]:
        """基础视线分析（降级方案）"""
        w, h = frame_shape
        left_eye = landmarks.landmark[33]
        right_eye = landmarks.landmark[263]
        nose = landmarks.landmark[1]
        
        eye_center_x = (left_eye.x + right_eye.x) / 2
        eye_center_y = (left_eye.y + right_eye.y) / 2
        
        gaze_x = (eye_center_x - nose.x) * 100
        gaze_y = (eye_center_y - nose.y) * 100
        
        return {
            'x': float(gaze_x),
            'y': float(gaze_y),
            'magnitude': float(np.sqrt(gaze_x**2 + gaze_y**2)),
            'eye_contact_score': 0.5  # 默认值
        }
    
    def _analyze_emotion_enhanced(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """增强情绪分析"""
        if not DEEPFACE_AVAILABLE:
            logger.error("DeepFace不可用")
            return None
        
        current_time = time.time()
        
        # 检查缓存
        if 'last_analysis' in self.emotion_cache:
            if current_time - self.emotion_cache['last_analysis'] < self.emotion_cache_duration:
                return self.emotion_cache.get('result')
        
        try:
            # 使用原始分辨率保证准确率
            # 如果图像太大则适度缩放
            h, w = frame.shape[:2]
            if w > 640:
                scale = 640 / w
                new_w = int(w * scale)
                new_h = int(h * scale)
                resized_frame = cv2.resize(frame, (new_w, new_h))
            else:
                resized_frame = frame
            
            # 使用高精度检测器
            result = DeepFace.analyze(
                resized_frame,
                actions=['emotion', 'age', 'gender'],  # 多维度分析
                detector_backend=model_config.DEEPFACE_BACKEND,
                enforce_detection=False,
                silent=True
            )
            
            if isinstance(result, list):
                result = result[0]
            
            emotions = result.get('emotion', {})
            age = result.get('age', 0)
            gender = result.get('gender', {})
            
            if not emotions:
                raise Exception("DeepFace返回空结果")
            
            # 找出主导情绪
            dominant_emotion = max(emotions.items(), key=lambda x: x[1])
            
            # 计算情绪稳定性
            emotion_variance = np.var(list(emotions.values()))
            emotion_stability = 1.0 / (1.0 + emotion_variance / 1000)
            
            emotion_result = {
                'dominant_emotion': dominant_emotion[0],
                'emotion_confidence': float(dominant_emotion[1] / 100),
                'emotion_distribution': {k: float(v/100) for k, v in emotions.items()},
                'emotion_stability': float(emotion_stability),
                'estimated_age': float(age),
                'gender_prediction': gender
            }
            
            # 更新缓存
            self.emotion_cache = {
                'last_analysis': current_time,
                'result': emotion_result
            }
            
            logger.debug(f"✅ 增强情绪分析: {dominant_emotion[0]} ({dominant_emotion[1]:.1f}%)")
            return emotion_result
            
        except Exception as e:
            logger.error(f"❌ 增强情绪分析失败: {e}")
            return None
    
    def _analyze_facial_features(self, landmarks, frame_shape) -> Dict[str, float]:
        """分析面部特征"""
        try:
            w, h = frame_shape
            
            # 计算面部几何特征
            nose = landmarks.landmark[1]
            left_eye = landmarks.landmark[33]
            right_eye = landmarks.landmark[263]
            mouth_left = landmarks.landmark[61]
            mouth_right = landmarks.landmark[291]
            
            # 眼部开合度
            eye_distance = abs(left_eye.y - right_eye.y) * h
            eye_width = abs(left_eye.x - right_eye.x) * w
            eye_aspect_ratio = eye_distance / max(eye_width, 1)
            
            # 嘴部开合度
            mouth_width = abs(mouth_left.x - mouth_right.x) * w
            mouth_height = abs(mouth_left.y - mouth_right.y) * h
            mouth_aspect_ratio = mouth_height / max(mouth_width, 1)
            
            # 面部对称性
            face_center_x = nose.x * w
            left_distance = abs(face_center_x - left_eye.x * w)
            right_distance = abs(right_eye.x * w - face_center_x)
            symmetry_score = 1.0 - abs(left_distance - right_distance) / max(left_distance + right_distance, 1)
            
            return {
                'eye_aspect_ratio': float(eye_aspect_ratio),
                'mouth_aspect_ratio': float(mouth_aspect_ratio),
                'facial_symmetry': float(symmetry_score),
                'alertness_score': float(min(1.0, eye_aspect_ratio * 2))
            }
            
        except Exception as e:
            logger.error(f"❌ 面部特征分析失败: {e}")
            return {
                'eye_aspect_ratio': 0.0,
                'mouth_aspect_ratio': 0.0,
                'facial_symmetry': 0.5,
                'alertness_score': 0.5
            }
    
    def _rotation_matrix_to_euler(self, rotation_matrix) -> np.ndarray:
        """旋转矩阵转欧拉角"""
        sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
        singular = sy < 1e-6
        
        if not singular:
            x = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2])
            y = np.arctan2(-rotation_matrix[2,0], sy)
            z = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0])
        else:
            x = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1])
            y = np.arctan2(-rotation_matrix[2,0], sy)
            z = 0
        
        return np.degrees([x, y, z])
    
    def _calculate_head_stability(self, angles: np.ndarray) -> float:
        """计算头部稳定性"""
        angle_magnitude = np.linalg.norm(angles)
        return float(max(0.0, 1.0 - angle_magnitude / 45.0))  # 45度为不稳定阈值
    
    def _save_analysis_frame(self, frame: np.ndarray, frame_count: int, 
                           timestamp: float, analysis_result: Dict[str, Any]) -> str:
        """保存分析帧"""
        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"{timestamp_str}_frame_{frame_count:06d}_enhanced.jpg"
            filepath = self.save_dir / filename
            
            # 在图像上绘制详细分析信息
            annotated_frame = frame.copy()
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            color = (0, 255, 0)  # 绿色
            thickness = 1
            
            y_offset = 20
            # 基本信息
            cv2.putText(annotated_frame, f"Frame: {frame_count}", (10, y_offset), 
                       font, font_scale, color, thickness)
            y_offset += 20
            
            # 情绪信息
            if 'dominant_emotion' in analysis_result:
                emotion = analysis_result['dominant_emotion']
                confidence = analysis_result.get('emotion_confidence', 0)
                cv2.putText(annotated_frame, f"Emotion: {emotion} ({confidence:.2f})", 
                           (10, y_offset), font, font_scale, color, thickness)
                y_offset += 20
            
            # 头部姿态
            if 'pitch' in analysis_result:
                pitch = analysis_result['pitch']
                yaw = analysis_result['yaw']
                roll = analysis_result['roll']
                cv2.putText(annotated_frame, f"Pose: P{pitch:.1f} Y{yaw:.1f} R{roll:.1f}", 
                           (10, y_offset), font, font_scale, color, thickness)
            
            cv2.imwrite(str(filepath), annotated_frame)
            
            # 保存JSON数据
            json_filepath = filepath.with_suffix('.json')
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'frame_count': frame_count,
                    'timestamp': timestamp,
                    'analysis_result': analysis_result,
                    'saved_at': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ 保存分析帧失败: {e}")
            return ""
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        if self.stats['processing_times']:
            avg_time = np.mean(self.stats['processing_times'])
            fps = 1.0 / avg_time if avg_time > 0 else 0
        else:
            avg_time = 0
            fps = 0
        
        return {
            'frames_analyzed': self.stats['frames_analyzed'],
            'emotions_detected': self.stats['emotions_detected'],
            'head_poses_calculated': self.stats['head_poses_calculated'],
            'error_count': self.stats['error_count'],
            'average_processing_time_ms': round(avg_time * 1000, 2),
            'estimated_fps': round(fps, 2),
            'emotion_detection_rate': (self.stats['emotions_detected'] / 
                                     max(self.stats['frames_analyzed'], 1)),
            'error_rate': (self.stats['error_count'] / 
                          max(self.stats['frames_analyzed'], 1))
        }


class UnifiedAudioAnalyzer:
    """统一音频分析器 - 高精度模式"""
    
    def __init__(self):
        self.sample_rate = model_config.AUDIO_SAMPLE_RATE  # 使用高采样率
        self.analysis_cache = {}
        self.cache_duration = 0.5  # 减少缓存时间
        
        # 性能统计
        self.stats = {
            'chunks_analyzed': 0,
            'processing_times': [],
            'error_count': 0
        }
        
        logger.info("✅ 统一音频分析器初始化完成 (高精度模式)")
    
    def analyze_chunk(self, audio_bytes: bytes) -> Dict[str, Any]:
        """分析音频片段 - 高精度模式"""
        start_time = time.time()
        self.stats['chunks_analyzed'] += 1
        
        if not audio_bytes:
            raise ValueError("音频数据为空")
        
        try:
            # 高质量音频转换
            audio_data = self._bytes_to_audio_hq(audio_bytes)
            
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'processing_time': 0,
                'audio_detected': True,
                'analysis_mode': 'high_precision'
            }
            
            # 综合音频特征分析
            audio_features = self._analyze_audio_features_comprehensive(audio_data)
            analysis_result.update(audio_features)
            
            # 高级语音情感分析
            emotion_result = self._analyze_speech_emotion_advanced(audio_data)
            analysis_result.update(emotion_result)
            
            # 语音质量评估
            quality_metrics = self._assess_speech_quality(audio_data)
            analysis_result['speech_quality'] = quality_metrics
            
            processing_time = time.time() - start_time
            analysis_result['processing_time'] = round(processing_time * 1000, 2)
            self.stats['processing_times'].append(processing_time)
            
            logger.debug(f"🎵 高精度音频分析完成: {processing_time:.3f}s")
            return analysis_result
            
        except Exception as e:
            self.stats['error_count'] += 1
            logger.error(f"❌ 音频分析失败: {e}")
            raise
    
    def _bytes_to_audio_hq(self, audio_bytes: bytes) -> np.ndarray:
        """高质量音频转换"""
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_file.flush()
            
            # 使用高采样率加载
            y, sr = librosa.load(temp_file.name, sr=self.sample_rate, mono=True)
            
            # 音频预处理
            y = librosa.util.normalize(y)  # 标准化
            y = librosa.effects.trim(y, top_db=20)[0]  # 去除静音
            
            return y
    
    def _analyze_audio_features_comprehensive(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """综合音频特征分析"""
        try:
            # 基础特征
            # 语速分析
            tempo, beats = librosa.beat.beat_track(y=audio_data, sr=self.sample_rate)
            speech_rate = tempo * 0.6  # 转换为语音节奏
            
            # 高精度音高分析
            f0, voiced_flag, voiced_probs = librosa.pyin(
                audio_data, 
                fmin=librosa.note_to_hz('C2'), 
                fmax=librosa.note_to_hz('C7'),
                frame_length=2048
            )
            
            valid_f0 = f0[voiced_flag & (voiced_probs > 0.8)]  # 高置信度音高
            
            if len(valid_f0) > 0:
                pitch_mean = float(np.mean(valid_f0))
                pitch_std = float(np.std(valid_f0))
                pitch_range = float(np.max(valid_f0) - np.min(valid_f0))
            else:
                pitch_mean = pitch_std = pitch_range = 0.0
            
            # 音量分析
            rms = librosa.feature.rms(y=audio_data, frame_length=2048)[0]
            volume_mean = float(np.mean(librosa.amplitude_to_db(rms)))
            volume_variance = float(np.var(librosa.amplitude_to_db(rms)))
            
            # 频谱特征
            spectral_centroids = librosa.feature.spectral_centroid(
                y=audio_data, sr=self.sample_rate)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(
                y=audio_data, sr=self.sample_rate)[0]
            
            clarity_score = float(np.mean(spectral_centroids) / 4000)  # 标准化
            brightness = float(np.mean(spectral_rolloff) / 8000)  # 亮度指标
            
            # MFCC特征 (梅尔倒谱系数)
            mfccs = librosa.feature.mfcc(y=audio_data, sr=self.sample_rate, n_mfcc=13)
            mfcc_mean = np.mean(mfccs, axis=1)
            
            return {
                'speech_rate_bpm': float(speech_rate),
                'pitch_mean_hz': pitch_mean,
                'pitch_std_hz': pitch_std,
                'pitch_range_hz': pitch_range,
                'volume_mean_db': volume_mean,
                'volume_variance': volume_variance,
                'clarity_score': min(1.0, clarity_score),
                'brightness_score': min(1.0, brightness),
                'voiced_ratio': float(np.sum(voiced_flag) / len(voiced_flag)),
                'mfcc_features': mfcc_mean.tolist()[:5]  # 前5个MFCC系数
            }
            
        except Exception as e:
            logger.error(f"❌ 综合音频特征分析失败: {e}")
            raise
    
    def _analyze_speech_emotion_advanced(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """高级语音情感分析"""
        try:
            # 基于多维特征的情感分析
            rms = librosa.feature.rms(y=audio_data)[0]
            zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=self.sample_rate)[0]
            
            # 特征统计
            energy = np.mean(rms)
            zcr_mean = np.mean(zcr)
            spectral_mean = np.mean(spectral_centroid)
            
            # 情感映射 (基于声学特征)
            if energy > 0.6 and spectral_mean > 2000:
                emotion = 'excited'
                confidence = 0.85
            elif energy > 0.4 and zcr_mean > 0.1:
                emotion = 'confident'
                confidence = 0.8
            elif energy < 0.2:
                emotion = 'nervous'
                confidence = 0.75
            elif spectral_mean < 1000:
                emotion = 'sad'
                confidence = 0.7
            else:
                emotion = 'neutral'
                confidence = 0.65
            
            # 情感稳定性评估
            energy_variance = np.var(rms)
            stability = 1.0 / (1.0 + energy_variance * 10)
            
            return {
                'speech_emotion': emotion,
                'emotion_confidence': confidence,
                'emotion_stability': float(stability),
                'vocal_energy': float(energy),
                'speech_variability': float(zcr_mean)
            }
            
        except Exception as e:
            logger.error(f"❌ 高级语音情感分析失败: {e}")
            return {
                'speech_emotion': 'unknown',
                'emotion_confidence': 0.0,
                'emotion_stability': 0.5,
                'vocal_energy': 0.0,
                'speech_variability': 0.0
            }
    
    def _assess_speech_quality(self, audio_data: np.ndarray) -> Dict[str, float]:
        """评估语音质量"""
        try:
            # 信噪比估算
            signal_power = np.mean(audio_data ** 2)
            noise_power = np.mean((audio_data - np.mean(audio_data)) ** 2) * 0.1
            snr = 10 * np.log10(signal_power / max(noise_power, 1e-10))
            
            # 清晰度评估
            high_freq_energy = np.mean(librosa.feature.spectral_centroid(
                y=audio_data, sr=self.sample_rate)[0])
            clarity = min(1.0, high_freq_energy / 3000)
            
            # 稳定性评估
            rms = librosa.feature.rms(y=audio_data)[0]
            stability = 1.0 - (np.std(rms) / max(np.mean(rms), 1e-10))
            
            return {
                'estimated_snr_db': float(max(0, min(40, snr))),
                'clarity_score': float(clarity),
                'volume_stability': float(max(0, stability))
            }
            
        except Exception as e:
            logger.error(f"❌ 语音质量评估失败: {e}")
            return {
                'estimated_snr_db': 0.0,
                'clarity_score': 0.5,
                'volume_stability': 0.5
            }


class UnifiedMultimodalProcessor:
    """统一多模态处理器 - 主控制器"""
    
    def __init__(self):
        self.video_analyzer = UnifiedVideoAnalyzer()
        self.audio_analyzer = UnifiedAudioAnalyzer()
        
        # 综合性能统计
        self.performance_stats = {
            'start_time': time.time(),
            'total_video_frames': 0,
            'total_audio_chunks': 0,
            'total_errors': 0,
            'avg_video_time': 0,
            'avg_audio_time': 0
        }
        
        logger.info("✅ 统一多模态处理器初始化完成 (高精度模式)")
    
    def analyze_video_frame(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """分析视频帧"""
        start_time = time.time()
        
        try:
            result = self.video_analyzer.analyze_frame(frame, **kwargs)
            
            # 更新性能统计
            processing_time = time.time() - start_time
            self.performance_stats['total_video_frames'] += 1
            count = self.performance_stats['total_video_frames']
            self.performance_stats['avg_video_time'] = (
                (self.performance_stats['avg_video_time'] * (count - 1) + processing_time) / count
            )
            
            return result
            
        except Exception as e:
            self.performance_stats['total_errors'] += 1
            logger.error(f"❌ 视频帧分析失败: {e}")
            raise
    
    def analyze_audio_chunk(self, audio_bytes: bytes) -> Dict[str, Any]:
        """分析音频片段"""
        start_time = time.time()
        
        try:
            result = self.audio_analyzer.analyze_chunk(audio_bytes)
            
            # 更新性能统计
            processing_time = time.time() - start_time
            self.performance_stats['total_audio_chunks'] += 1
            count = self.performance_stats['total_audio_chunks']
            self.performance_stats['avg_audio_time'] = (
                (self.performance_stats['avg_audio_time'] * (count - 1) + processing_time) / count
            )
            
            return result
            
        except Exception as e:
            self.performance_stats['total_errors'] += 1
            logger.error(f"❌ 音频片段分析失败: {e}")
            raise
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合性能统计"""
        runtime = time.time() - self.performance_stats['start_time']
        
        video_stats = self.video_analyzer.get_performance_stats()
        
        return {
            'runtime_seconds': round(runtime, 2),
            'video_analysis': video_stats,
            'audio_analysis': {
                'chunks_analyzed': self.performance_stats['total_audio_chunks'],
                'average_processing_time_ms': round(self.performance_stats['avg_audio_time'] * 1000, 2)
            },
            'overall_error_rate': (self.performance_stats['total_errors'] / 
                                 max(self.performance_stats['total_video_frames'] + 
                                     self.performance_stats['total_audio_chunks'], 1)),
            'deepface_status': 'available' if DEEPFACE_AVAILABLE else 'unavailable'
        }


# 全局实例
def create_unified_processor() -> UnifiedMultimodalProcessor:
    """创建统一多模态处理器实例"""
    return UnifiedMultimodalProcessor()


# 导出
__all__ = ['UnifiedMultimodalProcessor', 'create_unified_processor'] 