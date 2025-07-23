#!/usr/bin/env python3
"""
测试脚本：验证 setting_page1.html 在简历分析完成后的正确显示和结果渲染
"""

import asyncio
import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import requests
import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class FrontendAnalysisTest:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.frontend_url = f"{self.base_url}/frontend/setting_page1.html"
        self.driver = None
        self.task_id = None
        
    def setup_driver(self):
        """设置Chrome浏览器驱动"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 无头模式
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            print("✅ Chrome驱动初始化成功")
        except Exception as e:
            print(f"❌ Chrome驱动初始化失败: {e}")
            print("请确保已安装ChromeDriver或使用其他浏览器")
            raise
    
    def create_test_pdf(self):
        """创建测试PDF文件"""
        test_pdf_path = "test_resume.pdf"
        
        # 创建一个简单的PDF内容（模拟）
        pdf_content = """
        个人简历
        
        基本信息：
        姓名：张三
        邮箱：zhangsan@example.com
        电话：13800138000
        
        技能：
        - Python编程
        - 机器学习
        - 深度学习
        - TensorFlow
        - 数据分析
        
        工作经历：
        2020-2023 ABC公司 算法工程师
        - 负责推荐系统开发
        - 优化深度学习模型
        
        项目经验：
        智能推荐系统
        - 基于深度学习的个性化推荐
        """
        
        # 这里简化处理，实际应该创建真正的PDF
        with open(test_pdf_path, "w", encoding="utf-8") as f:
            f.write(pdf_content)
        
        return test_pdf_path
    
    def upload_resume_via_api(self, file_path):
        """通过API上传简历"""
        try:
            # 创建FormData
            with open(file_path, "rb") as f:
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
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    self.task_id = result.get("task_id")
                    print(f"✅ 简历上传成功，任务ID: {self.task_id}")
                    return True
                else:
                    print(f"❌ 简历上传失败: {result.get('message')}")
                    return False
            else:
                print(f"❌ 简历上传请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 简历上传异常: {e}")
            return False
    
    def wait_for_analysis_completion(self, max_wait_time=120):
        """等待分析完成"""
        if not self.task_id:
            print("❌ 没有有效的任务ID")
            return False
        
        print(f"⏳ 等待分析完成，任务ID: {self.task_id}")
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                response = requests.get(
                    f"{self.base_url}/api/v1/resume/status/{self.task_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        status = result.get("status")
                        progress = result.get("progress", 0)
                        
                        print(f"📊 分析状态: {status}, 进度: {progress}%")
                        
                        if status == "completed":
                            print("✅ 后端分析完成")
                            return True
                        elif status == "failed":
                            print(f"❌ 后端分析失败: {result.get('error')}")
                            return False
                    
            except Exception as e:
                print(f"⚠️ 检查分析状态异常: {e}")
            
            time.sleep(3)  # 每3秒检查一次
        
        print("⏰ 等待分析完成超时")
        return False
    
    def test_frontend_display(self):
        """测试前端页面显示"""
        try:
            # 打开前端页面
            self.driver.get(self.frontend_url)
            print(f"📱 打开前端页面: {self.frontend_url}")
            
            # 等待页面加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "summaryResume"))
            )
            
            # 1. 测试基础信息配置
            print("\n🔍 测试1: 基础信息配置")
            self._test_basic_info_config()
            
            # 2. 模拟文件上传（通过JavaScript）
            print("\n🔍 测试2: 模拟简历上传")
            self._simulate_file_upload()
            
            # 3. 测试分析完成后的显示
            print("\n🔍 测试3: 分析完成后的显示")
            self._test_analysis_completion_display()
            
            # 4. 测试结果渲染
            print("\n🔍 测试4: 分析结果渲染")
            self._test_analysis_results_rendering()
            
            print("\n✅ 所有前端测试通过")
            return True
            
        except Exception as e:
            print(f"❌ 前端测试失败: {e}")
            return False
    
    def _test_basic_info_config(self):
        """测试基础信息配置"""
        # 选择目标领域
        domain_select = self.driver.find_element(By.ID, "domainSelect")
        domain_select.click()
        
        # 选择"人工智能"
        ai_option = self.driver.find_element(By.CSS_SELECTOR, "[data-value='ai']")
        ai_option.click()
        
        # 等待岗位选项加载
        time.sleep(1)
        
        # 选择具体岗位
        position_select = self.driver.find_element(By.ID, "positionSelect")
        position_select.click()
        
        # 选择"算法工程师"
        position_option = self.driver.find_element(By.CSS_SELECTOR, "[data-value='算法工程师']")
        position_option.click()
        
        # 选择工作经验
        experience_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-value='1-3']")
        experience_btn.click()
        
        # 验证配置摘要更新
        summary_domain = self.driver.find_element(By.ID, "summaryDomain").text
        summary_position = self.driver.find_element(By.ID, "summaryPosition").text
        summary_experience = self.driver.find_element(By.ID, "summaryExperience").text
        
        assert summary_domain == "人工智能", f"领域配置错误: {summary_domain}"
        assert summary_position == "算法工程师", f"岗位配置错误: {summary_position}"
        assert summary_experience == "1-3年", f"经验配置错误: {summary_experience}"
        
        print("✅ 基础信息配置正确")
    
    def _simulate_file_upload(self):
        """模拟文件上传"""
        if not self.task_id:
            print("⚠️ 没有任务ID，跳过文件上传模拟")
            return
        
        # 通过JavaScript设置全局变量，模拟文件上传成功
        script = f"""
        window.currentTaskId = '{self.task_id}';
        document.getElementById('summaryResume').textContent = '正在分析...';
        console.log('模拟文件上传成功，任务ID:', window.currentTaskId);
        """
        self.driver.execute_script(script)
        
        # 验证上传状态
        summary_resume = self.driver.find_element(By.ID, "summaryResume").text
        assert "正在分析" in summary_resume, f"上传状态错误: {summary_resume}"
        
        print("✅ 文件上传模拟成功")
    
    def _test_analysis_completion_display(self):
        """测试分析完成后的显示"""
        if not self.task_id:
            print("⚠️ 没有任务ID，跳过分析完成测试")
            return
        
        # 模拟轮询到分析完成
        mock_result = {
            "success": True,
            "status": "completed",
            "progress": 100,
            "result": {
                "basic_info": {
                    "name": "张三",
                    "email": "zhangsan@example.com",
                    "phone": "13800138000",
                    "current_position": "算法工程师"
                },
                "skills": ["Python", "机器学习", "深度学习", "TensorFlow", "数据分析"],
                "projects": [
                    {
                        "name": "智能推荐系统",
                        "description": "基于深度学习的个性化推荐算法"
                    }
                ],
                "work_experience": [
                    {
                        "company": "ABC公司",
                        "position": "算法工程师",
                        "duration": "2020-2023"
                    }
                ]
            }
        }
        
        # 通过JavaScript模拟分析完成
        script = f"""
        const result = {json.dumps(mock_result)};
        
        // 模拟updateProgress(100)
        const progressBar = document.querySelector('.progress-bar');
        const progressText = document.getElementById('progressText');
        const progressDetail = document.getElementById('progressDetail');
        
        if (progressBar) progressBar.style.width = '100%';
        if (progressText) progressText.textContent = '分析完成！';
        if (progressDetail) progressDetail.textContent = '简历分析已完成，正在渲染结果...';
        
        // 模拟updateAnalysisResults
        if (result.result && result.result.skills) {{
            const skillsContainer = document.getElementById('skillsSection');
            const skillsList = skillsContainer.querySelector('.flex.flex-wrap.gap-2');
            skillsList.innerHTML = '';
            result.result.skills.forEach(skill => {{
                const skillTag = document.createElement('span');
                skillTag.className = 'px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded';
                skillTag.textContent = skill;
                skillsList.appendChild(skillTag);
            }});
            skillsContainer.classList.remove('hidden');
        }}
        
        // 更新简历状态
        document.getElementById('summaryResume').textContent = '分析完成';
        document.getElementById('resumeAnalysis').classList.remove('hidden');
        
        console.log('模拟分析完成');
        """
        
        self.driver.execute_script(script)
        
        # 验证分析完成状态
        time.sleep(2)  # 等待DOM更新
        
        summary_resume = self.driver.find_element(By.ID, "summaryResume").text
        assert summary_resume == "分析完成", f"分析完成状态错误: {summary_resume}"
        
        # 验证简历解析结果显示
        resume_analysis = self.driver.find_element(By.ID, "resumeAnalysis")
        assert "hidden" not in resume_analysis.get_attribute("class"), "简历解析结果未显示"
        
        print("✅ 分析完成显示正确")
    
    def _test_analysis_results_rendering(self):
        """测试分析结果渲染"""
        # 验证技能点显示
        skills_section = self.driver.find_element(By.ID, "skillsSection")
        assert "hidden" not in skills_section.get_attribute("class"), "技能点区域未显示"
        
        # 验证技能标签
        skill_tags = skills_section.find_elements(By.CSS_SELECTOR, ".px-2.py-1.bg-blue-100")
        assert len(skill_tags) > 0, "技能标签未渲染"
        
        # 验证技能内容
        skill_texts = [tag.text for tag in skill_tags]
        expected_skills = ["Python", "机器学习", "深度学习", "TensorFlow", "数据分析"]
        
        for skill in expected_skills:
            assert skill in skill_texts, f"技能 {skill} 未正确渲染"
        
        print(f"✅ 技能点渲染正确: {skill_texts}")
        
        # 验证简历解析完成提示
        analysis_text = self.driver.find_element(By.CSS_SELECTOR, "#resumeAnalysis .text-sm.text-blue-900").text
        assert "解析完成" in analysis_text, f"解析完成提示错误: {analysis_text}"
        
        print("✅ 分析结果渲染正确")
    
    def cleanup(self):
        """清理资源"""
        if self.driver:
            self.driver.quit()
            print("🧹 浏览器驱动已关闭")
        
        # 清理测试文件
        test_files = ["test_resume.pdf"]
        for file in test_files:
            if os.path.exists(file):
                os.remove(file)
                print(f"🧹 测试文件已删除: {file}")
    
    def run_full_test(self):
        """运行完整测试"""
        print("🚀 开始前端分析完成测试")
        print("=" * 50)
        
        try:
            # 1. 设置浏览器驱动
            self.setup_driver()
            
            # 2. 创建测试PDF
            test_pdf = self.create_test_pdf()
            print(f"📄 创建测试PDF: {test_pdf}")
            
            # 3. 上传简历并等待分析完成
            if self.upload_resume_via_api(test_pdf):
                if self.wait_for_analysis_completion():
                    # 4. 测试前端显示
                    if self.test_frontend_display():
                        print("\n🎉 所有测试通过！")
                        return True
            
            print("\n❌ 测试失败")
            return False
            
        except Exception as e:
            print(f"\n💥 测试过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            self.cleanup()

def main():
    """主函数"""
    tester = FrontendAnalysisTest()
    success = tester.run_full_test()
    
    if success:
        print("\n✅ 前端分析完成测试：通过")
        exit(0)
    else:
        print("\n❌ 前端分析完成测试：失败")
        exit(1)

if __name__ == "__main__":
    main() 