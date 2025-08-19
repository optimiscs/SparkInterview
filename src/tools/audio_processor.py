# -*- encoding:utf-8 -*-
"""
音频处理和转换工具
支持多种音频格式的转换、处理和优化
"""
import os
import io
import logging
import numpy as np
from typing import Optional, Tuple, Union, BinaryIO
from pathlib import Path

# 音频处理库
try:
    import wave
    import audioop
    WAVE_AVAILABLE = True
except ImportError:
    WAVE_AVAILABLE = False
    logging.warning("⚠️ wave库不可用")

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logging.warning("⚠️ webrtcvad库不可用，语音活动检测功能受限")

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.warning("⚠️ librosa/soundfile库不可用，高级音频处理功能受限")

logger = logging.getLogger(__name__)


class AudioFormat:
    """音频格式定义"""
    
    PCM_16BIT = "pcm_16bit"
    WAV = "wav" 
    MP3 = "mp3"
    WEBM = "webm"
    OGG = "ogg"
    
    # 采样率
    SAMPLE_RATE_8K = 8000
    SAMPLE_RATE_16K = 16000
    SAMPLE_RATE_22K = 22050
    SAMPLE_RATE_44K = 44100
    SAMPLE_RATE_48K = 48000


class AudioProcessor:
    """音频处理器"""
    
    def __init__(self):
        """初始化音频处理器"""
        self.supported_formats = []
        
        if WAVE_AVAILABLE:
            self.supported_formats.extend([AudioFormat.WAV, AudioFormat.PCM_16BIT])
        
        if LIBROSA_AVAILABLE:
            self.supported_formats.extend([AudioFormat.MP3, AudioFormat.OGG])
        
        logger.info(f"🎵 音频处理器初始化完成，支持格式: {self.supported_formats}")
    
    def convert_to_pcm16(self, audio_data: Union[bytes, str, Path], 
                        source_format: str = None,
                        target_sample_rate: int = 16000) -> bytes:
        """
        转换音频到PCM 16bit格式
        
        Args:
            audio_data: 音频数据（bytes）或文件路径
            source_format: 源格式
            target_sample_rate: 目标采样率
            
        Returns:
            bytes: PCM 16bit音频数据
        """
        try:
            if isinstance(audio_data, (str, Path)):
                # 从文件读取
                return self._convert_file_to_pcm16(audio_data, target_sample_rate)
            else:
                # 处理字节数据
                return self._convert_bytes_to_pcm16(audio_data, source_format, target_sample_rate)
                
        except Exception as e:
            logger.error(f"❌ 音频转换失败: {e}")
            raise
    
    def _convert_file_to_pcm16(self, file_path: Union[str, Path], 
                              target_sample_rate: int = 16000) -> bytes:
        """从文件转换到PCM16"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {file_path}")
        
        file_ext = file_path.suffix.lower()
        
        if file_ext == '.wav':
            return self._convert_wav_to_pcm16(file_path, target_sample_rate)
        elif file_ext in ['.mp3', '.ogg', '.webm']:
            if LIBROSA_AVAILABLE:
                return self._convert_with_librosa(file_path, target_sample_rate)
            else:
                raise ValueError(f"不支持的音频格式: {file_ext}")
        else:
            raise ValueError(f"未知音频格式: {file_ext}")
    
    def _convert_wav_to_pcm16(self, file_path: Path, target_sample_rate: int) -> bytes:
        """转换WAV文件到PCM16"""
        if not WAVE_AVAILABLE:
            raise RuntimeError("wave库不可用")
        
        try:
            with wave.open(str(file_path), 'rb') as wav_file:
                # 获取音频参数
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                
                logger.info(f"📊 WAV文件信息: {sample_rate}Hz, {channels}声道, {sample_width}字节深度")
                
                # 读取音频数据
                audio_data = wav_file.readframes(frames)
                
                # 转换为单声道
                if channels > 1:
                    audio_data = audioop.tomono(audio_data, sample_width, 1, 1)
                
                # 转换为16bit
                if sample_width != 2:
                    if sample_width == 1:
                        audio_data = audioop.bias(audio_data, 1, 128)  # 8bit unsigned to signed
                        audio_data = audioop.lin2lin(audio_data, 1, 2)  # 8bit to 16bit
                    elif sample_width == 4:
                        audio_data = audioop.lin2lin(audio_data, 4, 2)  # 32bit to 16bit
                
                # 转换采样率
                if sample_rate != target_sample_rate:
                    audio_data, _ = audioop.ratecv(
                        audio_data, 2, 1, sample_rate, target_sample_rate, None
                    )
                
                logger.info(f"✅ WAV转换完成: {len(audio_data)} bytes")
                return audio_data
                
        except Exception as e:
            logger.error(f"❌ WAV转换失败: {e}")
            raise
    
    def _convert_with_librosa(self, file_path: Path, target_sample_rate: int) -> bytes:
        """使用librosa转换音频"""
        if not LIBROSA_AVAILABLE:
            raise RuntimeError("librosa库不可用")
        
        try:
            # 使用librosa加载音频
            audio_data, sample_rate = librosa.load(
                str(file_path), 
                sr=target_sample_rate, 
                mono=True
            )
            
            # 转换为16bit PCM
            audio_data = np.clip(audio_data, -1.0, 1.0)  # 限制范围
            audio_data = (audio_data * 32767).astype(np.int16)  # 转换为16bit整数
            
            # 转换为bytes
            pcm_data = audio_data.tobytes()
            
            logger.info(f"✅ Librosa转换完成: {len(pcm_data)} bytes")
            return pcm_data
            
        except Exception as e:
            logger.error(f"❌ Librosa转换失败: {e}")
            raise
    
    def _convert_bytes_to_pcm16(self, audio_data: bytes, source_format: str, 
                               target_sample_rate: int) -> bytes:
        """转换字节数据到PCM16"""
        if source_format == AudioFormat.PCM_16BIT:
            # 已经是PCM16格式，可能需要调整采样率
            return self._adjust_sample_rate(audio_data, target_sample_rate)
        
        # 其他格式转换需要更复杂的处理
        # 这里提供基础实现
        return audio_data
    
    def _adjust_sample_rate(self, pcm_data: bytes, target_sample_rate: int,
                           source_sample_rate: int = 16000) -> bytes:
        """调整PCM数据的采样率"""
        if source_sample_rate == target_sample_rate:
            return pcm_data
        
        if not WAVE_AVAILABLE:
            logger.warning("⚠️ 无法调整采样率，返回原始数据")
            return pcm_data
        
        try:
            converted_data, _ = audioop.ratecv(
                pcm_data, 2, 1, source_sample_rate, target_sample_rate, None
            )
            return converted_data
            
        except Exception as e:
            logger.error(f"❌ 采样率调整失败: {e}")
            return pcm_data
    
    def normalize_audio(self, audio_data: bytes) -> bytes:
        """音频归一化"""
        if not WAVE_AVAILABLE:
            return audio_data
        
        try:
            # 计算最大值
            max_val = audioop.max(audio_data, 2)
            if max_val == 0:
                return audio_data
            
            # 计算归一化因子
            target_max = 32767 * 0.8  # 避免过度归一化
            factor = target_max / max_val
            
            if factor < 1.0:  # 只在需要时进行归一化
                normalized = audioop.mul(audio_data, 2, factor)
                logger.debug(f"🔧 音频归一化: factor={factor:.2f}")
                return normalized
            
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ 音频归一化失败: {e}")
            return audio_data
    
    def remove_silence(self, audio_data: bytes, sample_rate: int = 16000) -> bytes:
        """移除静音片段"""
        if not VAD_AVAILABLE:
            logger.warning("⚠️ VAD库不可用，跳过静音移除")
            return audio_data
        
        try:
            # 使用WebRTC VAD
            vad = webrtcvad.Vad(2)  # 中等敏感度
            
            # 分帧处理（20ms帧）
            frame_duration = 20  # ms
            frame_size = int(sample_rate * frame_duration / 1000) * 2  # 2 bytes per sample
            
            output_data = b''
            
            for i in range(0, len(audio_data), frame_size):
                frame = audio_data[i:i + frame_size]
                
                if len(frame) == frame_size:
                    # 检测语音活动
                    if vad.is_speech(frame, sample_rate):
                        output_data += frame
                else:
                    # 保留不完整的最后一帧
                    output_data += frame
            
            reduction = (len(audio_data) - len(output_data)) / len(audio_data) * 100
            logger.info(f"🔇 静音移除完成，压缩率: {reduction:.1f}%")
            
            return output_data
            
        except Exception as e:
            logger.error(f"❌ 静音移除失败: {e}")
            return audio_data
    
    def split_audio_chunks(self, audio_data: bytes, chunk_duration: float = 1.0,
                          sample_rate: int = 16000) -> list:
        """将音频分割为块"""
        try:
            chunk_size = int(sample_rate * chunk_duration * 2)  # 2 bytes per sample
            chunks = []
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) > 0:
                    chunks.append(chunk)
            
            logger.info(f"🔪 音频分割完成: {len(chunks)}块")
            return chunks
            
        except Exception as e:
            logger.error(f"❌ 音频分割失败: {e}")
            return [audio_data]
    
    def validate_audio_quality(self, audio_data: bytes, sample_rate: int = 16000) -> dict:
        """验证音频质量"""
        try:
            quality_info = {
                "size_bytes": len(audio_data),
                "duration_seconds": len(audio_data) / (sample_rate * 2),
                "is_valid": True,
                "warnings": []
            }
            
            # 基本长度检查
            if len(audio_data) < 1024:  # 少于1KB
                quality_info["warnings"].append("音频数据太短")
            
            # 检查是否为有效PCM
            if len(audio_data) % 2 != 0:
                quality_info["warnings"].append("音频数据长度不是偶数（可能不是16bit PCM）")
                quality_info["is_valid"] = False
            
            # 检查音量
            if WAVE_AVAILABLE:
                try:
                    max_val = audioop.max(audio_data, 2)
                    avg_val = audioop.avg(audio_data, 2)
                    
                    quality_info["max_amplitude"] = max_val
                    quality_info["avg_amplitude"] = avg_val
                    
                    if max_val < 1000:  # 音量太小
                        quality_info["warnings"].append("音频音量过低")
                    elif max_val > 30000:  # 音量太大
                        quality_info["warnings"].append("音频音量过高，可能失真")
                    
                except:
                    pass
            
            return quality_info
            
        except Exception as e:
            logger.error(f"❌ 音频质量检查失败: {e}")
            return {"is_valid": False, "error": str(e)}
    
    def save_pcm_as_wav(self, pcm_data: bytes, output_path: Union[str, Path],
                       sample_rate: int = 16000, channels: int = 1) -> bool:
        """将PCM数据保存为WAV文件"""
        if not WAVE_AVAILABLE:
            logger.error("❌ wave库不可用，无法保存WAV文件")
            return False
        
        try:
            with wave.open(str(output_path), 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16bit = 2 bytes
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_data)
            
            logger.info(f"💾 PCM数据已保存为WAV: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存WAV文件失败: {e}")
            return False


class RealTimeAudioProcessor:
    """实时音频处理器"""
    
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1024):
        """
        初始化实时音频处理器
        
        Args:
            sample_rate: 采样率
            chunk_size: 处理块大小
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_buffer = b''
        self.processor = AudioProcessor()
        
        # VAD检测器
        self.vad = None
        if VAD_AVAILABLE:
            self.vad = webrtcvad.Vad(2)
        
        logger.info(f"🔄 实时音频处理器初始化: {sample_rate}Hz, chunk={chunk_size}")
    
    def process_chunk(self, audio_chunk: bytes) -> dict:
        """处理音频块"""
        try:
            # 添加到缓冲区
            self.audio_buffer += audio_chunk
            
            result = {
                "processed_chunks": [],
                "has_speech": False,
                "buffer_size": len(self.audio_buffer)
            }
            
            # 处理完整的块
            while len(self.audio_buffer) >= self.chunk_size:
                chunk = self.audio_buffer[:self.chunk_size]
                self.audio_buffer = self.audio_buffer[self.chunk_size:]
                
                # 归一化
                normalized_chunk = self.processor.normalize_audio(chunk)
                
                # 语音活动检测
                has_speech = self._detect_speech(normalized_chunk)
                
                result["processed_chunks"].append({
                    "data": normalized_chunk,
                    "has_speech": has_speech,
                    "size": len(normalized_chunk)
                })
                
                if has_speech:
                    result["has_speech"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 实时音频处理失败: {e}")
            return {"error": str(e)}
    
    def _detect_speech(self, audio_chunk: bytes) -> bool:
        """检测语音活动"""
        if not self.vad or len(audio_chunk) < 640:  # VAD需要至少20ms的数据
            return True  # 默认认为有语音
        
        try:
            # 确保块大小正确（20ms = 320 samples = 640 bytes）
            if len(audio_chunk) != 640:
                return True
            
            return self.vad.is_speech(audio_chunk, self.sample_rate)
            
        except Exception as e:
            logger.debug(f"VAD检测失败: {e}")
            return True
    
    def flush_buffer(self) -> bytes:
        """清空缓冲区并返回剩余数据"""
        remaining = self.audio_buffer
        self.audio_buffer = b''
        return remaining
    
    def get_buffer_duration(self) -> float:
        """获取缓冲区持续时间（秒）"""
        return len(self.audio_buffer) / (self.sample_rate * 2)


# 工具函数
def detect_audio_format(file_path: Union[str, Path]) -> str:
    """检测音频文件格式"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    ext = file_path.suffix.lower()
    
    format_map = {
        '.wav': AudioFormat.WAV,
        '.mp3': AudioFormat.MP3,
        '.ogg': AudioFormat.OGG,
        '.webm': AudioFormat.WEBM,
        '.pcm': AudioFormat.PCM_16BIT
    }
    
    return format_map.get(ext, "unknown")


def create_silence(duration_seconds: float, sample_rate: int = 16000) -> bytes:
    """创建静音数据"""
    sample_count = int(duration_seconds * sample_rate)
    return b'\x00\x00' * sample_count  # 16bit静音


def mix_audio(audio1: bytes, audio2: bytes, ratio1: float = 0.5, ratio2: float = 0.5) -> bytes:
    """混合两个音频"""
    if not WAVE_AVAILABLE:
        logger.warning("⚠️ wave库不可用，返回第一个音频")
        return audio1
    
    try:
        # 确保长度一致
        min_length = min(len(audio1), len(audio2))
        audio1 = audio1[:min_length]
        audio2 = audio2[:min_length]
        
        # 混合音频
        mixed = audioop.add(audio1, audio2, 2)
        
        # 应用比例
        if ratio1 != 1.0:
            audio1 = audioop.mul(audio1, 2, ratio1)
        if ratio2 != 1.0:
            audio2 = audioop.mul(audio2, 2, ratio2)
        
        mixed = audioop.add(audio1, audio2, 2)
        
        return mixed
        
    except Exception as e:
        logger.error(f"❌ 音频混合失败: {e}")
        return audio1


# 使用示例
if __name__ == "__main__":
    # 测试音频处理器
    processor = AudioProcessor()
    
    # 测试文件转换（如果有测试文件）
    # pcm_data = processor.convert_to_pcm16("test.wav")
    # quality = processor.validate_audio_quality(pcm_data)
    # print(f"音频质量: {quality}")
    
    # 测试实时处理器
    realtime_processor = RealTimeAudioProcessor()
    
    # 模拟音频块处理
    test_chunk = create_silence(0.1)  # 100ms静音
    result = realtime_processor.process_chunk(test_chunk)
    print(f"实时处理结果: {result}")
