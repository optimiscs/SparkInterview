"""
多模态分析工具
集成MediaPipe、DeepFace、Librosa等库进行真实的音视频分析
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

# 配置详细日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DeepFace可用性检查和初始化
DEEPFACE_AVAILABLE = False
DEEPFACE_ERROR = None

def check_deepface_availability():
    """检查DeepFace是否可用并进行初始化测试"""
    global DEEPFACE_AVAILABLE, DEEPFACE_ERROR
    
    try:
        logger.info("🔍 检查DeepFace可用性...")
        from deepface import DeepFace
        
        # 尝试初始化DeepFace进行简单测试
        logger.info("🧪 测试DeepFace功能...")
        
        # 创建一个测试图像
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[30:70, 30:70] = [255, 255, 255]  # 白色方块模拟人脸
        
        # 尝试分析测试图像
        result = DeepFace.analyze(
            test_image, 
            actions=['emotion'], 
            enforce_detection=False,
            silent=True
        )
        
        DEEPFACE_AVAILABLE = True
        logger.info("✅ DeepFace初始化成功，情感分析功能可用")
        return True
        
    except ImportError as e:
        DEEPFACE_ERROR = f"DeepFace未安装: {str(e)}"
        logger.error(f"❌ {DEEPFACE_ERROR}")
        logger.info("💡 请安装DeepFace: pip install deepface")
        return False
    except Exception as e:
        DEEPFACE_ERROR = f"DeepFace初始化失败: {str(e)}"
        logger.error(f"❌ {DEEPFACE_ERROR}")
        logger.error(f"🔧 错误详情: {traceback.format_exc()}")
        return False

# 启动时检查DeepFace
check_deepface_availability()

try:
    from ..config.settings import model_config
except ImportError:
    logger.warning("⚠️ 无法导入model_config，使用默认配置")
    # 默认配置
    class DefaultConfig:
        MEDIAPIPE_CONFIDENCE = 0.5
        DEEPFACE_BACKEND = 'opencv'
        AUDIO_SAMPLE_RATE = 22050
    model_config = DefaultConfig()


class VideoAnalyzer:
    """视频分析器 - 处理视觉模态"""
    
    def __init__(self):
        # 初始化MediaPipe
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=model_config.MEDIAPIPE_CONFIDENCE,
            min_tracking_confidence=model_config.MEDIAPIPE_CONFIDENCE
        )
        
        # 面部关键点索引 (468个关键点中的重要点)
        self.face_landmarks_indexes = {
            'nose_tip': 1,
            'chin': 175,
            'left_eye_corner': 33,
            'right_eye_corner': 263,
            'left_iris': 468,
            'right_iris': 473
        }
        
        # 3D面部模型点 (用于PnP算法)
        self.model_points = np.array([
            (0.0, 0.0, 0.0),      # 鼻尖
            (0.0, -330.0, -65.0), # 下巴
            (-225.0, 170.0, -135.0), # 左眼角
            (225.0, 170.0, -135.0),  # 右眼角
            (-150.0, -150.0, -125.0), # 左嘴角
            (150.0, -150.0, -125.0)   # 右嘴角
        ], dtype=np.float64)
    
    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """分析视频文件，提取视觉特征"""
        
        start_time = datetime.now()
        logger.info(f"🎥 开始视频分析: {video_path}")
        
        try:
            # 检查视频文件是否存在
            if not Path(video_path).exists():
                raise FileNotFoundError(f"视频文件不存在: {video_path}")
            
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise Exception(f"无法打开视频文件: {video_path}")
            
            # 获取视频基本信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"📊 视频信息: {total_frames}帧, {fps:.1f}FPS, {duration:.1f}秒")
            
            # 初始化分析结果存储
            head_poses = []
            gaze_directions = []
            emotions_timeline = []
            frame_count = 0
            processed_frames = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                try:
                    # 转换颜色空间
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # MediaPipe面部检测
                    results = self.face_mesh.process(rgb_frame)
                    
                    if results.multi_face_landmarks:
                        processed_frames += 1
                        face_landmarks = results.multi_face_landmarks[0]
                        
                        # 分析头部姿态
                        head_pose = self._analyze_head_pose(face_landmarks, frame.shape)
                        if head_pose:
                            head_poses.append(head_pose)
                        
                        # 分析视线方向
                        gaze = self._analyze_gaze_direction(face_landmarks, frame.shape)
                        if gaze:
                            gaze_directions.append(gaze)
                        
                        # 情绪分析 (每10帧分析一次以提高效率)
                        if frame_count % 10 == 0:
                            emotion = self._analyze_emotion(frame)
                            if emotion:
                                emotions_timeline.append({
                                    'frame': frame_count,
                                    'timestamp': frame_count / fps,
                                    **emotion
                                })
                    
                    # 进度日志 (每100帧报告一次)
                    if frame_count % 100 == 0:
                        progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                        logger.debug(f"📈 视频分析进度: {progress:.1f}% ({frame_count}/{total_frames})")
                        
                except Exception as frame_error:
                    logger.warning(f"⚠️ 第{frame_count}帧分析失败: {str(frame_error)}")
                    continue
            
            cap.release()
            
            # 分析结果统计
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"📊 视频分析完成:")
            logger.info(f"   - 总帧数: {frame_count}")
            logger.info(f"   - 检测到人脸的帧数: {processed_frames}")
            logger.info(f"   - 头部姿态分析: {len(head_poses)}个有效结果")
            logger.info(f"   - 视线方向分析: {len(gaze_directions)}个有效结果") 
            logger.info(f"   - 情绪分析: {len(emotions_timeline)}个有效结果")
            logger.info(f"   - 处理耗时: {processing_time:.2f}秒")
            
            # 计算统计特征
            analysis_result = self._compute_visual_statistics(
                head_poses, gaze_directions, emotions_timeline
            )
            
            # 添加处理统计信息
            analysis_result.update({
                'processing_stats': {
                    'total_frames': frame_count,
                    'processed_frames': processed_frames,
                    'processing_time_seconds': processing_time,
                    'head_pose_count': len(head_poses),
                    'gaze_direction_count': len(gaze_directions),
                    'emotion_analysis_count': len(emotions_timeline)
                }
            })
            
            logger.info("✅ 视频分析成功完成")
            return analysis_result
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ 视频分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            logger.error(f"⏱️ 失败前处理时间: {processing_time:.2f}秒")
            
            fallback_result = self._get_fallback_visual_analysis()
            fallback_result['error_details'] = {
                'error_message': str(e),
                'processing_time': processing_time
            }
            return fallback_result
    
    def _analyze_head_pose(self, face_landmarks, frame_shape) -> Optional[Dict[str, float]]:
        """分析头部姿态"""
        
        try:
            h, w = frame_shape[:2]
            
            # 提取2D关键点
            landmark_points = []
            for idx in [1, 175, 33, 263, 61, 291]:  # 鼻尖、下巴、眼角、嘴角
                if idx < len(face_landmarks.landmark):
                    lm = face_landmarks.landmark[idx]
                    landmark_points.append([lm.x * w, lm.y * h])
            
            if len(landmark_points) < 6:
                logger.debug("⚠️ 头部姿态分析: 关键点数量不足")
                return None
            
            image_points = np.array(landmark_points, dtype=np.float64)
            
            # 相机参数 (估算)
            focal_length = w
            center = (w/2, h/2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)
            
            dist_coeffs = np.zeros((4,1))
            
            # 使用PnP算法求解头部姿态
            success, rotation_vector, translation_vector = cv2.solvePnP(
                self.model_points, image_points, camera_matrix, dist_coeffs
            )
            
            if success:
                # 转换为欧拉角
                rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
                angles = self._rotation_matrix_to_euler(rotation_matrix)
                
                return {
                    'pitch': float(angles[0]),  # 俯仰角
                    'yaw': float(angles[1]),    # 偶航角
                    'roll': float(angles[2])    # 翻滚角
                }
            else:
                logger.debug("⚠️ 头部姿态分析: PnP算法求解失败")
            
        except Exception as e:
            logger.warning(f"❌ 头部姿态分析失败: {str(e)}")
            logger.debug(f"🔧 错误详情: {traceback.format_exc()}")
        
        return None
    
    def _analyze_gaze_direction(self, face_landmarks, frame_shape) -> Optional[Dict[str, float]]:
        """分析视线方向"""
        
        try:
            h, w = frame_shape[:2]
            
            # 获取虹膜和眼角关键点
            left_iris_idx = 468
            right_iris_idx = 473
            left_eye_corner_idx = 33
            right_eye_corner_idx = 263
            
            if (left_iris_idx >= len(face_landmarks.landmark) or 
                right_iris_idx >= len(face_landmarks.landmark)):
                return None
            
            # 计算视线向量
            left_iris = face_landmarks.landmark[left_iris_idx]
            right_iris = face_landmarks.landmark[right_iris_idx]
            left_corner = face_landmarks.landmark[left_eye_corner_idx]
            right_corner = face_landmarks.landmark[right_eye_corner_idx]
            
            # 计算视线偏移
            left_gaze_x = (left_iris.x - left_corner.x) * w
            left_gaze_y = (left_iris.y - left_corner.y) * h
            right_gaze_x = (right_iris.x - right_corner.x) * w
            right_gaze_y = (right_iris.y - right_corner.y) * h
            
            # 平均视线方向
            avg_gaze_x = (left_gaze_x + right_gaze_x) / 2
            avg_gaze_y = (left_gaze_y + right_gaze_y) / 2
            
            return {
                'gaze_x': float(avg_gaze_x),
                'gaze_y': float(avg_gaze_y),
                'gaze_magnitude': float(np.sqrt(avg_gaze_x**2 + avg_gaze_y**2))
            }
            
        except Exception as e:
            logging.warning(f"视线分析失败: {str(e)}")
        
        return None
    
    def _analyze_emotion(self, frame) -> Optional[Dict[str, float]]:
        """分析情绪"""
        
        if not DEEPFACE_AVAILABLE:
            logger.warning(f"🚫 DeepFace不可用，使用备用情绪分析: {DEEPFACE_ERROR}")
            return self._fallback_emotion_analysis()
        
        try:
            logger.debug("😊 开始DeepFace情绪分析...")
            
            # 检查帧的有效性
            if frame is None or frame.size == 0:
                logger.error("❌ 情绪分析失败: 输入帧为空")
                return self._fallback_emotion_analysis()
            
            # 使用DeepFace分析情绪
            result = DeepFace.analyze(
                frame, 
                actions=['emotion'], 
                enforce_detection=False,
                detector_backend=model_config.DEEPFACE_BACKEND,
                silent=True
            )
            
            if isinstance(result, list):
                result = result[0]
            
            emotions = result.get('emotion', {})
            
            if not emotions:
                logger.warning("⚠️ DeepFace返回空的情绪结果")
                return self._fallback_emotion_analysis()
            
            # 找出主导情绪
            dominant_emotion = max(emotions.items(), key=lambda x: x[1])
            
            logger.debug(f"✅ 情绪分析成功: {dominant_emotion[0]} ({dominant_emotion[1]:.2f}%)")
            
            return {
                'dominant_emotion': dominant_emotion[0],
                'dominant_score': float(dominant_emotion[1]),
                'emotions': {k: float(v) for k, v in emotions.items()}
            }
            
        except Exception as e:
            logger.error(f"❌ DeepFace情绪分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            logger.info("🔄 切换到备用情绪分析")
            return self._fallback_emotion_analysis()
    
    def _rotation_matrix_to_euler(self, rotation_matrix) -> Tuple[float, float, float]:
        """旋转矩阵转欧拉角"""
        
        sy = np.sqrt(rotation_matrix[0,0] * rotation_matrix[0,0] + 
                    rotation_matrix[1,0] * rotation_matrix[1,0])
        
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
    
    def _compute_visual_statistics(
        self, 
        head_poses: List[Dict], 
        gaze_directions: List[Dict], 
        emotions_timeline: List[Dict]
    ) -> Dict[str, Any]:
        """计算视觉分析统计特征"""
        
        result = {
            'head_pose_stability': 0.8,
            'gaze_stability': 0.7,
            'dominant_emotion': 'neutral',
            'emotion_stability': 0.8,
            'eye_contact_ratio': 0.75
        }
        
        if head_poses:
            # 计算头部姿态稳定性
            yaw_values = [pose['yaw'] for pose in head_poses]
            pitch_values = [pose['pitch'] for pose in head_poses]
            
            yaw_variance = np.var(yaw_values)
            pitch_variance = np.var(pitch_values)
            
            # 稳定性与方差成反比
            head_stability = 1.0 / (1.0 + (yaw_variance + pitch_variance) / 100)
            result['head_pose_stability'] = float(head_stability)
        
        if gaze_directions:
            # 计算视线稳定性
            gaze_magnitudes = [gaze['gaze_magnitude'] for gaze in gaze_directions]
            gaze_variance = np.var(gaze_magnitudes)
            
            gaze_stability = 1.0 / (1.0 + gaze_variance / 10)
            result['gaze_stability'] = float(gaze_stability)
            
            # 计算眼神接触比例 (视线偏移小于阈值的帧数比例)
            eye_contact_frames = sum(1 for mag in gaze_magnitudes if mag < 5.0)
            result['eye_contact_ratio'] = eye_contact_frames / len(gaze_magnitudes)
        
        if emotions_timeline:
            # 分析情绪分布
            emotion_counts = {}
            for emotion_data in emotions_timeline:
                emotion = emotion_data['dominant_emotion']
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
            
            # 主导情绪
            if emotion_counts:
                result['dominant_emotion'] = max(emotion_counts.items(), key=lambda x: x[1])[0]
            
            # 情绪稳定性 (负面情绪占比的倒数)
            negative_emotions = ['angry', 'disgust', 'fear', 'sad']
            negative_count = sum(emotion_counts.get(emotion, 0) for emotion in negative_emotions)
            total_count = sum(emotion_counts.values())
            
            if total_count > 0:
                negative_ratio = negative_count / total_count
                result['emotion_stability'] = 1.0 - negative_ratio
        
        return result
    
    def _fallback_emotion_analysis(self) -> Dict[str, Any]:
        """DeepFace不可用时的备用情绪分析"""
        logger.debug("🔄 使用备用情绪分析 (默认值)")
        return {
            'dominant_emotion': 'neutral',
            'dominant_score': 0.7,
            'emotions': {
                'neutral': 0.7,
                'happy': 0.1,
                'sad': 0.05,
                'angry': 0.05,
                'surprise': 0.05,
                'disgust': 0.025,
                'fear': 0.025
            },
            'fallback': True,
            'reason': 'DeepFace不可用或分析失败'
        }
    
    def _get_fallback_visual_analysis(self) -> Dict[str, Any]:
        """视频分析失败时的备用结果"""
        return {
            'head_pose_stability': 0.7,
            'gaze_stability': 0.7,
            'dominant_emotion': 'neutral',
            'emotion_stability': 0.8,
            'eye_contact_ratio': 0.6,
            'error': True,
            'message': '视频分析失败，使用默认值'
        }


class AudioAnalyzer:
    """音频分析器 - 处理听觉模态"""
    
    def __init__(self):
        self.sample_rate = model_config.AUDIO_SAMPLE_RATE
    
    def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """分析音频文件，提取听觉特征"""
        
        start_time = datetime.now()
        logger.info(f"🎵 开始音频分析: {audio_path}")
        
        try:
            # 检查音频文件是否存在
            if not Path(audio_path).exists():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            
            # 检查文件大小
            file_size = Path(audio_path).stat().st_size
            if file_size == 0:
                raise Exception("音频文件为空")
            
            logger.info(f"📊 音频文件大小: {file_size / 1024:.1f} KB")
            
            # 加载音频文件
            logger.debug("🔄 加载音频文件...")
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            
            if len(y) == 0:
                raise Exception("音频数据为空")
            
            duration = len(y) / sr
            logger.info(f"📊 音频信息: 采样率{sr}Hz, 时长{duration:.2f}秒, {len(y)}个采样点")
            
            # 语速分析
            logger.debug("🗣️ 分析语速...")
            speech_rate = self._analyze_speech_rate(y, sr)
            logger.debug(f"✅ 语速分析完成: {speech_rate:.1f} BPM")
            
            # 音高分析
            logger.debug("🎼 分析音高...")
            pitch_analysis = self._analyze_pitch(y, sr)
            logger.debug(f"✅ 音高分析完成: 平均{pitch_analysis['mean']:.1f}Hz")
            
            # 音量分析
            logger.debug("📢 分析音量...")
            volume_analysis = self._analyze_volume(y)
            logger.debug(f"✅ 音量分析完成: 平均{volume_analysis['mean']:.1f}dB")
            
            # 语音清晰度分析
            logger.debug("🎯 分析清晰度...")
            clarity_score = self._analyze_clarity(y, sr)
            logger.debug(f"✅ 清晰度分析完成: {clarity_score:.2f}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                'speech_rate_bpm': speech_rate,
                'pitch_mean': pitch_analysis['mean'],
                'pitch_variance': pitch_analysis['variance'],
                'pitch_range': pitch_analysis['range'],
                'volume_mean': volume_analysis['mean'],
                'volume_variance': volume_analysis['variance'],
                'clarity_score': clarity_score,
                'audio_duration': duration,
                'processing_stats': {
                    'processing_time_seconds': processing_time,
                    'sample_rate': sr,
                    'samples_count': len(y),
                    'file_size_bytes': file_size
                }
            }
            
            logger.info(f"✅ 音频分析成功完成 (耗时: {processing_time:.2f}秒)")
            return result
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ 音频分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            logger.error(f"⏱️ 失败前处理时间: {processing_time:.2f}秒")
            
            fallback_result = self._get_fallback_audio_analysis()
            fallback_result['error_details'] = {
                'error_message': str(e),
                'processing_time': processing_time
            }
            return fallback_result
    
    def _analyze_speech_rate(self, y: np.ndarray, sr: int) -> float:
        """分析语速"""
        
        try:
            # 使用节拍追踪估算语速
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            
            # 将音乐节拍转换为语音节奏的估算
            # 语音的"节拍"通常比音乐慢，需要调整
            speech_tempo = tempo * 0.6  # 经验调整因子
            
            return float(speech_tempo)
            
        except Exception as e:
            logging.warning(f"语速分析失败: {str(e)}")
            return 120.0  # 默认语速
    
    def _analyze_pitch(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """分析音高特征"""
        
        try:
            # 使用pyin算法提取基频
            f0, voiced_flag, voiced_probs = librosa.pyin(
                y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7')
            )
            
            # 只保留有效的音高值
            valid_f0 = f0[voiced_flag]
            
            if len(valid_f0) > 0:
                pitch_mean = float(np.mean(valid_f0))
                pitch_variance = float(np.var(valid_f0))
                pitch_range = float(np.max(valid_f0) - np.min(valid_f0))
            else:
                pitch_mean = 150.0  # 默认音高
                pitch_variance = 20.0
                pitch_range = 50.0
            
            return {
                'mean': pitch_mean,
                'variance': pitch_variance,
                'range': pitch_range
            }
            
        except Exception as e:
            logging.warning(f"音高分析失败: {str(e)}")
            return {
                'mean': 150.0,
                'variance': 20.0,
                'range': 50.0
            }
    
    def _analyze_volume(self, y: np.ndarray) -> Dict[str, float]:
        """分析音量特征"""
        
        try:
            # 计算RMS能量
            rms = librosa.feature.rms(y=y)[0]
            
            # 转换为分贝
            db = librosa.amplitude_to_db(rms)
            
            volume_mean = float(np.mean(db))
            volume_variance = float(np.var(db))
            
            return {
                'mean': volume_mean,
                'variance': volume_variance
            }
            
        except Exception as e:
            logging.warning(f"音量分析失败: {str(e)}")
            return {
                'mean': -20.0,
                'variance': 5.0
            }
    
    def _analyze_clarity(self, y: np.ndarray, sr: int) -> float:
        """分析语音清晰度"""
        
        try:
            # 使用频谱质心作为清晰度的代理指标
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            
            # 计算清晰度分数 (频谱质心的稳定性)
            centroid_variance = np.var(spectral_centroids)
            clarity_score = 1.0 / (1.0 + centroid_variance / 1000000)
            
            return float(clarity_score)
            
        except Exception as e:
            logging.warning(f"清晰度分析失败: {str(e)}")
            return 0.8  # 默认清晰度
    
    def _get_fallback_audio_analysis(self) -> Dict[str, Any]:
        """音频分析失败时的备用结果"""
        return {
            'speech_rate_bpm': 120.0,
            'pitch_mean': 150.0,
            'pitch_variance': 20.0,
            'pitch_range': 50.0,
            'volume_mean': -20.0,
            'volume_variance': 5.0,
            'clarity_score': 0.8,
            'audio_duration': 60.0,
            'error': True,
            'message': '音频分析失败，使用默认值'
        }


class MultimodalAnalyzer:
    """多模态分析器 - 整合视觉和听觉分析"""
    
    def __init__(self):
        self.video_analyzer = VideoAnalyzer()
        self.audio_analyzer = AudioAnalyzer()
    
    def analyze_interview_media(
        self, 
        video_path: Optional[str] = None, 
        audio_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """分析面试的音视频数据"""
        
        start_time = datetime.now()
        logger.info("🚀 开始多模态面试分析")
        logger.info(f"📁 视频文件: {video_path if video_path else '未提供'}")
        logger.info(f"📁 音频文件: {audio_path if audio_path else '未提供'}")
        
        result = {
            'visual_analysis': None,
            'audio_analysis': None,
            'analysis_timestamp': start_time.isoformat(),
            'processing_summary': {
                'video_success': False,
                'audio_success': False,
                'errors': []
            }
        }
        
        # DeepFace可用性检查
        if not DEEPFACE_AVAILABLE:
            logger.warning(f"⚠️ DeepFace不可用，情绪分析将使用备用方案: {DEEPFACE_ERROR}")
            result['processing_summary']['errors'].append(f"DeepFace不可用: {DEEPFACE_ERROR}")
        
        # 视觉分析
        logger.info("=" * 50)
        logger.info("🎥 开始视觉分析部分")
        
        if video_path:
            video_file = Path(video_path)
            if video_file.exists() and video_file.stat().st_size > 0:
                logger.info(f"📂 视频文件有效: {video_file.stat().st_size / (1024*1024):.1f} MB")
                try:
                    result['visual_analysis'] = self.video_analyzer.analyze_video(video_path)
                    result['processing_summary']['video_success'] = True
                    logger.info("✅ 视频分析部分完成")
                except Exception as e:
                    error_msg = f"视频分析失败: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    logger.error(f"🔧 错误详情: {traceback.format_exc()}")
                    result['visual_analysis'] = self.video_analyzer._get_fallback_visual_analysis()
                    result['processing_summary']['errors'].append(error_msg)
            else:
                error_msg = f"视频文件不存在或为空: {video_path}"
                logger.warning(f"⚠️ {error_msg}")
                result['visual_analysis'] = self.video_analyzer._get_fallback_visual_analysis()
                result['processing_summary']['errors'].append(error_msg)
        else:
            logger.info("ℹ️ 未提供视频文件路径，使用默认视觉分析")
            result['visual_analysis'] = self.video_analyzer._get_fallback_visual_analysis()
        
        # 听觉分析
        logger.info("=" * 50)
        logger.info("🎵 开始听觉分析部分")
        
        if audio_path:
            audio_file = Path(audio_path)
            if audio_file.exists() and audio_file.stat().st_size > 0:
                logger.info(f"📂 音频文件有效: {audio_file.stat().st_size / 1024:.1f} KB")
                try:
                    result['audio_analysis'] = self.audio_analyzer.analyze_audio(audio_path)
                    result['processing_summary']['audio_success'] = True
                    logger.info("✅ 音频分析部分完成")
                except Exception as e:
                    error_msg = f"音频分析失败: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    logger.error(f"🔧 错误详情: {traceback.format_exc()}")
                    result['audio_analysis'] = self.audio_analyzer._get_fallback_audio_analysis()
                    result['processing_summary']['errors'].append(error_msg)
            else:
                error_msg = f"音频文件不存在或为空: {audio_path}"
                logger.warning(f"⚠️ {error_msg}")
                result['audio_analysis'] = self.audio_analyzer._get_fallback_audio_analysis()
                result['processing_summary']['errors'].append(error_msg)
        else:
            logger.info("ℹ️ 未提供音频文件路径，使用默认听觉分析")
            result['audio_analysis'] = self.audio_analyzer._get_fallback_audio_analysis()
        
        # 分析总结
        total_processing_time = (datetime.now() - start_time).total_seconds()
        result['processing_summary']['total_time_seconds'] = total_processing_time
        
        logger.info("=" * 50)
        logger.info("📊 多模态分析总结:")
        logger.info(f"   🎥 视频分析: {'✅ 成功' if result['processing_summary']['video_success'] else '❌ 失败/跳过'}")
        logger.info(f"   🎵 音频分析: {'✅ 成功' if result['processing_summary']['audio_success'] else '❌ 失败/跳过'}")
        logger.info(f"   ⏱️ 总处理时间: {total_processing_time:.2f}秒")
        
        if result['processing_summary']['errors']:
            logger.warning(f"   ⚠️ 错误数量: {len(result['processing_summary']['errors'])}")
            for i, error in enumerate(result['processing_summary']['errors'], 1):
                logger.warning(f"     {i}. {error}")
        else:
            logger.info("   🎉 所有分析均成功完成!")
        
        logger.info("🏁 多模态面试分析完成")
        return result


def create_multimodal_analyzer() -> MultimodalAnalyzer:
    """创建多模态分析器实例"""
    return MultimodalAnalyzer() 