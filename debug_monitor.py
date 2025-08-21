#!/usr/bin/env python3
"""
调试监控脚本
监控data/debug_frames目录中的调试文件
"""
import os
import time
import json
from pathlib import Path
from datetime import datetime

def monitor_debug_files():
    """监控调试文件"""
    debug_dir = Path("data/debug_frames")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🔍 开始监控调试目录: {debug_dir.absolute()}")
    print("=" * 60)
    
    processed_files = set()
    
    while True:
        try:
            # 扫描调试文件
            json_files = list(debug_dir.glob("*_analysis.json"))
            
            for json_file in json_files:
                if json_file.name not in processed_files:
                    processed_files.add(json_file.name)
                    analyze_debug_file(json_file)
            
            time.sleep(2)  # 每2秒检查一次
            
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
            break
        except Exception as e:
            print(f"❌ 监控错误: {e}")
            time.sleep(5)

def analyze_debug_file(json_file: Path):
    """分析调试文件"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📋 分析文件: {json_file.name}")
        print(f"⏰ 时间: {data['analysis_timestamp']}")
        
        # 帧信息
        frame_info = data['frame_info']
        print(f"🖼️ 帧信息: #{frame_info['frame_count']} - {frame_info['original_size']}")
        
        # 图像质量
        quality = data.get('image_quality', {})
        if quality:
            brightness = quality.get('brightness', {})
            contrast = quality.get('contrast', {})
            
            print(f"💡 亮度: {brightness.get('mean', 0):.1f} (标准差: {brightness.get('std', 0):.1f})")
            print(f"🔍 对比度: {contrast.get('laplacian_variance', 0):.1f}")
            
            issues = quality.get('potential_issues', [])
            if issues:
                print(f"⚠️ 图像问题: {', '.join(issues)}")
        
        # DeepFace结果
        deepface_result = data.get('deepface_result', {})
        if deepface_result:
            emotion = deepface_result['dominant_emotion']
            score = deepface_result['dominant_score']
            all_emotions = deepface_result.get('all_emotions', {})
            
            print(f"😊 主导情绪: {emotion} ({score:.1f}%)")
            
            # 显示所有情绪分布
            emotions_str = ", ".join([f"{k}: {v:.1f}%" for k, v in all_emotions.items()])
            print(f"📊 情绪分布: {emotions_str}")
        
        # 问题分析
        problem_analysis = data.get('problem_analysis', {})
        if problem_analysis:
            issues = problem_analysis.get('potential_issues', [])
            if issues:
                print(f"🚨 检测到问题: {', '.join(issues)}")
        
        # DeepFace配置
        config = data.get('deepface_config', {})
        if config:
            backend = config.get('detector_backend', 'unknown')
            print(f"🔧 检测器: {backend}")
        
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ 分析调试文件失败: {e}")

def list_current_debug_files():
    """列出当前的调试文件"""
    debug_dir = Path("data/debug_frames")
    if not debug_dir.exists():
        print("📁 调试目录不存在")
        return
    
    jpg_files = list(debug_dir.glob("*.jpg"))
    json_files = list(debug_dir.glob("*.json"))
    
    print(f"📁 调试目录: {debug_dir.absolute()}")
    print(f"🖼️ 图像文件: {len(jpg_files)}个")
    print(f"📄 分析文件: {len(json_files)}个")
    
    if json_files:
        print("\n最新的分析文件:")
        for json_file in sorted(json_files)[-3:]:  # 显示最新3个
            analyze_debug_file(json_file)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_current_debug_files()
    else:
        monitor_debug_files()
