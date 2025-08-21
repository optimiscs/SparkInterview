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
import os
import json

# 配置详细日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DeepFace可用性检查和初始化
DEEPFACE_AVAILABLE = False
DEEPFACE_ERROR = None

# DeepFace导入
DeepFace = None

def check_deepface_availability():
    """检查DeepFace是否可用并进行初始化测试"""
    global DEEPFACE_AVAILABLE, DEEPFACE_ERROR, DeepFace
    
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
        logger.error("💡 请安装DeepFace: pip install deepface")
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
        # 初始化MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=model_config.MEDIAPIPE_CONFIDENCE,
            min_tracking_confidence=model_config.MEDIAPIPE_CONFIDENCE
        )
        
        # 初始化MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=model_config.MEDIAPIPE_CONFIDENCE,
            min_tracking_confidence=model_config.MEDIAPIPE_CONFIDENCE
        )
        
        # 初始化MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=1,
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
        
        # 创建保存目录
        self.save_dir = Path("data/analysis_frames")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 分析帧保存目录: {self.save_dir.absolute()}")
    
    def _save_analysis_frame(self, frame: np.ndarray, frame_count: int, timestamp: float, 
                           analysis_result: Dict[str, Any], frame_type: str = "analysis") -> str:
        """保存分析帧到本地"""
        
        try:
            # 生成时间戳
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            # 构建文件名
            filename = f"{timestamp_str}_frame_{frame_count:06d}_{frame_type}.jpg"
            filepath = self.save_dir / filename
            
            # 在图像上绘制分析结果信息
            annotated_frame = frame.copy()
            
            # 添加文本信息
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            color = (255, 255, 255)  # 白色
            thickness = 2
            
            # 基本信息
            y_offset = 30
            cv2.putText(annotated_frame, f"Frame: {frame_count}", (10, y_offset), 
                       font, font_scale, color, thickness)
            y_offset += 25
            cv2.putText(annotated_frame, f"Time: {timestamp:.2f}s", (10, y_offset), 
                       font, font_scale, color, thickness)
            y_offset += 25
            
            # 分析结果信息
            if 'head_pose' in analysis_result:
                pose = analysis_result['head_pose']
                cv2.putText(annotated_frame, f"Pitch: {pose.get('pitch', 0):.1f}°", (10, y_offset), 
                           font, font_scale, color, thickness)
                y_offset += 25
                cv2.putText(annotated_frame, f"Yaw: {pose.get('yaw', 0):.1f}°", (10, y_offset), 
                           font, font_scale, color, thickness)
                y_offset += 25
                cv2.putText(annotated_frame, f"Roll: {pose.get('roll', 0):.1f}°", (10, y_offset), 
                           font, font_scale, color, thickness)
                y_offset += 25
            
            if 'gaze' in analysis_result:
                gaze = analysis_result['gaze']
                cv2.putText(annotated_frame, f"Gaze: ({gaze.get('gaze_x', 0):.1f}, {gaze.get('gaze_y', 0):.1f})", 
                           (10, y_offset), font, font_scale, color, thickness)
                y_offset += 25
            
            if 'emotion' in analysis_result:
                emotion = analysis_result['emotion']
                cv2.putText(annotated_frame, f"Emotion: {emotion.get('dominant_emotion', 'Unknown')}", 
                           (10, y_offset), font, font_scale, color, thickness)
                y_offset += 25
                cv2.putText(annotated_frame, f"Score: {emotion.get('dominant_score', 0):.1f}%", 
                           (10, y_offset), font, font_scale, color, thickness)
            
            # 保存图像
            cv2.imwrite(str(filepath), annotated_frame)
            
            # 保存分析结果JSON
            json_filename = f"{timestamp_str}_frame_{frame_count:06d}_{frame_type}_analysis.json"
            json_filepath = self.save_dir / json_filename
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'frame_count': frame_count,
                    'timestamp': timestamp,
                    'frame_type': frame_type,
                    'analysis_result': analysis_result,
                    'saved_at': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"💾 保存分析帧: {filename}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ 保存分析帧失败: {str(e)}")
            return ""
    
    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """分析视频文件，提取视觉特征"""
        
        start_time = datetime.now()
        logger.info(f"🎥 开始视频分析: {video_path}")
        
        # 检查视频文件是否存在
        if not Path(video_path).exists():
            error_msg = f"视频文件不存在: {video_path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            error_msg = f"无法打开视频文件: {video_path}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        try:
            # 获取视频基本信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"📊 视频信息: {total_frames}帧, {fps:.1f}FPS, {duration:.1f}秒")
            
            # 初始化分析结果存储
            head_poses = []
            gaze_directions = []
            body_language_results = []
            gesture_results = []
            emotions_timeline = []
            frame_count = 0
            processed_frames = 0
            saved_frames = []
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                timestamp = frame_count / fps if fps > 0 else 0
                
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
                        emotion = None
                        if frame_count % 10 == 0:
                            emotion = self._analyze_emotion(frame)
                            if emotion:
                                emotions_timeline.append({
                                    'frame': frame_count,
                                    'timestamp': timestamp,
                                    **emotion
                                })
                        
                        # 体态语言分析
                        body_language = self._analyze_body_language(frame)
                        if body_language:
                            body_language_results.append({
                                'frame': frame_count,
                                'timestamp': timestamp,
                                **body_language
                            })
                        
                        # 手势分析
                        gestures = self._analyze_gestures(frame)
                        if gestures:
                            gesture_results.append({
                                'frame': frame_count,
                                'timestamp': timestamp,
                                **gestures
                            })
                        
                        # 保存关键分析帧 (每30帧保存一次，或者有重要分析结果时)
                        should_save = (frame_count % 30 == 0 or 
                                     (emotion and emotion.get('dominant_score', 0) > 70) or
                                     (head_pose and abs(head_pose.get('yaw', 0)) > 15))
                        
                        if should_save:
                            analysis_result = {
                                'head_pose': head_pose,
                                'gaze': gaze,
                                'emotion': emotion,
                                'body_language': body_language,
                                'gestures': gestures
                            }
                            
                            saved_path = self._save_analysis_frame(
                                frame, frame_count, timestamp, analysis_result, "key"
                            )
                            if saved_path:
                                saved_frames.append({
                                    'frame_count': frame_count,
                                    'timestamp': timestamp,
                                    'filepath': saved_path,
                                    'analysis_result': analysis_result
                                })
                    
                    # 进度日志 (每100帧报告一次)
                    if frame_count % 100 == 0:
                        progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                        logger.debug(f"📈 视频分析进度: {progress:.1f}% ({frame_count}/{total_frames})")
                        
                except Exception as frame_error:
                    logger.error(f"❌ 第{frame_count}帧分析失败: {str(frame_error)}")
                    logger.error(f"🔧 错误详情: {traceback.format_exc()}")
                    # 不再使用备用方案，继续处理下一帧
                    continue
            
            cap.release()
            
            # 检查是否有有效的分析结果
            if processed_frames == 0:
                error_msg = "视频中未检测到任何有效的面部数据"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # 分析结果统计
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"📊 视频分析完成:")
            logger.info(f"   - 总帧数: {frame_count}")
            logger.info(f"   - 检测到人脸的帧数: {processed_frames}")
            logger.info(f"   - 头部姿态分析: {len(head_poses)}个有效结果")
            logger.info(f"   - 视线方向分析: {len(gaze_directions)}个有效结果") 
            logger.info(f"   - 情绪分析: {len(emotions_timeline)}个有效结果")
            logger.info(f"   - 体态语言分析: {len(body_language_results)}个有效结果")
            logger.info(f"   - 手势分析: {len(gesture_results)}个有效结果")
            logger.info(f"   - 保存的关键帧: {len(saved_frames)}个")
            logger.info(f"   - 处理耗时: {processing_time:.2f}秒")
            
            # 计算统计特征
            analysis_result = self._compute_visual_statistics(
                head_poses, gaze_directions, emotions_timeline, body_language_results, gesture_results
            )
            
            # 添加处理统计信息
            analysis_result.update({
                'processing_stats': {
                    'total_frames': frame_count,
                    'processed_frames': processed_frames,
                    'processing_time_seconds': processing_time,
                    'head_pose_count': len(head_poses),
                    'gaze_direction_count': len(gaze_directions),
                    'emotion_analysis_count': len(emotions_timeline),
                    'body_language_count': len(body_language_results),
                    'gesture_count': len(gesture_results),
                    'saved_frames_count': len(saved_frames),
                    'save_directory': str(self.save_dir.absolute())
                },
                'saved_frames': saved_frames
            })
            
            logger.info("✅ 视频分析成功完成")
            return analysis_result
            
        except Exception as e:
            cap.release()
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ 视频分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            logger.error(f"⏱️ 失败前处理时间: {processing_time:.2f}秒")
            raise
    
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
                logger.error("❌ 头部姿态分析: 关键点数量不足")
                raise Exception("头部姿态分析失败：关键点数量不足")
            
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
            
            if not success:
                logger.error("❌ 头部姿态分析: PnP算法求解失败")
                raise Exception("头部姿态分析失败：PnP算法求解失败")
            
            # 转换为欧拉角
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            angles = self._rotation_matrix_to_euler(rotation_matrix)
            
            return {
                'pitch': float(angles[0]),  # 俯仰角
                'yaw': float(angles[1]),    # 偶航角
                'roll': float(angles[2])    # 翻滚角
            }
            
        except Exception as e:
            logger.error(f"❌ 头部姿态分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
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
                logger.error("❌ 视线分析失败：虹膜关键点索引超出范围")
                raise Exception("视线分析失败：虹膜关键点索引超出范围")
            
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
            logger.error(f"❌ 视线分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_emotion(self, frame) -> Optional[Dict[str, float]]:
        """分析情绪"""
        
        if not DEEPFACE_AVAILABLE:
            error_msg = f"❌ DeepFace不可用，无法进行情绪分析: {DEEPFACE_ERROR}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        try:
            logger.debug("😊 开始DeepFace情绪分析...")
            
            # 检查帧的有效性
            if frame is None or frame.size == 0:
                logger.error("❌ 情绪分析失败: 输入帧为空")
                raise Exception("情绪分析失败：输入帧为空")
            
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
                logger.error("❌ DeepFace返回空的情绪结果")
                raise Exception("DeepFace返回空的情绪结果")
            
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
            raise
    
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
    
    def _analyze_body_language(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """分析体态语言 - 使用MediaPipe Pose"""
        try:
            # 转换为RGB格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 进行姿态检测
            results = self.pose.process(rgb_frame)
            
            if not results.pose_landmarks:
                logger.debug("🤷 未检测到身体姿态")
                return None
            
            landmarks = results.pose_landmarks.landmark
            
            # 关键点索引
            LEFT_SHOULDER = self.mp_pose.PoseLandmark.LEFT_SHOULDER.value
            RIGHT_SHOULDER = self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value
            LEFT_HIP = self.mp_pose.PoseLandmark.LEFT_HIP.value
            RIGHT_HIP = self.mp_pose.PoseLandmark.RIGHT_HIP.value
            NOSE = self.mp_pose.PoseLandmark.NOSE.value
            
            # 计算肩膀水平度
            left_shoulder = landmarks[LEFT_SHOULDER]
            right_shoulder = landmarks[RIGHT_SHOULDER]
            shoulder_slope = abs(left_shoulder.y - right_shoulder.y)
            
            # 计算身体倾斜度 (基于肩膀和臀部的偏移)
            left_hip = landmarks[LEFT_HIP]
            right_hip = landmarks[RIGHT_HIP]
            
            shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2
            hip_center_x = (left_hip.x + right_hip.x) / 2
            body_angle = abs(shoulder_center_x - hip_center_x) * 180  # 转换为角度
            
            # 计算姿态分数 (0-100)
            posture_score = max(0, 100 - (shoulder_slope * 500) - (body_angle * 2))
            
            # 计算身体稳定性
            nose_position = landmarks[NOSE]
            center_offset = abs(nose_position.x - 0.5)  # 相对于画面中心的偏移
            
            # 分析坐姿/站姿状态
            shoulder_hip_distance = abs(left_shoulder.y - left_hip.y)
            posture_type = "sitting" if shoulder_hip_distance < 0.3 else "standing"
            
            # 检测紧张迹象
            tension_indicators = 0
            if shoulder_slope > 0.05:  # 肩膀不平
                tension_indicators += 1
            if body_angle > 10:  # 身体过度倾斜
                tension_indicators += 1
            if center_offset > 0.15:  # 偏离中心过多
                tension_indicators += 1
                
            tension_level = min(100, tension_indicators * 30)
            
            logger.debug(f"🧍 体态分析: 姿态分数={posture_score:.1f}, 身体角度={body_angle:.1f}°, 紧张度={tension_level}")
            
            return {
                'posture_score': float(posture_score),
                'body_angle': float(body_angle),
                'shoulder_slope': float(shoulder_slope),
                'tension_level': float(tension_level),
                'posture_type': posture_type,
                'center_offset': float(center_offset),
                'body_stability': float(1.0 - center_offset)
            }
            
        except Exception as e:
            logger.error(f"❌ 体态语言分析失败: {str(e)}")
            return None
    
    def _analyze_gestures(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """分析手势 - 使用MediaPipe Hands"""
        try:
            # 转换为RGB格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 进行手部检测
            results = self.hands.process(rgb_frame)
            
            if not results.multi_hand_landmarks:
                logger.debug("👋 未检测到手部")
                return {
                    'hands_detected': 0,
                    'gesture_activity': 0.0,
                    'dominant_gesture': 'none',
                    'hand_positions': []
                }
            
            hands_data = []
            total_movement = 0.0
            
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                landmarks = hand_landmarks.landmark
                
                # 关键点索引
                WRIST = 0
                THUMB_TIP = 4
                INDEX_TIP = 8
                MIDDLE_TIP = 12
                RING_TIP = 16
                PINKY_TIP = 20
                
                # 计算手的位置 (基于手腕)
                wrist = landmarks[WRIST]
                hand_position = (wrist.x, wrist.y)
                
                # 计算手指的展开程度
                finger_tips = [
                    landmarks[THUMB_TIP],
                    landmarks[INDEX_TIP], 
                    landmarks[MIDDLE_TIP],
                    landmarks[RING_TIP],
                    landmarks[PINKY_TIP]
                ]
                
                # 计算手指间的平均距离 (表示手的展开程度)
                finger_spread = 0
                for i in range(len(finger_tips)):
                    for j in range(i + 1, len(finger_tips)):
                        tip1, tip2 = finger_tips[i], finger_tips[j]
                        distance = np.sqrt((tip1.x - tip2.x)**2 + (tip1.y - tip2.y)**2)
                        finger_spread += distance
                
                finger_spread /= 10  # 标准化
                
                # 计算手的移动量 (基于相对位置变化)
                movement = abs(wrist.x - 0.5) + abs(wrist.y - 0.5)
                total_movement += movement
                
                # 简单的手势识别
                gesture_type = self._classify_gesture(landmarks)
                
                hands_data.append({
                    'hand_index': idx,
                    'position': hand_position,
                    'finger_spread': float(finger_spread),
                    'movement': float(movement),
                    'gesture_type': gesture_type
                })
            
            # 计算整体手势活跃度
            gesture_activity = min(100, total_movement * 200)
            
            # 确定主导手势
            gesture_types = [hand['gesture_type'] for hand in hands_data]
            dominant_gesture = max(set(gesture_types), key=gesture_types.count) if gesture_types else 'none'
            
            logger.debug(f"👋 手势分析: 检测到{len(hands_data)}只手, 活跃度={gesture_activity:.1f}, 主导手势={dominant_gesture}")
            
            return {
                'hands_detected': len(hands_data),
                'gesture_activity': float(gesture_activity),
                'dominant_gesture': dominant_gesture,
                'hand_positions': hands_data,
                'total_movement': float(total_movement)
            }
            
        except Exception as e:
            logger.error(f"❌ 手势分析失败: {str(e)}")
            return None
    
    def _classify_gesture(self, landmarks) -> str:
        """简单的手势分类"""
        try:
            # 关键点
            wrist = landmarks[0]
            thumb_tip = landmarks[4]
            index_tip = landmarks[8]
            middle_tip = landmarks[12]
            ring_tip = landmarks[16]
            pinky_tip = landmarks[20]
            
            # 计算手指相对于手腕的位置
            fingers_up = []
            
            # 拇指 (特殊处理，因为方向不同)
            if thumb_tip.x > wrist.x:  # 假设右手
                fingers_up.append(thumb_tip.x > landmarks[3].x)
            else:  # 左手
                fingers_up.append(thumb_tip.x < landmarks[3].x)
            
            # 其他四指
            finger_tips = [index_tip, middle_tip, ring_tip, pinky_tip]
            finger_pips = [landmarks[6], landmarks[10], landmarks[14], landmarks[18]]
            
            for tip, pip in zip(finger_tips, finger_pips):
                fingers_up.append(tip.y < pip.y)
            
            # 简单手势识别
            fingers_count = sum(fingers_up)
            
            if fingers_count == 0:
                return "fist"
            elif fingers_count == 1:
                if fingers_up[1]:  # 只有食指
                    return "pointing"
                elif fingers_up[0]:  # 只有拇指
                    return "thumbs_up"
                else:
                    return "one_finger"
            elif fingers_count == 2:
                if fingers_up[1] and fingers_up[2]:  # 食指和中指
                    return "peace"
                else:
                    return "two_fingers"
            elif fingers_count == 5:
                return "open_hand"
            else:
                return "partial_open"
                
        except Exception as e:
            logger.debug(f"⚠️ 手势分类失败: {str(e)}")
            return "unknown"
    
    def _compute_visual_statistics(
        self, 
        head_poses: List[Dict], 
        gaze_directions: List[Dict], 
        emotions_timeline: List[Dict],
        body_language_results: List[Dict] = None,
        gesture_results: List[Dict] = None
    ) -> Dict[str, Any]:
        """计算视觉分析统计特征"""
        
        if not head_poses and not gaze_directions and not emotions_timeline:
            error_msg = "所有视觉分析结果均为空，无法计算统计特征"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        result = {}
        
        if head_poses:
            # 计算头部姿态稳定性
            yaw_values = [pose['yaw'] for pose in head_poses]
            pitch_values = [pose['pitch'] for pose in head_poses]
            
            yaw_variance = np.var(yaw_values)
            pitch_variance = np.var(pitch_values)
            
            # 稳定性与方差成反比
            head_stability = 1.0 / (1.0 + (yaw_variance + pitch_variance) / 100)
            result['head_pose_stability'] = float(head_stability)
        else:
            logger.warning("⚠️ 头部姿态数据为空")
        
        if gaze_directions:
            # 计算视线稳定性
            gaze_magnitudes = [gaze['gaze_magnitude'] for gaze in gaze_directions]
            gaze_variance = np.var(gaze_magnitudes)
            
            gaze_stability = 1.0 / (1.0 + gaze_variance / 10)
            result['gaze_stability'] = float(gaze_stability)
            
            # 计算眼神接触比例 (视线偏移小于阈值的帧数比例)
            eye_contact_frames = sum(1 for mag in gaze_magnitudes if mag < 5.0)
            result['eye_contact_ratio'] = eye_contact_frames / len(gaze_magnitudes)
        else:
            logger.warning("⚠️ 视线方向数据为空")
        
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
        else:
            logger.warning("⚠️ 情绪分析数据为空")
        
        # 体态语言分析统计
        if body_language_results:
            posture_scores = [bl.get('posture_score', 0) for bl in body_language_results if 'posture_score' in bl]
            if posture_scores:
                result['avg_posture_score'] = float(np.mean(posture_scores))
                result['posture_stability'] = float(1.0 - (np.std(posture_scores) / 100.0))
            
            # 身体倾斜度统计
            body_angles = [bl.get('body_angle', 0) for bl in body_language_results if 'body_angle' in bl]
            if body_angles:
                result['avg_body_angle'] = float(np.mean(body_angles))
                result['body_angle_variance'] = float(np.var(body_angles))
        else:
            logger.warning("⚠️ 体态语言分析数据为空")
        
        # 手势分析统计
        if gesture_results:
            gesture_activity = [gr.get('gesture_activity', 0) for gr in gesture_results if 'gesture_activity' in gr]
            if gesture_activity:
                result['avg_gesture_activity'] = float(np.mean(gesture_activity))
                result['gesture_expressiveness'] = float(np.max(gesture_activity))
            
            # 手势类型分布
            gesture_types = {}
            for gr in gesture_results:
                gesture_type = gr.get('dominant_gesture', 'unknown')
                gesture_types[gesture_type] = gesture_types.get(gesture_type, 0) + 1
            
            if gesture_types:
                result['dominant_gesture_type'] = max(gesture_types.items(), key=lambda x: x[1])[0]
                result['gesture_variety'] = len(gesture_types)
        else:
            logger.warning("⚠️ 手势分析数据为空")
        
        return result


class AudioAnalyzer:
    """音频分析器 - 处理听觉模态"""
    
    def __init__(self):
        self.sample_rate = model_config.AUDIO_SAMPLE_RATE
    
    def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """分析音频文件，提取听觉特征"""
        
        start_time = datetime.now()
        logger.info(f"🎵 开始音频分析: {audio_path}")
        
        # 检查音频文件是否存在
        if not Path(audio_path).exists():
            error_msg = f"音频文件不存在: {audio_path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # 检查文件大小
        file_size = Path(audio_path).stat().st_size
        if file_size == 0:
            error_msg = "音频文件为空"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        logger.info(f"📊 音频文件大小: {file_size / 1024:.1f} KB")
        
        try:
            # 加载音频文件
            logger.debug("🔄 加载音频文件...")
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            
            if len(y) == 0:
                error_msg = "音频数据为空"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
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
            raise
    
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
            logger.error(f"❌ 语速分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_pitch(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """分析音高特征"""
        
        try:
            # 使用pyin算法提取基频
            f0, voiced_flag, voiced_probs = librosa.pyin(
                y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7')
            )
            
            # 只保留有效的音高值
            valid_f0 = f0[voiced_flag]
            
            if len(valid_f0) == 0:
                error_msg = "音高分析失败：未检测到有效的音高值"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            pitch_mean = float(np.mean(valid_f0))
            pitch_variance = float(np.var(valid_f0))
            pitch_range = float(np.max(valid_f0) - np.min(valid_f0))
            
            return {
                'mean': pitch_mean,
                'variance': pitch_variance,
                'range': pitch_range
            }
            
        except Exception as e:
            logger.error(f"❌ 音高分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_volume(self, y: np.ndarray) -> Dict[str, float]:
        """分析音量特征"""
        
        try:
            # 计算RMS能量
            rms = librosa.feature.rms(y=y)[0]
            
            if len(rms) == 0:
                error_msg = "音量分析失败：RMS计算结果为空"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # 转换为分贝
            db = librosa.amplitude_to_db(rms)
            
            volume_mean = float(np.mean(db))
            volume_variance = float(np.var(db))
            
            return {
                'mean': volume_mean,
                'variance': volume_variance
            }
            
        except Exception as e:
            logger.error(f"❌ 音量分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise
    
    def _analyze_clarity(self, y: np.ndarray, sr: int) -> float:
        """分析语音清晰度"""
        
        try:
            # 使用频谱质心作为清晰度的代理指标
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            
            if len(spectral_centroids) == 0:
                error_msg = "清晰度分析失败：频谱质心计算结果为空"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # 计算清晰度分数 (频谱质心的稳定性)
            centroid_variance = np.var(spectral_centroids)
            clarity_score = 1.0 / (1.0 + centroid_variance / 1000000)
            
            return float(clarity_score)
            
        except Exception as e:
            logger.error(f"❌ 清晰度分析失败: {str(e)}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            raise


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
        
        if not video_path and not audio_path:
            error_msg = "必须至少提供视频文件或音频文件路径"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
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
            error_msg = f"DeepFace不可用，无法进行情绪分析: {DEEPFACE_ERROR}"
            logger.error(f"❌ {error_msg}")
            result['processing_summary']['errors'].append(error_msg)
        
        # 视觉分析
        if video_path:
            logger.info("=" * 50)
            logger.info("🎥 开始视觉分析部分")
            
            try:
                result['visual_analysis'] = self.video_analyzer.analyze_video(video_path)
                result['processing_summary']['video_success'] = True
                logger.info("✅ 视频分析部分完成")
            except Exception as e:
                error_msg = f"视频分析失败: {str(e)}"
                logger.error(f"❌ {error_msg}")
                logger.error(f"🔧 错误详情: {traceback.format_exc()}")
                result['processing_summary']['errors'].append(error_msg)
                # 不再提供备用结果，直接记录错误
        
        # 听觉分析
        if audio_path:
            logger.info("=" * 50)
            logger.info("🎵 开始听觉分析部分")
            
            try:
                result['audio_analysis'] = self.audio_analyzer.analyze_audio(audio_path)
                result['processing_summary']['audio_success'] = True
                logger.info("✅ 音频分析部分完成")
            except Exception as e:
                error_msg = f"音频分析失败: {str(e)}"
                logger.error(f"❌ {error_msg}")
                logger.error(f"🔧 错误详情: {traceback.format_exc()}")
                result['processing_summary']['errors'].append(error_msg)
                # 不再提供备用结果，直接记录错误
        
        # 分析总结
        total_processing_time = (datetime.now() - start_time).total_seconds()
        result['processing_summary']['total_time_seconds'] = total_processing_time
        
        logger.info("=" * 50)
        logger.info("📊 多模态分析总结:")
        logger.info(f"   🎥 视频分析: {'✅ 成功' if result['processing_summary']['video_success'] else '❌ 失败/跳过'}")
        logger.info(f"   🎵 音频分析: {'✅ 成功' if result['processing_summary']['audio_success'] else '❌ 失败/跳过'}")
        logger.info(f"   ⏱️ 总处理时间: {total_processing_time:.2f}秒")
        
        if result['processing_summary']['errors']:
            logger.error(f"   ⚠️ 错误数量: {len(result['processing_summary']['errors'])}")
            for i, error in enumerate(result['processing_summary']['errors'], 1):
                logger.error(f"     {i}. {error}")
            
            # 如果所有分析都失败，抛出异常
            if not result['processing_summary']['video_success'] and not result['processing_summary']['audio_success']:
                error_msg = "所有多模态分析均失败"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        else:
            logger.info("   🎉 所有分析均成功完成!")
        
        logger.info("🏁 多模态面试分析完成")
        return result


def create_multimodal_analyzer() -> MultimodalAnalyzer:
    """创建多模态分析器实例"""
    return MultimodalAnalyzer() 