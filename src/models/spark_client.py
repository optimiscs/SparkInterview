"""
讯飞星火大模型客户端 - 符合最新LangChain规范
基于官方兼容OpenAI的SDK，支持ChatModel接口
"""
from typing import Any, Optional, List, AsyncIterator, Dict
from langchain_core.language_models.llms import LLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration, LLMResult, Generation
from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from openai import OpenAI
import logging

from ..config.settings import spark_config

logger = logging.getLogger(__name__)


class SparkChatModel(BaseChatModel):
    """
    讯飞星火大模型LangChain Chat适配器
    符合最新LangChain BaseChatModel规范
    """
    
    model_name: str = "x1"
    temperature: float = 0.7
    max_tokens: int = 8192
    
    def __init__(self, model_name: str = "x1", **kwargs):
        super().__init__(**kwargs)
        self.model_name = model_name
        
        # 创建OpenAI客户端，使用讯飞API
        api_key = f"{spark_config.app_id}:{spark_config.api_secret}"
        base_url = "https://spark-api-open.xf-yun.com/v2/"
        
        # 使用私有属性避免Pydantic字段冲突
        object.__setattr__(self, '_client', OpenAI(
            api_key=api_key,
            base_url=base_url
        ))
        
        # 设置模型参数
        self.temperature = kwargs.get('temperature', 0.7)
        self.max_tokens = kwargs.get('max_tokens', 8192)
        
        logger.info(f"✅ 初始化Spark ChatModel: {self.model_name}")
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型标识"""
        return "spark_chat"
    
    def _convert_messages_to_api_format(self, messages: List[BaseMessage]) -> List[dict]:
        """将LangChain消息转换为API格式"""
        api_messages = []
        
        for message in messages:
            if isinstance(message, HumanMessage):
                api_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                api_messages.append({"role": "assistant", "content": message.content})
            elif isinstance(message, SystemMessage):
                api_messages.append({"role": "system", "content": message.content})
            else:
                # 降级处理未知消息类型
                api_messages.append({"role": "user", "content": str(message.content)})
        
        return api_messages
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """生成聊天回复 - 符合LangChain规范"""
        
        try:
            # 转换消息格式
            api_messages = self._convert_messages_to_api_format(messages)
            
            # 调用星火API
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=api_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
                **kwargs
            )
            
            # 构建LangChain格式的响应
            content = response.choices[0].message.content
            ai_message = AIMessage(content=content)
            
            generation = ChatGeneration(message=ai_message)
            
            return ChatResult(generations=[generation])
                
        except Exception as e:
            logger.error(f"星火模型调用失败: {e}")
            raise ValueError(f"Spark API调用失败: {e}")
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """异步生成聊天回复 - 符合LangChain规范"""
        
        try:
            # 转换消息格式
            api_messages = self._convert_messages_to_api_format(messages)
            
            # 调用星火API (同步调用，因为官方SDK不支持异步)
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=api_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
                **kwargs
            )
            
            # 构建LangChain格式的响应
            content = response.choices[0].message.content
            ai_message = AIMessage(content=content)
            
            generation = ChatGeneration(message=ai_message)
            
            return ChatResult(generations=[generation])
                
        except Exception as e:
            logger.error(f"星火模型异步调用失败: {e}")
            raise ValueError(f"Spark API异步调用失败: {e}")
    
    def _identifying_params(self) -> Dict[str, Any]:
        """返回识别模型的参数"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }


def create_spark_model(model_type: str = "chat", **kwargs) -> SparkChatModel:
    """
    创建星火ChatModel实例 - 符合LangChain规范
    
    Args:
        model_type: 模型类型配置 (chat, structured, creative)
        **kwargs: 其他模型参数
    
    Returns:
        SparkChatModel: 配置好的星火聊天模型实例
    """
    
    # 设置默认参数
    default_kwargs = {
        "temperature": 0.7,
        "max_tokens": 8192,
        "model_name": "x1"
    }
    
    # 根据用途调整参数
    if model_type == "structured":
        # 用于结构化任务，温度较低
        default_kwargs.update({
            "temperature": 0.1,
            "max_tokens": 4096
        })
    elif model_type == "creative":
        # 用于创意生成，温度较高
        default_kwargs.update({
            "temperature": 0.9,
            "max_tokens": 8192
        })
    elif model_type == "chat":
        # 用于对话，平衡设置
        default_kwargs.update({
            "temperature": 0.7,
            "max_tokens": 8192
        })
    
    # 合并用户参数
    merged_kwargs = {**default_kwargs, **kwargs}
    
    try:
        return SparkChatModel(**merged_kwargs)
    except Exception as e:
        logger.error(f"创建星火模型失败: {e}")
        raise


def create_spark_chat_model(model_type: str = "chat", **kwargs) -> SparkChatModel:
    """
    创建星火聊天模型实例（向后兼容）
    
    Args:
        model_type: 模型类型
        **kwargs: 模型参数
        
    Returns:
        SparkChatModel: 星火聊天模型实例
    """
    return create_spark_model(model_type, **kwargs) 