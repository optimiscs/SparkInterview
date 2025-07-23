#!/usr/bin/env python3
"""
简化版测试脚本：验证简历分析完成后的API响应和前端逻辑
"""

import json
import time
import requests
import os
from datetime import datetime

class SimpleAnalysisTest:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.task_id = None
        
    def create_test_pdf(self):
        """创建测试PDF文件"""
        test_pdf_path = "test_resume_simple.pdf"
        
        # 创建一个简单的PDF内容（模拟）
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n"
            b"<<\n"
            b"/Type /Catalog\n"
            b"/Pages 2 0 R\n"
            b">>\n"
            b"endobj\n\n"
            b"2 0 obj\n"
            b"<<\n"
            b"/Type /Pages\n"
            b"/Kids [3 0 R]\n"
            b"/Count 1\n"
            b">>\n"
            b"endobj\n\n"
            b"3 0 obj\n"
            b"<<\n"
            b"/Type /Page\n"
            b"/Parent 2 0 R\n"
            b"/MediaBox [0 0 612 792]\n"
            b"/Contents 4 0 R\n"
            b">>\n"
            b"endobj\n\n"
            b"4 0 obj\n"
            b"<<\n"
            b"/Length 44\n"
            b">>\n"
            b"stream\n"
            b"BT\n"
            b"/F1 12 Tf\n"
            b"72 720 Td\n"
            b"(Test Resume - Python Engineer) Tj\n"
            b"ET\n"
            b"endstream\n"
            b"endobj\n\n"
            b"xref\n"
            b"0 5\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000206 00000 n \n"
            b"trailer\n"
            b"<<\n"
            b"/Size 5\n"
            b"/Root 1 0 R\n"
            b">>\n"
            b"startxref\n"
            b"299\n"
            b"%%EOF"
        )
        
        with open(test_pdf_path, "wb") as f:
            f.write(pdf_content)
        
        return test_pdf_path
    
    def test_upload_resume(self):
        """测试简历上传"""
        print("🔍 测试1: 简历上传")
        
        test_pdf = self.create_test_pdf()
        
        try:
            with open(test_pdf, "rb") as f:
                files = {"file": ("test_resume.pdf", f, "application/pdf")}
                data = {
                    "domain": "人工智能",
                    "position": "算法工程师", 
                    "experience": "1-3年"
                }
                
                response = requests.post(
                    f"{self.base_url}/api/v1/resume/upload",
                    files=files,
                    data=data,
                    timeout=30
                )
            
            print(f"📤 上传响应状态: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📤 上传响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                if result.get("success"):
                    self.task_id = result.get("task_id")
                    print(f"✅ 简历上传成功，任务ID: {self.task_id}")
                    return True
                else:
                    print(f"❌ 简历上传失败: {result.get('message')}")
                    return False
            else:
                print(f"❌ 简历上传请求失败: {response.status_code}")
                print(f"响应内容: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 简历上传异常: {e}")
            return False
        finally:
            if os.path.exists(test_pdf):
                os.remove(test_pdf)
    
    def test_analysis_status_polling(self):
        """测试分析状态轮询"""
        print("\n🔍 测试2: 分析状态轮询")
        
        if not self.task_id:
            print("❌ 没有有效的任务ID")
            return False
        
        max_attempts = 40  # 最多等待2分钟
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = requests.get(
                    f"{self.base_url}/api/v1/resume/status/{self.task_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"📊 轮询 {attempt+1}: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    
                    if result.get("success"):
                        status = result.get("status")
                        progress = result.get("progress", 0)
                        
                        if status == "completed":
                            print("✅ 后端分析完成")
                            self.final_result = result
                            return True
                        elif status == "failed":
                            print(f"❌ 后端分析失败: {result.get('error')}")
                            return False
                        else:
                            print(f"⏳ 分析进行中: {status}, 进度: {progress}%")
                    
                else:
                    print(f"⚠️ 状态查询失败: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠️ 轮询异常: {e}")
            
            attempt += 1
            time.sleep(3)
        
        print("⏰ 轮询超时")
        return False
    
    def test_analysis_result_retrieval(self):
        """测试分析结果获取"""
        print("\n🔍 测试3: 分析结果获取")
        
        if not self.task_id:
            print("❌ 没有有效的任务ID")
            return False
        
        try:
            # 测试通过 /json/{task_id} 接口获取结果
            response = requests.get(
                f"{self.base_url}/api/v1/resume/json/{self.task_id}",
                timeout=10
            )
            
            print(f"📥 结果获取响应状态: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📥 结果内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                if result.get("success") and result.get("data"):
                    analysis_data = result["data"]
                    
                    # 验证分析结果结构
                    required_fields = ["basic_info", "skills", "work_experience", "projects"]
                    missing_fields = []
                    
                    for field in required_fields:
                        if field not in analysis_data:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        print(f"⚠️ 缺少字段: {missing_fields}")
                    else:
                        print("✅ 分析结果结构完整")
                    
                    # 验证具体内容
                    if analysis_data.get("skills"):
                        print(f"🔧 识别技能: {analysis_data['skills']}")
                    
                    if analysis_data.get("basic_info"):
                        basic_info = analysis_data["basic_info"]
                        print(f"👤 基本信息: 姓名={basic_info.get('name')}, 邮箱={basic_info.get('email')}")
                    
                    if analysis_data.get("projects"):
                        projects = analysis_data["projects"]
                        print(f"📋 项目数量: {len(projects)}")
                        for i, project in enumerate(projects[:3]):  # 只显示前3个
                            print(f"   项目{i+1}: {project.get('name')} - {project.get('description', '')[:50]}...")
                    
                    return True
                else:
                    print(f"❌ 结果获取失败: {result.get('message')}")
                    return False
            else:
                print(f"❌ 结果获取请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 结果获取异常: {e}")
            return False
    
    def test_frontend_logic_simulation(self):
        """测试前端逻辑模拟"""
        print("\n🔍 测试4: 前端逻辑模拟")
        
        if not hasattr(self, 'final_result'):
            print("❌ 没有最终分析结果")
            return False
        
        # 模拟前端 pollAnalysisStatus 函数的逻辑
        result = self.final_result
        
        print("🖥️ 模拟前端处理逻辑:")
        
        if result.get("success"):
            if result.get("status") == "completed":
                print("   ✅ 检测到分析完成状态")
                
                # 模拟 updateProgress(100)
                progress = 100
                print(f"   📊 更新进度条: {progress}%")
                
                # 模拟更新进度文本
                progress_text = "分析完成！"
                progress_detail = "简历分析已完成，正在渲染结果..."
                print(f"   📝 进度文本: {progress_text}")
                print(f"   📝 详细信息: {progress_detail}")
                
                # 模拟 updateAnalysisResults
                analysis_data = result.get("result")
                if analysis_data:
                    print("   🎨 开始渲染分析结果:")
                    
                    # 模拟技能点渲染
                    if analysis_data.get("skills"):
                        skills = analysis_data["skills"]
                        print(f"      🔧 渲染技能标签: {len(skills)} 个技能")
                        for skill in skills[:5]:  # 显示前5个
                            print(f"         - {skill}")
                    
                    # 模拟项目经验渲染
                    if analysis_data.get("projects"):
                        projects = analysis_data["projects"]
                        print(f"      📋 渲染项目经验: {len(projects)} 个项目")
                        for project in projects[:3]:  # 显示前3个
                            print(f"         - {project.get('name', '未知项目')}")
                    
                    # 模拟基本信息更新
                    if analysis_data.get("basic_info"):
                        basic_info = analysis_data["basic_info"]
                        print(f"      👤 更新基本信息: {basic_info.get('name', '未知')}")
                    
                    print("   ✅ 分析结果渲染完成")
                else:
                    print("   ⚠️ 没有分析结果数据")
                
                # 模拟状态更新
                summary_resume_text = "分析完成"
                print(f"   📋 更新简历状态: {summary_resume_text}")
                
                # 模拟隐藏加载动画
                print("   🎭 隐藏加载动画")
                
                print("   🎉 前端处理完成")
                return True
            else:
                print(f"   ❌ 意外的状态: {result.get('status')}")
                return False
        else:
            print(f"   ❌ API响应失败: {result.get('message')}")
            return False
    
    def run_full_test(self):
        """运行完整测试"""
        print("🚀 开始简历分析完成测试")
        print("=" * 60)
        
        try:
            # 1. 测试简历上传
            if not self.test_upload_resume():
                return False
            
            # 2. 测试分析状态轮询
            if not self.test_analysis_status_polling():
                return False
            
            # 3. 测试分析结果获取
            if not self.test_analysis_result_retrieval():
                return False
            
            # 4. 测试前端逻辑模拟
            if not self.test_frontend_logic_simulation():
                return False
            
            print("\n🎉 所有测试通过！")
            return True
            
        except Exception as e:
            print(f"\n💥 测试过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """主函数"""
    print("📋 简历分析完成测试 - 简化版")
    print("测试目标: 验证分析完成后前端能正确显示成功状态并渲染结果")
    print()
    
    tester = SimpleAnalysisTest()
    success = tester.run_full_test()
    
    if success:
        print("\n✅ 测试结果: 通过")
        print("📝 总结:")
        print("   - 简历上传成功")
        print("   - 分析状态轮询正常")
        print("   - 分析结果获取正确")
        print("   - 前端逻辑模拟通过")
        print("   - setting_page1.html 应该能正确显示分析完成状态")
        exit(0)
    else:
        print("\n❌ 测试结果: 失败")
        print("请检查:")
        print("   - 后端服务是否正常运行")
        print("   - Redis服务是否启动")
        print("   - 大模型API是否可用")
        print("   - setting_page1.html 前端逻辑是否正确")
        exit(1)

if __name__ == "__main__":
    main() 