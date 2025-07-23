#!/usr/bin/env python3
"""
创建测试PDF文件
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

def create_test_pdf():
    """创建测试PDF文件"""
    
    # 创建PDF文件
    filename = "test_resume.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # 设置字体（使用默认字体）
    c.setFont("Helvetica", 12)
    
    # 添加内容
    content = [
        "莫栩",
        "算法工程师",
        "",
        "联系方式：",
        "电话：13480805647",
        "邮箱：2022302181277@whu.edu.cn",
        "地址：武汉市",
        "",
        "教育背景：",
        "武汉大学 - 网络空间安全 (2022.09 - 2026.06)",
        "本科 | GPA: 3.72/4.0",
        "",
        "工作经历：",
        "武汉大学 - 学生 (2022.09 - 2026.06)",
        "• 大模型微调的安全对齐研究",
        "• 舆情分析系统开发",
        "• 创新发明与知识产权协会副会长",
        "",
        "电商电群 - 创业者 (2023.06 - 至今)",
        "• 团队管理：组建9人跨职能团队",
        "• 效率优化：引入智能发货机器人",
        "• 规模拓展：运营七个店铺，服务超二十万用户",
        "",
        "技能专长：",
        "编程语言：Python, JavaScript, Java",
        "框架工具：PyTorch, Springboot, React, FastAPI",
        "数据库：Redis, MongoDB, MySQL",
        "其他工具：Docker, Git, Linux",
        "",
        "项目经验：",
        "大模型微调的安全对齐研究",
        "成功复现ICLR的关键结论，采用GPT-4o对目标大语言模型输出进行精细化安全性量化评估",
        "技术栈：Python, PyTorch, GPT-4o, 安全评估",
        "时间：2025.03 - 至今",
        "",
        "舆情分析系统",
        "前后端分离架构，支持实时情感分析和热点事件检测",
        "技术栈：React, FastAPI, Redis, MongoDB, Docker",
        "时间：2024.11 - 至今",
        "",
        "电商电群运营",
        "从零开始孵化并运营七个店铺，形成店群效应，C端营收突破百万",
        "技术栈：团队管理, 自动化系统, 数据分析",
        "时间：2023.06 - 至今"
    ]
    
    # 绘制内容
    y_position = height - 50
    for line in content:
        if y_position < 50:  # 如果页面空间不足，添加新页面
            c.showPage()
            c.setFont("Helvetica", 12)
            y_position = height - 50
        
        c.drawString(50, y_position, line)
        y_position -= 20
    
    # 保存PDF
    c.save()
    print(f"✅ 测试PDF文件已创建: {filename}")
    print(f"📄 文件大小: {os.path.getsize(filename)} 字节")

if __name__ == "__main__":
    create_test_pdf() 