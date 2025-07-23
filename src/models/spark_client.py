"""
讯飞星火大模型客户端
基于官方兼容OpenAI的SDK
"""
from typing import Any, Optional, List
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from openai import OpenAI

from ..config.settings import spark_config


class SparkLLM(LLM):
    """
    讯飞星火大模型LangChain适配器
    基于官方兼容OpenAI的SDK
    """
    
    model_name: str = "x1"
    temperature: float = 0.7
    max_tokens: int = 8192
    client: Any = None
    
    def __init__(self, model_name: str = "x1", **kwargs):
        super().__init__()
        self.model_name = model_name
        
        # 创建OpenAI客户端，使用讯飞API
        # API密钥格式：app_id:api_secret
        api_key = f"{spark_config.app_id}:{spark_config.api_secret}"
        base_url = "https://spark-api-open.xf-yun.com/v2/"
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # 设置模型参数
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @property
    def _llm_type(self) -> str:
        return "spark"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """调用星火模型"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
                **kwargs
            )
            
            return response.choices[0].message.content
                
        except Exception as e:
            raise ValueError(f"Chat failed: {e}")
    
    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """异步调用"""
        return self._call(prompt, stop, run_manager, **kwargs)
    
    def chat_with_messages(self, messages: List[dict], **kwargs) -> str:
        """支持多轮对话的接口"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
                **kwargs
            )
            
            return response.choices[0].message.content
                
        except Exception as e:
            raise ValueError(f"Chat failed: {e}")


def create_spark_model(model_type: str = "ultra", **kwargs) -> SparkLLM:
    """
    创建星火模型实例
    
    Args:
        model_type: 模型类型，默认为"ultra"（响应更快）
        **kwargs: 其他模型参数
    """
    
    # 设置默认参数
    default_kwargs = {
        "temperature": 0.7,
        "max_tokens": 8192
    }
    
    # 根据用途调整参数
    if model_type == "pro":
        # 用于结构化任务，温度较低
        default_kwargs["temperature"] = 0.1
        default_kwargs["max_tokens"] = 4096
    elif model_type == "ultra":
        # 用于对话，温度适中，响应更快
        default_kwargs["temperature"] = 0.7
        default_kwargs["max_tokens"] = 8192
    elif model_type == "x1":
        # 通用版本
        default_kwargs["temperature"] = 0.7
        default_kwargs["max_tokens"] = 8192
    
    # 合并参数
    merged_kwargs = {**default_kwargs, **kwargs}
    
    return SparkLLM(model_name="x1", **merged_kwargs)


def create_spark_chat_model(model_type: str = "ultra", **kwargs) -> SparkLLM:
    """
    创建支持对话的星火模型实例（向后兼容）
    默认使用ultra版本以获得更快的响应速度
    """
    return create_spark_model(model_type, **kwargs) 