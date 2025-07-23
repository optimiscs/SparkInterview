"""
媒体录制工具
用于录制面试过程中的音视频
优化FFmpeg警告处理
"""
import cv2
import pyaudio
import wave
import threading
import time
import os
import logging
from typing import Optional, Tuple
from pathlib import Path

# 配置OpenCV日志级别，减少FFmpeg警告
try:
    cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
except AttributeError:
    # 较老版本的OpenCV不支持setLogLevel
    pass


class MediaRecorder:
    """媒体录制器"""
    
    def __init__(self):
        self.video_recorder = None
        self.audio_recorder = None
        self.audio_pyaudio = None
        self.is_recording = False
        self.output_dir = Path("./data/interviews")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 视频录制参数
        self.video_fps = 30
        self.video_width = 640
        self.video_height = 480
        
        # 音频录制参数
        self.audio_channels = 1
        self.audio_rate = 16000
        self.audio_chunk = 1024
        self.audio_format = pyaudio.paInt16
        
        # 录制状态
        self.video_thread = None
        self.audio_thread = None
        self.video_path = None
        self.audio_path = None
    
    def start_recording(self, session_id: str) -> Tuple[str, str]:
        """开始录制音视频"""
        
        if self.is_recording:
            raise Exception("已经在录制中")
        
        # 生成文件路径
        timestamp = int(time.time())
        self.video_path = str(self.output_dir / f"{session_id}_video_{timestamp}.mp4")
        self.audio_path = str(self.output_dir / f"{session_id}_audio_{timestamp}.wav")
        
        # 启动录制线程
        self.is_recording = True
        
        # 启动视频录制
        self.video_thread = threading.Thread(
            target=self._record_video, 
            args=(self.video_path,),
            daemon=True
        )
        self.video_thread.start()
        
        # 启动音频录制
        self.audio_thread = threading.Thread(
            target=self._record_audio, 
            args=(self.audio_path,),
            daemon=True
        )
        self.audio_thread.start()
        
        print(f"🎥 开始录制音视频...")
        print(f"   视频文件: {self.video_path}")
        print(f"   音频文件: {self.audio_path}")
        
        return self.video_path, self.audio_path
    
    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # 等待录制线程结束
        if self.video_thread and self.video_thread.is_alive():
            self.video_thread.join(timeout=2.0)
        
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2.0)
        
        # 清理资源
        if self.video_recorder:
            try:
                self.video_recorder.release()
            except Exception as e:
                print(f"⚠️ 视频录制器释放失败: {e}")
        
        if self.audio_recorder:
            try:
                self.audio_recorder.stop_stream()
                self.audio_recorder.close()
            except Exception as e:
                print(f"⚠️ 音频录制器释放失败: {e}")
        
        if self.audio_pyaudio:
            try:
                self.audio_pyaudio.terminate()
            except Exception as e:
                print(f"⚠️ 音频PyAudio释放失败: {e}")
        
        print("⏹️ 录制已停止")
    
    def _record_video(self, video_path: str):
        """录制视频 - 优化FFmpeg警告处理"""
        cap = None
        out = None
        
        try:
            # 初始化摄像头
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("⚠️ 无法访问摄像头，跳过视频录制")
                return
            
            # 设置摄像头参数
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.video_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.video_height)
            cap.set(cv2.CAP_PROP_FPS, self.video_fps)
            
            # 尝试不同的编码器，优先使用更兼容的编码器
            codecs = ['mp4v', 'avc1', 'XVID']
            out = None
            
            for codec in codecs:
                try:
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    out = cv2.VideoWriter(
                        video_path, 
                        fourcc, 
                        self.video_fps, 
                        (self.video_width, self.video_height)
                    )
                    
                    if out.isOpened():
                        print(f"✅ 使用编码器: {codec}")
                        break
                    else:
                        out.release()
                        out = None
                except Exception:
                    continue
            
            if not out or not out.isOpened():
                print("⚠️ 无法创建视频写入器，跳过视频录制")
                return
            
            self.video_recorder = out
            
            frame_count = 0
            while self.is_recording:
                ret, frame = cap.read()
                if ret:
                    # 调整帧大小
                    frame = cv2.resize(frame, (self.video_width, self.video_height))
                    
                    # 写入帧，忽略FFmpeg警告
                    try:
                        out.write(frame)
                        frame_count += 1
                    except Exception as e:
                        # 忽略写入错误，继续录制
                        pass
                    
                    # 添加小延迟减少CPU使用
                    time.sleep(1.0 / self.video_fps)
                else:
                    break
            
            print(f"✅ 视频录制完成，共录制 {frame_count} 帧")
            
        except Exception as e:
            print(f"⚠️ 视频录制失败: {e}")
        
        finally:
            # 清理资源
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass
            
            if out:
                try:
                    out.release()
                except Exception:
                    pass
            
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
    
    def _record_audio(self, audio_path: str):
        """录制音频 - 优化错误处理"""
        audio = None
        stream = None
        
        try:
            # 初始化音频
            audio = pyaudio.PyAudio()
            self.audio_pyaudio = audio
            
            # 打开音频流
            stream = audio.open(
                format=self.audio_format,
                channels=self.audio_channels,
                rate=self.audio_rate,
                input=True,
                frames_per_buffer=self.audio_chunk
            )
            
            self.audio_recorder = stream
            
            frames = []
            chunk_count = 0
            
            while self.is_recording:
                try:
                    data = stream.read(self.audio_chunk, exception_on_overflow=False)
                    frames.append(data)
                    chunk_count += 1
                except Exception as e:
                    # 忽略音频录制错误，继续录制
                    pass
            
            # 保存音频文件
            if frames:
                try:
                    with wave.open(audio_path, 'wb') as wf:
                        wf.setnchannels(self.audio_channels)
                        wf.setsampwidth(audio.get_sample_size(self.audio_format))
                        wf.setframerate(self.audio_rate)
                        wf.writeframes(b''.join(frames))
                    
                    print(f"✅ 音频录制完成，共录制 {chunk_count} 个音频块")
                except Exception as e:
                    print(f"⚠️ 音频文件保存失败: {e}")
            
        except Exception as e:
            print(f"⚠️ 音频录制失败: {e}")
        
        finally:
            # 清理资源
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            
            if audio:
                try:
                    audio.terminate()
                except Exception:
                    pass


def create_media_recorder() -> MediaRecorder:
    """创建媒体录制器实例"""
    return MediaRecorder() 