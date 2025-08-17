#!/usr/bin/env python3
"""
手动下载DeepFace模型脚本
使用代理设置解决下载卡住的问题
"""

import os
import sys
import requests
import zipfile
import tempfile
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置代理
PROXIES = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
    'all': 'socks5://127.0.0.1:7890'
}

# DeepFace模型下载地址
DEEPFACE_MODELS = {
    'retinaface.h5': 'https://github.com/serengil/deepface_models/releases/download/v1.0/retinaface.h5',
    'age_model_weights.h5': 'https://github.com/serengil/deepface_models/releases/download/v1.0/age_model_weights.h5',
    'gender_model_weights.h5': 'https://github.com/serengil/deepface_models/releases/download/v1.0/gender_model_weights.h5',
    'emotion_model_weights.h5': 'https://github.com/serengil/deepface_models/releases/download/v1.0/emotion_model_weights.h5'
}

def get_deepface_dir():
    """获取DeepFace模型目录"""
    home_dir = Path.home()
    deepface_dir = home_dir / '.deepface' / 'weights'
    deepface_dir.mkdir(parents=True, exist_ok=True)
    return deepface_dir

def download_file(url: str, filepath: Path, chunk_size: int = 8192):
    """下载文件"""
    try:
        logger.info(f"📥 开始下载: {url}")
        logger.info(f"📁 保存到: {filepath}")
        
        response = requests.get(url, proxies=PROXIES, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # 显示下载进度
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        logger.info(f"📊 下载进度: {progress:.1f}% ({downloaded}/{total_size} bytes)")
        
        logger.info(f"✅ 下载完成: {filepath.name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 下载失败 {filepath.name}: {e}")
        return False

def download_deepface_models():
    """下载所有DeepFace模型"""
    deepface_dir = get_deepface_dir()
    logger.info(f"🎯 DeepFace模型目录: {deepface_dir}")
    
    success_count = 0
    total_count = len(DEEPFACE_MODELS)
    
    for model_name, url in DEEPFACE_MODELS.items():
        filepath = deepface_dir / model_name
        
        # 检查文件是否已存在
        if filepath.exists():
            logger.info(f"✅ 模型已存在: {model_name}")
            success_count += 1
            continue
        
        # 下载模型
        if download_file(url, filepath):
            success_count += 1
    
    logger.info(f"📊 下载统计: {success_count}/{total_count} 个模型下载成功")
    
    if success_count == total_count:
        logger.info("🎉 所有DeepFace模型下载完成！")
    else:
        logger.warning(f"⚠️ 有 {total_count - success_count} 个模型下载失败")
    
    return success_count == total_count

def test_deepface_import():
    """测试DeepFace导入"""
    try:
        logger.info("🔍 测试DeepFace导入...")
        from deepface import DeepFace
        import numpy as np
        
        # 创建测试图像
        test_image = np.zeros((224, 224, 3), dtype=np.uint8)
        test_image[50:174, 50:174] = [128, 128, 128]
        
        # 测试分析
        result = DeepFace.analyze(
            test_image,
            actions=['emotion', 'age', 'gender'],
            detector_backend='retinaface',
            enforce_detection=False,
            silent=True
        )
        
        logger.info("✅ DeepFace测试成功！")
        logger.info(f"📊 测试结果: {result}")
        return True
        
    except Exception as e:
        logger.error(f"❌ DeepFace测试失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("🚀 开始DeepFace模型下载...")
    
    # 设置环境变量
    os.environ['https_proxy'] = 'http://127.0.0.1:7890'
    os.environ['http_proxy'] = 'http://127.0.0.1:7890'
    os.environ['all_proxy'] = 'socks5://127.0.0.1:7890'
    
    logger.info("🔧 代理设置:")
    logger.info(f"   HTTPS_PROXY: {os.environ.get('https_proxy')}")
    logger.info(f"   HTTP_PROXY: {os.environ.get('http_proxy')}")
    logger.info(f"   ALL_PROXY: {os.environ.get('all_proxy')}")
    
    # 下载模型
    download_success = download_deepface_models()
    
    if download_success:
        # 测试导入
        test_deepface_import()
    
    logger.info("🏁 脚本执行完成")

if __name__ == "__main__":
    main() 