#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
语音识别依赖安装脚本
安装语音识别功能所需的额外依赖包
"""
import subprocess
import sys
import os

def run_command(command):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def install_dependencies():
    """安装语音识别相关依赖"""
    print("🎤 开始安装语音识别依赖包...")
    
    # 语音识别相关依赖
    dependencies = [
        "websocket-client==1.8.0",
        "websockets==12.0",
        "webrtcvad==2.0.10",
    ]
    
    # 可选依赖（根据系统支持情况）
    optional_dependencies = [
        "audioop2==1.2.2",
    ]
    
    # 安装必需依赖
    print("\n📦 安装必需依赖...")
    for dep in dependencies:
        print(f"安装 {dep}...")
        success, output = run_command(f"pip install {dep}")
        if success:
            print(f"✅ {dep} 安装成功")
        else:
            print(f"❌ {dep} 安装失败: {output}")
    
    # 安装可选依赖
    print("\n📦 安装可选依赖...")
    for dep in optional_dependencies:
        print(f"尝试安装 {dep}...")
        success, output = run_command(f"pip install {dep}")
        if success:
            print(f"✅ {dep} 安装成功")
        else:
            print(f"⚠️ {dep} 安装失败（这是可选依赖，不影响基本功能）")
    
    # 检查安装结果
    print("\n🔍 检查安装结果...")
    check_imports()

def check_imports():
    """检查导入是否正常"""
    imports_to_check = [
        ("websocket", "websocket-client"),
        ("websockets", "websockets"), 
        ("webrtcvad", "webrtcvad"),
        ("wave", "built-in"),
        ("audioop", "built-in")
    ]
    
    for module_name, package_name in imports_to_check:
        try:
            __import__(module_name)
            print(f"✅ {module_name} 可以正常导入")
        except ImportError:
            if package_name == "built-in":
                print(f"⚠️ {module_name} 导入失败（内置模块，可能是Python版本问题）")
            else:
                print(f"❌ {module_name} 导入失败，请手动安装：pip install {package_name}")

def main():
    """主函数"""
    print("=" * 60)
    print("职面星火 - 语音识别依赖安装器")
    print("=" * 60)
    
    # 检查Python版本
    python_version = sys.version_info
    print(f"🐍 Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("❌ 警告: 建议使用Python 3.8或更高版本")
    
    # 检查pip版本
    success, pip_version = run_command("pip --version")
    if success:
        print(f"📦 pip版本: {pip_version.strip()}")
    else:
        print("❌ 无法获取pip版本信息")
    
    # 安装依赖
    install_dependencies()
    
    print("\n" + "=" * 60)
    print("安装完成！")
    print("=" * 60)
    print("📖 使用说明:")
    print("1. 确保你的系统支持麦克风访问")
    print("2. 在浏览器中允许网站访问麦克风")
    print("3. 启动后端服务: python main.py")
    print("4. 打开前端页面开始语音面试")
    print("")
    print("🔧 如果遇到问题:")
    print("- WebRTC VAD可能需要系统级依赖")
    print("- 某些Linux系统需要安装: sudo apt-get install libportaudio2-dev")
    print("- 某些Windows系统需要Visual C++ Build Tools")
    print("")
    print("💡 可选配置:")
    print("- 在config.env中配置讯飞语音识别的APPID和APIKey")
    print("- 调整音频采样率和处理参数")

if __name__ == "__main__":
    main()
