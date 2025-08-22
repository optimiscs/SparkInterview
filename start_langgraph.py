#!/usr/bin/env python3
"""
LangGraph智能面试系统启动脚本
自动检查依赖、初始化数据库、启动服务
"""
import os
import sys
import subprocess
import asyncio
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LangGraphStarter:
    """LangGraph系统启动器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.required_dirs = [
            "data/sqlite",
            "data/checkpoints", 
            "data/cache",
            "logs"
        ]
        
    def check_dependencies(self):
        """检查Python依赖"""
        print("🔍 检查LangGraph依赖...")
        
        required_packages = [
            'langchain',
            'langgraph', 
            'langchain_community',
            'aiosqlite',
            'fastapi',
            'uvicorn'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                print(f"   ✅ {package}")
            except ImportError:
                missing_packages.append(package)
                print(f"   ❌ {package} - 缺失")
        
        if missing_packages:
            print(f"\\n⚠️ 发现缺失依赖: {', '.join(missing_packages)}")
            print("请运行以下命令安装:")
            print(f"pip install {' '.join(missing_packages)}")
            
            # 尝试自动安装
            user_input = input("\\n是否自动安装缺失依赖? (y/n): ")
            if user_input.lower() in ['y', 'yes', '是']:
                self.install_dependencies(missing_packages)
            else:
                print("❌ 请手动安装依赖后重试")
                sys.exit(1)
        else:
            print("✅ 所有依赖已安装")
    
    def install_dependencies(self, packages):
        """自动安装依赖"""
        try:
            print(f"📦 开始安装依赖: {', '.join(packages)}")
            
            # 先尝试安装LangGraph相关依赖
            cmd = [sys.executable, "-m", "pip", "install"] + packages
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 依赖安装成功")
            else:
                print(f"❌ 依赖安装失败: {result.stderr}")
                print("请手动安装依赖")
                sys.exit(1)
                
        except Exception as e:
            print(f"❌ 安装依赖时出错: {e}")
            sys.exit(1)
    
    def create_directories(self):
        """创建必要的目录"""
        print("📁 创建项目目录...")
        
        for dir_path in self.required_dirs:
            full_path = self.project_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ {dir_path}")
    
    def initialize_database(self):
        """初始化数据库"""
        print("🗄️ 初始化数据库...")
        
        try:
            # 导入数据库管理器
            sys.path.append(str(self.project_root))
            from src.database.sqlite_manager import db_manager
            
            # 确保用户表存在
            print("   🔧 检查用户表...")
            
            # 创建演示用户
            try:
                from src.database.sqlite_manager import db_manager
                import uuid
                import hashlib
                
                demo_user = {
                    "id": "demo-user-12345",
                    "name": "演示用户",
                    "email": "demo@test.com", 
                    "password": hashlib.sha256("demo123".encode()).hexdigest(),
                    "role": "student"
                }
                
                # 检查用户是否已存在
                existing_user = db_manager.get_user_by_id("demo-user-12345")
                if not existing_user:
                    db_manager.create_user(demo_user)
                    print("   ✅ 演示用户创建成功")
                else:
                    print("   ✅ 演示用户已存在")
                    
            except Exception as e:
                print(f"   ⚠️ 演示用户创建失败: {e}")
            
            print("✅ 数据库初始化完成")
            
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            print("请检查数据库配置")
    
    def test_langgraph_import(self):
        """测试LangGraph导入"""
        print("🧪 测试LangGraph模块...")
        
        try:
            from src.agents.langgraph_interview_agent import LangGraphInterviewAgent
            print("   ✅ LangGraph智能体模块导入成功")
            
            # 尝试创建实例
            agent = LangGraphInterviewAgent()
            print("   ✅ LangGraph智能体实例创建成功")
            
        except ImportError as e:
            print(f"   ❌ LangGraph模块导入失败: {e}")
            print("   请检查依赖安装和模块路径")
        except Exception as e:
            print(f"   ❌ LangGraph智能体创建失败: {e}")
            print("   智能体可能存在配置问题")
    
    def start_server(self, port=8000, reload=True):
        """启动FastAPI服务器"""
        print(f"🚀 启动LangGraph智能面试服务器 (端口: {port})...")
        
        try:
            import uvicorn
            
            # 启动服务器
            uvicorn.run(
                "main:app",
                host="0.0.0.0",
                port=port,
                reload=reload,
                reload_dirs=["src", "api", "frontend"],
                log_level="info"
            )
            
        except KeyboardInterrupt:
            print("\\n🛑 服务器已停止")
        except Exception as e:
            print(f"❌ 启动服务器失败: {e}")
    
    def run_tests(self):
        """运行快速测试"""
        print("🧪 运行LangGraph功能测试...")
        
        try:
            # 运行演示脚本
            result = subprocess.run([
                sys.executable, "langgraph_demo.py"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                print("✅ LangGraph功能测试通过")
                print("输出预览:")
                print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
            else:
                print(f"❌ 功能测试失败: {result.stderr}")
                
        except Exception as e:
            print(f"❌ 运行测试失败: {e}")
    
    def show_startup_info(self, port=8000):
        """显示启动信息"""
        print("\\n" + "="*60)
        print("🎉 LangGraph智能面试系统启动完成！")
        print("="*60)
        print(f"🌐 Web界面: http://localhost:{port}")
        print(f"📊 API文档: http://localhost:{port}/docs")
        print(f"🤖 LangGraph演示: http://localhost:{port}/frontend/langgraph-demo.html")
        print(f"📋 原有界面: http://localhost:{port}/frontend/interview.html")
        print("\\n🔧 API端点:")
        print("   POST /api/v1/langgraph-chat/start - 启动智能体")
        print("   POST /api/v1/langgraph-chat/message - 发送消息")
        print("   GET  /api/v1/langgraph-chat/health - 健康检查")
        print("   WebSocket /api/v1/langgraph-chat/ws/{session_id} - 实时连接")
        print("\\n💡 测试建议:")
        print("   1. 访问LangGraph演示页面进行交互测试")
        print("   2. 运行 python test_langgraph_api.py 进行API测试")
        print("   3. 查看 langgraph_demo.py 了解用法示例")
        print("="*60)


def main():
    """主函数"""
    starter = LangGraphStarter()
    
    print("🚀 LangGraph智能面试系统启动器")
    print("="*50)
    
    # 1. 检查依赖
    starter.check_dependencies()
    
    # 2. 创建目录
    starter.create_directories()
    
    # 3. 初始化数据库
    starter.initialize_database()
    
    # 4. 测试LangGraph导入
    starter.test_langgraph_import()
    
    # 5. 选择操作
    print("\\n📋 请选择操作:")
    print("1. 启动服务器")
    print("2. 运行功能测试") 
    print("3. 启动服务器并运行测试")
    print("4. 退出")
    
    try:
        choice = input("\\n请输入选择 (1-4): ").strip()
        
        if choice == "1":
            starter.show_startup_info()
            starter.start_server()
        elif choice == "2":
            starter.run_tests()
        elif choice == "3":
            # 先运行测试
            starter.run_tests()
            print("\\n" + "-"*50)
            print("测试完成，即将启动服务器...")
            time.sleep(2)
            starter.show_startup_info()
            starter.start_server()
        elif choice == "4":
            print("👋 再见！")
        else:
            print("❌ 无效选择")
            
    except KeyboardInterrupt:
        print("\\n👋 用户取消操作")
    except Exception as e:
        print(f"❌ 启动过程中出错: {e}")


if __name__ == "__main__":
    main()
