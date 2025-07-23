"""
简历解析工具
支持PDF和Word文档的解析和结构化
"""
import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
import PyPDF2
import docx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..models.spark_client import create_spark_model


class ResumeParserInput(BaseModel):
    """简历解析工具输入"""
    file_path: str = Field(description="简历文件路径")
    extract_format: str = Field(
        default="structured", 
        description="提取格式: 'structured' 或 'summary'"
    )


class ResumeParserTool(BaseTool):
    """简历解析工具"""
    
    name: str = "resume_parser"
    description: str = """
    解析简历文件(PDF/Word)，提取结构化信息。
    输入: 文件路径
    输出: 结构化的简历信息JSON
    """
    args_schema: type = ResumeParserInput
    llm: Any = None
    
    def __init__(self):
        super().__init__()
        self.llm = create_spark_model("pro")
        
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF文件提取文本"""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            raise Exception(f"PDF解析失败: {str(e)}")
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """从Word文档提取文本"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Word文档解析失败: {str(e)}")
    
    def _extract_text(self, file_path: str) -> str:
        """根据文件类型提取文本"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.pdf':
            return self._extract_text_from_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            return self._extract_text_from_docx(file_path)
        else:
            raise Exception(f"不支持的文件格式: {file_extension}")
    
    def _structure_resume_content(self, text: str) -> Dict[str, Any]:
        """使用LLM结构化简历内容"""
        
        prompt = f"""
请分析以下简历内容，并以JSON格式输出结构化信息。

简历内容：
{text}

请按以下格式输出：
{{
    "personal_info": {{
        "name": "姓名",
        "phone": "电话",
        "email": "邮箱",
        "location": "地址"
    }},
    "education": [
        {{
            "school": "学校名称",
            "degree": "学位",
            "major": "专业",
            "graduation_year": "毕业年份"
        }}
    ],
    "work_experience": [
        {{
            "company": "公司名称",
            "position": "职位",
            "start_date": "开始时间",
            "end_date": "结束时间",
            "responsibilities": ["职责1", "职责2"]
        }}
    ],
    "projects": [
        {{
            "name": "项目名称",
            "description": "项目描述",
            "technologies": ["技术1", "技术2"],
            "role": "个人角色"
        }}
    ],
    "skills": {{
        "programming_languages": ["编程语言"],
        "frameworks": ["框架"],
        "tools": ["工具"],
        "databases": ["数据库"]
    }},
    "summary": "简历核心亮点总结"
}}

只返回JSON，不要其他内容。
"""
        
        try:
            response = self.llm(prompt)
            # 清理可能的markdown标记
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            # 如果JSON解析失败，返回基础格式
            return {
                "personal_info": {"name": "解析失败"},
                "education": [],
                "work_experience": [],
                "projects": [],
                "skills": {},
                "summary": "简历解析出现问题，请检查文件格式",
                "raw_text": text[:500]  # 保留前500字符作为备份
            }
        except Exception as e:
            raise Exception(f"简历结构化失败: {str(e)}")
    
    def _run(self, file_path: str, extract_format: str = "structured") -> str:
        """执行简历解析"""
        
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise Exception(f"文件不存在: {file_path}")
            
            # 提取文本
            raw_text = self._extract_text(file_path)
            
            if not raw_text.strip():
                raise Exception("文件内容为空或无法读取")
            
            # 结构化处理
            if extract_format == "structured":
                structured_data = self._structure_resume_content(raw_text)
                return json.dumps(structured_data, ensure_ascii=False, indent=2)
            
            elif extract_format == "summary":
                # 生成简历摘要
                summary_prompt = f"""
请为以下简历内容生成一个简洁的专业摘要，重点突出候选人的技术背景、经验和技能：

{raw_text}

摘要要求：
1. 控制在200字以内
2. 突出技术技能和项目经验
3. 适合面试官快速了解候选人
"""
                summary = self.llm(summary_prompt)
                return summary.strip()
            
            else:
                return raw_text
                
        except Exception as e:
            error_result = {
                "error": True,
                "message": str(e),
                "file_path": file_path
            }
            return json.dumps(error_result, ensure_ascii=False, indent=2)


def create_resume_parser_tool() -> ResumeParserTool:
    """创建简历解析工具实例"""
    return ResumeParserTool() 