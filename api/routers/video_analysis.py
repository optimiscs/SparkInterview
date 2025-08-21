# -*- encoding:utf-8 -*-
"""
实时视频多模态分析服务
基于WebSocket实现前后端视频分析集成
集成MediaPipe、DeepFace等工具进行真实多模态分析

主要功能：
- 实时视频流接收和处理
- 头部姿态分析
- 面部表情/情绪分析  
- 视线追踪
- 体态语言分析
- 与语音识别协同工作
"""
import asyncio
import json
import logging
import base64
import time
import cv2
import numpy as np
import traceback
from datetime import datetime
from typing import Dict, Optional, Any, List
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 设置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 多模态分析工具
from src.tools.multimodal_analyzer import create_multimodal_analyzer, VideoAnalyzer, DEEPFACE_AVAILABLE

# 导入DeepFace用于调试分析
try:
    from deepface import DeepFace
    logger.info("✅ DeepFace直接导入成功")
except ImportError as e:
    DeepFace = None
    logger.error(f"❌ DeepFace直接导入失败: {e}")

# 路由器
router = APIRouter(tags=["视频分析"])

class RealTimeAnalysisManager:
    """实时分析管理器 - 处理视频帧缓存和分析调度"""
    
    def __init__(self):
        self.video_analyzer = VideoAnalyzer()
        self.frame_buffer = []  # 帧缓存
        self.analysis_results = []  # 分析结果缓存
        self.max_buffer_size = 30  # 最多缓存30帧
        self.analysis_interval = 5  # 每5帧分析一次
        self.frame_count = 0
        self.last_analysis_time = time.time()
        
        # 实时状态跟踪
        self.current_emotion = {"dominant_emotion": "neutral", "confidence": 0.0}
        self.head_pose_stability = 0.0
        self.eye_contact_ratio = 0.0
        self.tension_level = 0.0
        self.confidence_score = 0.5
        
        # 调试功能
        self.debug_enabled = True  # 是否保存调试图像
        self.debug_frames_saved = 0  # 已保存的调试帧数量
        self.max_debug_frames = 50  # 最多保存调试帧数量（循环覆盖）
        self.deepface_backends = ['opencv', 'retinaface', 'mtcnn']  # 不同的检测器
        self.current_backend_index = 0
        
        logger.info("📊 实时分析管理器初始化完成")
    
    def add_frame(self, frame_data) -> bool:
        """添加新帧到缓存"""
        try:
            logger.debug(f"🔍 接收帧数据类型: {type(frame_data)}, 大小: {len(frame_data) if hasattr(frame_data, '__len__') else 'N/A'}")
            
            # 解码图像数据
            if isinstance(frame_data, str):
                # Base64字符串格式
                logger.debug("📝 处理Base64字符串格式")
                # 移除data URL前缀
                if frame_data.startswith('data:image'):
                    frame_data = frame_data.split(',')[1]
                frame_bytes = base64.b64decode(frame_data)
            else:
                # 二进制数据格式
                logger.debug("📦 处理二进制数据格式")
                frame_bytes = frame_data
            
            logger.debug(f"🔢 解码后数据大小: {len(frame_bytes)} bytes")
            
            # 转换为numpy数组
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                logger.error(f"❌ 帧解码失败 - 数据前32字节: {frame_bytes[:32]}")
                return False
            
            # 检查帧尺寸
            height, width = frame.shape[:2]
            logger.debug(f"🖼️ 帧尺寸: {width}x{height}")
            
            # 添加到缓存
            timestamp = time.time()
            self.frame_buffer.append({
                'frame': frame,
                'timestamp': timestamp,
                'frame_id': self.frame_count
            })
            self.frame_count += 1
            
            # 维护缓存大小
            if len(self.frame_buffer) > self.max_buffer_size:
                self.frame_buffer.pop(0)
            
            logger.debug(f"✅ 添加帧 #{self.frame_count}, 缓存大小: {len(self.frame_buffer)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加帧失败: {e}")
            import traceback
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            return False
    
    async def analyze_current_frame(self) -> Optional[Dict[str, Any]]:
        """分析当前帧"""
        if not self.frame_buffer:
            return None
        
        current_time = time.time()
        
        # 检查是否需要分析（避免过于频繁）
        if current_time - self.last_analysis_time < 0.5:  # 最少0.5秒间隔，匹配前端2FPS
            return self._get_cached_results()
        
        try:
            # 获取最新帧
            latest_frame_data = self.frame_buffer[-1]
            frame = latest_frame_data['frame']
            
            logger.debug(f"🔍 开始分析帧 #{latest_frame_data['frame_id']}")
            
            # 执行分析
            analysis_result = await self._analyze_single_frame(frame)
            
            if analysis_result:
                # 更新实时状态
                self._update_realtime_state(analysis_result)
                
                # 缓存结果
                self.analysis_results.append({
                    'timestamp': current_time,
                    'frame_id': latest_frame_data['frame_id'],
                    'analysis': analysis_result
                })
                
                # 维护结果缓存大小
                if len(self.analysis_results) > 10:
                    self.analysis_results.pop(0)
                
                self.last_analysis_time = current_time
                
                logger.info(f"✅ 帧分析完成 #{latest_frame_data['frame_id']}")
                return self._format_realtime_result(analysis_result)
            
            return self._get_cached_results()
            
        except Exception as e:
            logger.error(f"❌ 帧分析失败: {e}")
            return self._get_cached_results()
    
    async def _analyze_single_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """分析单个帧"""
        results = {}
        
        try:
            # 保存调试图像（如果启用且未达到限制）
            debug_path = self._save_debug_frame(frame)
            if not debug_path:
                debug_path = f"frame_{self.frame_count}"  # 使用备用标识符
            
            # MediaPipe面部检测
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mediapipe_results = self.video_analyzer.face_mesh.process(rgb_frame)
            
            if mediapipe_results.multi_face_landmarks:
                face_landmarks = mediapipe_results.multi_face_landmarks[0]
                
                # 头部姿态分析
                try:
                    head_pose = self.video_analyzer._analyze_head_pose(face_landmarks, frame.shape)
                    if head_pose:
                        results['head_pose'] = head_pose
                        logger.debug(f"✅ 头部姿态: {head_pose}")
                except Exception as e:
                    logger.warning(f"⚠️ 头部姿态分析失败: {e}")
                
                # 视线方向分析
                try:
                    gaze = self.video_analyzer._analyze_gaze_direction(face_landmarks, frame.shape)
                    if gaze:
                        results['gaze'] = gaze
                        logger.debug(f"✅ 视线方向: {gaze}")
                except Exception as e:
                    logger.warning(f"⚠️ 视线分析失败: {e}")
            
            # 情绪分析（DeepFace）- 增强调试版本
            if DEEPFACE_AVAILABLE:
                try:
                    emotion_result = self._analyze_emotion_with_debug(frame, debug_path)
                    if emotion_result:
                        results['emotion'] = emotion_result
                        logger.debug(f"✅ 情绪分析: {emotion_result['dominant_emotion']} ({emotion_result['dominant_score']:.1f}%)")
                except Exception as e:
                    logger.warning(f"⚠️ 情绪分析失败: {e}")
            else:
                logger.debug("⚠️ DeepFace不可用，跳过情绪分析")
            
            # 体态语言分析
            try:
                body_language_result = self.video_analyzer._analyze_body_language(frame)
                if body_language_result:
                    results['body_language'] = body_language_result
                    logger.debug(f"✅ 体态语言分析: 姿态分数={body_language_result.get('posture_score', 0):.1f}")
                    
                    # 更新实时状态
                    self.posture_score = body_language_result.get('posture_score', 75)
                    self.body_angle = body_language_result.get('body_angle', 0)
                    self.tension_level = body_language_result.get('tension_level', 25) / 100.0  # 标准化到0-1
                    self.posture_type = body_language_result.get('posture_type', 'sitting')
            except Exception as e:
                logger.warning(f"⚠️ 体态语言分析失败: {e}")
            
            # 手势分析
            try:
                gesture_result = self.video_analyzer._analyze_gestures(frame)
                if gesture_result:
                    results['gestures'] = gesture_result
                    logger.debug(f"✅ 手势分析: 活跃度={gesture_result.get('gesture_activity', 0):.1f}, 主导手势={gesture_result.get('dominant_gesture', 'none')}")
                    
                    # 更新实时状态
                    self.gesture_activity = gesture_result.get('gesture_activity', 0)
                    self.dominant_gesture = gesture_result.get('dominant_gesture', 'none')
            except Exception as e:
                logger.warning(f"⚠️ 手势分析失败: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 单帧分析异常: {e}")
            return {}
    
    def _save_debug_frame(self, frame: np.ndarray) -> str:
        """保存调试帧（循环覆盖模式）"""
        if not self.debug_enabled:
            return ""
        
        try:
            # 创建调试目录
            debug_dir = Path("data/debug_frames")
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            # 清理旧的调试文件（如果是第一次保存）
            if self.debug_frames_saved == 0:
                self._cleanup_old_debug_files(debug_dir)
            
            # 生成文件名（使用循环索引）
            debug_index = self.debug_frames_saved % self.max_debug_frames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"debug_frame_{timestamp}_{self.frame_count}.jpg"
            filepath = debug_dir / filename
            
            # 保存图像
            success = cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            if success:
                self.debug_frames_saved += 1
                logger.debug(f"💾 调试帧已保存: {filepath} (总计: {self.debug_frames_saved})")
                return str(filepath)
            else:
                logger.warning(f"⚠️ 调试帧保存失败: {filepath}")
                return ""
            
        except Exception as e:
            logger.error(f"❌ 保存调试帧失败: {e}")
            return ""
    
    def _cleanup_old_debug_files(self, debug_dir: Path):
        """清理旧的调试文件"""
        try:
            for file in debug_dir.glob("debug_frame_*"):
                file.unlink()
            logger.info("🧹 已清理旧的调试文件")
        except Exception as e:
            logger.warning(f"⚠️ 清理调试文件失败: {e}")
    
    def _analyze_emotion_with_debug(self, frame: np.ndarray, debug_path: str) -> Optional[Dict[str, Any]]:
        """带调试信息的情绪分析"""
        if not DEEPFACE_AVAILABLE or DeepFace is None:
            logger.error("❌ DeepFace不可用")
            return None
        
        try:
            # 检查输入帧
            height, width = frame.shape[:2]
            logger.info(f"🔍 情绪分析输入帧: {width}x{height}, 调试图像: {debug_path}")
            
            # 检查图像质量
            image_quality = self._assess_image_quality(frame)
            logger.info(f"📊 图像质量评估: {image_quality}")
            
            # 创建面部检测的调试版本
            frame_for_analysis = frame.copy()
            
            # 预处理：调整图像质量
            if width > 640:
                scale = 640 / width
                new_width = int(width * scale)  
                new_height = int(height * scale)
                frame_for_analysis = cv2.resize(frame_for_analysis, (new_width, new_height))
                logger.debug(f"🔄 图像缩放: {width}x{height} → {new_width}x{new_height}")
            
            # 保存处理后的图像用于调试
            processed_debug_path = debug_path.replace('.jpg', '_processed.jpg')
            try:
                # 确保目录存在
                Path(processed_debug_path).parent.mkdir(parents=True, exist_ok=True)
                
                # 使用更稳定的保存方法
                success = cv2.imwrite(processed_debug_path, frame_for_analysis, 
                                    [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                if success:
                    logger.debug(f"💾 处理后图像已保存: {processed_debug_path}")
                else:
                    logger.warning(f"⚠️ 处理后图像保存失败: {processed_debug_path}")
                    processed_debug_path = debug_path  # 使用原始路径作为fallback
                    
            except Exception as save_error:
                logger.warning(f"⚠️ 保存处理后图像时出错: {save_error}")
                processed_debug_path = debug_path  # 使用原始路径作为fallback
            
            # 使用DeepFace分析 - 尝试不同的检测器  
            current_backend = self.deepface_backends[self.current_backend_index]
            logger.info(f"🧠 开始DeepFace情绪分析... (使用检测器: {current_backend})")
            
            # 确保有有效的图像用于分析
            if frame_for_analysis is None or frame_for_analysis.size == 0:
                logger.error("❌ 分析用图像无效")
                return None
            
            try:
                result = DeepFace.analyze(
                    frame_for_analysis, 
                    actions=['emotion'], 
                    enforce_detection=False,
                    detector_backend=current_backend,
                    silent=True
                )
            except Exception as detector_error:
                logger.warning(f"⚠️ 检测器 {current_backend} 失败: {detector_error}")
                # 尝试下一个检测器
                self.current_backend_index = (self.current_backend_index + 1) % len(self.deepface_backends)
                next_backend = self.deepface_backends[self.current_backend_index]
                logger.info(f"🔄 尝试切换到检测器: {next_backend}")
                
                try:
                    result = DeepFace.analyze(
                        frame_for_analysis, 
                        actions=['emotion'], 
                        enforce_detection=False,
                        detector_backend=next_backend,
                        silent=True
                    )
                    current_backend = next_backend  # 更新当前使用的检测器
                except Exception as fallback_error:
                    logger.error(f"❌ 所有检测器都失败: {fallback_error}")
                    return None
            
            if isinstance(result, list):
                result = result[0]
            
            emotions = result.get('emotion', {})
            logger.info(f"📊 DeepFace原始结果: {emotions}")
            
            if not emotions:
                logger.error("❌ DeepFace返回空的情绪结果")
                return None
            
            # 找出主导情绪
            dominant_emotion = max(emotions.items(), key=lambda x: x[1])
            
            # 保存分析结果到调试文件
            debug_result = {
                'analysis_timestamp': datetime.now().isoformat(),
                'frame_info': {
                    'frame_count': self.frame_count,
                    'original_size': f"{width}x{height}",
                    'processed_size': f"{frame_for_analysis.shape[1]}x{frame_for_analysis.shape[0]}",
                    'debug_path': debug_path,
                    'processed_debug_path': processed_debug_path
                },
                'image_quality': image_quality,
                'deepface_config': {
                    'detector_backend': current_backend,
                    'enforce_detection': False,
                    'actions': ['emotion']
                },
                'deepface_result': {
                    'dominant_emotion': dominant_emotion[0],
                    'dominant_score': float(dominant_emotion[1]),
                    'all_emotions': {k: float(v) for k, v in emotions.items()}
                },
                'problem_analysis': {
                    'is_consistent_angry': bool(dominant_emotion[0] == 'angry' and dominant_emotion[1] > 80),
                    'score_very_high': bool(dominant_emotion[1] > 95),
                    'emotions_distribution': len(emotions),
                    'potential_issues': []
                }
            }
            
            # 添加潜在问题分析
            if dominant_emotion[0] == 'angry' and dominant_emotion[1] > 80:
                debug_result['problem_analysis']['potential_issues'].append("一直检测为angry，可能存在问题")
            
            if dominant_emotion[1] > 95:
                debug_result['problem_analysis']['potential_issues'].append("情绪置信度过高，可能检测有误")
            
            if len(set(emotions.values())) < 3:
                debug_result['problem_analysis']['potential_issues'].append("情绪分布单一，可能模型有问题")
            
            # 保存JSON调试文件（可选，失败不影响分析）
            if debug_path and debug_path != f"frame_{self.frame_count}":
                try:
                    debug_json_path = debug_path.replace('.jpg', '_analysis.json')
                    
                    # 使用自定义JSON编码器处理所有numpy类型
                    class NumpyEncoder(json.JSONEncoder):
                        def default(self, obj):
                            if isinstance(obj, np.integer):
                                return int(obj)
                            elif isinstance(obj, np.floating):
                                return float(obj)
                            elif isinstance(obj, np.ndarray):
                                return obj.tolist()
                            elif isinstance(obj, np.bool_):
                                return bool(obj)
                            return super(NumpyEncoder, self).default(obj)
                    
                    with open(debug_json_path, 'w', encoding='utf-8') as f:
                        json.dump(debug_result, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
                        
                    logger.debug(f"💾 JSON调试文件已保存: {debug_json_path}")
                except Exception as json_error:
                    logger.warning(f"⚠️ JSON调试文件保存失败: {json_error}")
            
            logger.info(f"✅ 情绪分析完成: {dominant_emotion[0]} ({dominant_emotion[1]:.1f}%)")
            
            return {
                'dominant_emotion': dominant_emotion[0],
                'dominant_score': float(dominant_emotion[1]),
                'emotions': {k: float(v) for k, v in emotions.items()},
                'debug_info': debug_result
            }
            
        except Exception as e:
            logger.error(f"❌ 情绪分析失败: {e}")
            logger.error(f"🔧 错误详情: {traceback.format_exc()}")
            return None
    
    def _assess_image_quality(self, frame: np.ndarray) -> Dict[str, Any]:
        """评估图像质量"""
        try:
            # 基本统计
            height, width = frame.shape[:2]
            
            # 亮度分析
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_brightness = np.mean(gray)
            brightness_std = np.std(gray)
            
            # 对比度分析 (使用Laplacian方差)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # 颜色分布
            b_mean, g_mean, r_mean = cv2.mean(frame)[:3]
            
            quality_info = {
                'resolution': f"{width}x{height}",
                'brightness': {
                    'mean': float(mean_brightness),
                    'std': float(brightness_std),
                    'is_too_dark': bool(mean_brightness < 50),
                    'is_too_bright': bool(mean_brightness > 200)
                },
                'contrast': {
                    'laplacian_variance': float(laplacian_var),
                    'is_blurry': bool(laplacian_var < 100)
                },
                'color_balance': {
                    'blue_mean': float(b_mean),
                    'green_mean': float(g_mean), 
                    'red_mean': float(r_mean)
                },
                'potential_issues': []
            }
            
            # 问题检测
            if mean_brightness < 50:
                quality_info['potential_issues'].append("图像过暗")
            if mean_brightness > 200:
                quality_info['potential_issues'].append("图像过亮")
            if laplacian_var < 100:
                quality_info['potential_issues'].append("图像模糊")
            if brightness_std < 20:
                quality_info['potential_issues'].append("对比度过低")
            
            return quality_info
            
        except Exception as e:
            logger.error(f"❌ 图像质量评估失败: {e}")
            return {'error': str(e)}
    
    def _update_realtime_state(self, analysis_result: Dict[str, Any]):
        """更新实时状态"""
        try:
            # 更新情绪状态
            if 'emotion' in analysis_result:
                emotion = analysis_result['emotion']
                self.current_emotion = {
                    "dominant_emotion": emotion['dominant_emotion'],
                    "confidence": emotion['dominant_score']
                }
                
                # 计算紧张度（基于负面情绪）
                negative_emotions = ['angry', 'fear', 'sad']
                negative_score = sum(emotion['emotions'].get(e, 0) for e in negative_emotions)
                self.tension_level = min(1.0, negative_score / 100.0)
                
                # 计算自信度（基于正面情绪和中性）
                positive_emotions = ['happy', 'neutral']
                positive_score = sum(emotion['emotions'].get(e, 0) for e in positive_emotions)
                self.confidence_score = min(1.0, positive_score / 100.0)
            
            # 更新头部姿态稳定性
            if 'head_pose' in analysis_result:
                pose = analysis_result['head_pose']
                # 基于头部偏转角度计算稳定性
                angle_variance = abs(pose.get('yaw', 0)) + abs(pose.get('pitch', 0)) + abs(pose.get('roll', 0))
                self.head_pose_stability = max(0.0, 1.0 - angle_variance / 90.0)  # 90度为完全不稳定
            
            # 更新眼神接触比例
            if 'gaze' in analysis_result:
                gaze = analysis_result['gaze']
                gaze_magnitude = gaze.get('gaze_magnitude', 0)
                # 视线偏移小于阈值认为是眼神接触
                is_eye_contact = gaze_magnitude < 5.0
                
                # 使用滑动平均更新眼神接触比例
                alpha = 0.1  # 平滑因子
                if is_eye_contact:
                    self.eye_contact_ratio = (1 - alpha) * self.eye_contact_ratio + alpha * 1.0
                else:
                    self.eye_contact_ratio = (1 - alpha) * self.eye_contact_ratio + alpha * 0.0
            
        except Exception as e:
            logger.error(f"❌ 更新实时状态失败: {e}")
    
    def _format_realtime_result(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """格式化为前端需要的实时结果"""
        return {
            'type': 'analysis_update',
            'timestamp': time.time(),
            'micro_expressions': {
                'dominant_emotion': self.current_emotion['dominant_emotion'],
                'confidence': round(self.confidence_score * 100, 1),
                'tension': round(self.tension_level * 100, 1),
                'focus': round(self.eye_contact_ratio * 100, 1)
            },
            'body_language': {
                'eye_contact_ratio': round(self.eye_contact_ratio * 100, 1),
                'head_stability': round(self.head_pose_stability * 100, 1),
                'posture_score': round(getattr(self, 'posture_score', 75), 1),
                'body_angle': round(getattr(self, 'body_angle', 0), 1),
                'tension_level': round(getattr(self, 'tension_level', 25), 1),
                'posture_type': getattr(self, 'posture_type', 'sitting'),
                'gesture_activity': round(getattr(self, 'gesture_activity', 0), 1),
                'dominant_gesture': getattr(self, 'dominant_gesture', 'none')
            },
            'voice_analysis': {
                # 这部分数据来自语音识别模块，这里提供占位
                'speech_rate': 0,
                'pitch_variance': 0,
                'volume_consistency': 0
            },
            'quality_assessment': {
                'logic_score': round(self.confidence_score * 100, 1),
                'completeness_score': 75,  # 基于回答长度等因素
                'relevance_score': 80   # 基于语义分析
            },
            'suggestions': self._generate_suggestions(),
            'raw_analysis': analysis_result
        }
    
    def _generate_suggestions(self) -> List[Dict[str, str]]:
        """生成实时建议"""
        suggestions = []
        
        # 基于当前状态生成建议
        if self.tension_level > 0.3:
            suggestions.append({
                'type': 'warning',
                'message': '检测到紧张情绪，尝试深呼吸放松'
            })
        
        if self.eye_contact_ratio < 0.6:
            suggestions.append({
                'type': 'info', 
                'message': '尝试更多地与摄像头进行眼神接触'
            })
        
        if self.head_pose_stability < 0.7:
            suggestions.append({
                'type': 'info',
                'message': '保持头部姿态稳定，避免过度摆动'
            })
        
        if self.confidence_score > 0.8:
            suggestions.append({
                'type': 'success',
                'message': '表现出色！保持当前的自信状态'
            })
        
        # 至少保证有一个建议
        if not suggestions:
            suggestions.append({
                'type': 'info',
                'message': '继续保持，表现很好！'
            })
        
        return suggestions[:3]  # 最多3个建议
    
    def _get_cached_results(self) -> Optional[Dict[str, Any]]:
        """获取缓存的分析结果"""
        if self.analysis_results:
            # 返回基于当前实时状态的格式化结果
            return self._format_realtime_result({})
        return None
    
    def reset_session(self):
        """重置会话"""
        self.frame_buffer.clear()
        self.analysis_results.clear()
        self.frame_count = 0
        self.last_analysis_time = time.time()
        
        # 重置状态
        self.current_emotion = {"dominant_emotion": "neutral", "confidence": 0.0}
        self.head_pose_stability = 0.0
        self.eye_contact_ratio = 0.0
        self.tension_level = 0.0
        self.confidence_score = 0.5
        
        logger.info("🔄 分析会话已重置")


class VideoSessionManager:
    """视频分析会话管理器"""
    
    def __init__(self):
        self.active_sessions: Dict[str, RealTimeAnalysisManager] = {}
        self.session_metadata: Dict[str, Dict] = {}
        logger.info("📹 视频会话管理器初始化完成")
    
    def create_session(self, session_id: str, user_id: str) -> RealTimeAnalysisManager:
        """创建视频分析会话"""
        
        # 检查会话是否已存在
        if session_id in self.active_sessions:
            logger.info(f"🔄 复用现有视频分析会话: {session_id}")
            return self.active_sessions[session_id]
        
        # 创建新的分析管理器
        analyzer = RealTimeAnalysisManager()
        
        self.active_sessions[session_id] = analyzer
        self.session_metadata[session_id] = {
            'user_id': user_id,
            'created_at': time.time(),
            'status': 'active'
        }
        
        logger.info(f"🎬 创建视频分析会话: {session_id}")
        return analyzer
    
    def get_session(self, session_id: str) -> Optional[RealTimeAnalysisManager]:
        """获取视频分析会话"""
        return self.active_sessions.get(session_id)
    
    def close_session(self, session_id: str):
        """关闭视频分析会话"""
        analyzer = self.active_sessions.pop(session_id, None)
        metadata = self.session_metadata.pop(session_id, None)
        
        if analyzer:
            analyzer.reset_session()
            logger.info(f"🔚 视频分析会话已关闭: {session_id}")
        else:
            logger.debug(f"🤷 会话不存在: {session_id}")
    
    def get_active_sessions(self) -> Dict[str, Dict]:
        """获取活跃会话列表"""
        return self.session_metadata.copy()


# 全局视频会话管理器
video_session_manager = VideoSessionManager()


# ==================== API路由 ====================

class CreateVideoSessionRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None

@router.post("/create-video-session")
async def create_video_session(request: CreateVideoSessionRequest):
    """创建视频分析会话"""
    try:
        # 生成会话ID
        session_id = request.session_id
        if not session_id:
            session_id = f"video_{request.user_id}_{int(time.time())}"
        
        # 创建会话
        analyzer = video_session_manager.create_session(session_id, request.user_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "status": "created",
            "message": "视频分析会话创建成功",
            "deepface_available": DEEPFACE_AVAILABLE
        }
        
    except Exception as e:
        logger.error(f"❌ 创建视频分析会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.websocket("/video-analysis/{session_id}")
async def video_analysis_websocket(websocket: WebSocket, session_id: str):
    """WebSocket视频分析端点"""
    await websocket.accept()
    logger.info(f"🔗 视频分析WebSocket连接建立: {session_id}")
    
    analyzer = video_session_manager.get_session(session_id)
    if not analyzer:
        await websocket.send_json({
            "type": "error",
            "message": "会话不存在，请先创建会话"
        })
        await websocket.close()
        return
    
    try:
        # 发送初始状态
        await websocket.send_json({
            "type": "session_ready",
            "session_id": session_id,
            "deepface_available": DEEPFACE_AVAILABLE,
            "message": "视频分析会话准备就绪"
        })
        
        while True:
            try:
                # 接收客户端数据
                data = await websocket.receive()
                
                if data.get("type") == "websocket.receive":
                    if "bytes" in data:
                        # 视频帧数据 (二进制)
                        frame_data = data["bytes"]
                        logger.debug(f"📥 收到视频帧数据: {len(frame_data)} bytes")
                        
                        # 添加帧到分析器
                        if analyzer.add_frame(frame_data):
                            # 执行分析
                            analysis_result = await analyzer.analyze_current_frame()
                            
                            if analysis_result:
                                # 发送分析结果
                                await websocket.send_json(analysis_result)
                                logger.debug("📤 发送分析结果")
                        
                    elif "text" in data:
                        # 控制指令
                        try:
                            message = json.loads(data["text"])
                            logger.debug(f"📝 收到控制指令: {message}")
                            await handle_video_control_message(analyzer, websocket, message)
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️ 收到无效JSON控制指令: {data['text'][:100]}... 错误: {e}")
                            
                elif data.get("type") == "websocket.disconnect":
                    logger.info("🔌 WebSocket客户端主动断开")
                    break
                
            except WebSocketDisconnect:
                logger.info(f"🔌 视频分析WebSocket客户端断开: {session_id}")
                break
            except Exception as e:
                logger.warning(f"⚠️ 视频分析WebSocket消息处理异常: {e}")
                break
    
    except Exception as e:
        logger.error(f"❌ 视频分析WebSocket异常: {e}")
    
    finally:
        video_session_manager.close_session(session_id)
        logger.info(f"🧹 视频分析WebSocket会话清理完成: {session_id}")


async def handle_video_control_message(analyzer: RealTimeAnalysisManager, websocket: WebSocket, message: Dict):
    """处理视频控制消息"""
    try:
        command = message.get("command")
        
        if command == "start_analysis":
            logger.info("🎬 开始视频分析")
            await websocket.send_json({
                "type": "status",
                "status": "analyzing",
                "message": "开始视频分析"
            })
        
        elif command == "stop_analysis":
            logger.info("⏹️ 停止视频分析")
            await websocket.send_json({
                "type": "status",
                "status": "stopped",
                "message": "视频分析已停止"
            })
        
        elif command == "reset_analysis":
            logger.info("🔄 重置视频分析")
            analyzer.reset_session()
            await websocket.send_json({
                "type": "status",
                "status": "reset",
                "message": "视频分析已重置"
            })
        
        elif command == "get_current_status":
            # 返回当前分析状态
            current_result = analyzer._get_cached_results()
            if current_result:
                await websocket.send_json(current_result)
        
        else:
            logger.warning(f"⚠️ 未知视频控制命令: {command}")
            
    except Exception as e:
        logger.error(f"❌ 处理视频控制消息失败: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"处理命令失败: {str(e)}"
        })


@router.delete("/video-session/{session_id}")
async def close_video_session(session_id: str):
    """关闭视频分析会话"""
    try:
        video_session_manager.close_session(session_id)
        
        return {
            "success": True,
            "message": "视频分析会话已关闭"
        }
        
    except Exception as e:
        logger.error(f"❌ 关闭视频分析会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"关闭会话失败: {str(e)}")


@router.get("/video-sessions")
async def get_video_sessions():
    """获取活跃的视频分析会话列表"""
    try:
        sessions = video_session_manager.get_active_sessions()
        
        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"❌ 获取视频会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/video-analysis-health")
async def video_analysis_health():
    """视频分析服务健康检查"""
    try:
        active_count = len(video_session_manager.active_sessions)
        
        return {
            "success": True,
            "service": "video_analysis",
            "status": "healthy",
            "active_sessions": active_count,
            "deepface_available": DEEPFACE_AVAILABLE,
            "supported_features": {
                "head_pose_analysis": True,
                "gaze_tracking": True,
                "emotion_analysis": DEEPFACE_AVAILABLE,
                "realtime_analysis": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 视频分析服务健康检查失败: {e}")
        return {
            "success": False,
            "service": "video_analysis",
            "status": "unhealthy",
            "error": str(e)
        }
