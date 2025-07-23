"""
面试官智能体 - "模拟器" 
负责主导面试对话流程，进行动态追问
使用LangChain封装好的函数实现流式处理和对话管理
"""
import time
from typing import Dict, Any, List, Optional
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

from ..models.spark_client import create_spark_chat_model
from ..models.state import InterviewState, InterviewStage, ConversationTurn
from ..tools.media_recorder import create_media_recorder


class InterviewerAgent:
    """面试官智能体"""
    
    def __init__(self):
        # 使用Spark Ultra模型 - 最佳对话体验，响应更快
        self.llm = create_spark_chat_model("ultra")
        
        # 记忆模块
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # 创建流式回调处理器
        self.streaming_handler = StreamingStdOutCallbackHandler()
        
        # 创建提示模板
        self._create_prompt_templates()
        
        # 创建对话链
        self._create_conversation_chains()
        
        # 媒体录制器
        self.media_recorder = create_media_recorder()
        
        # 面试官人设
        self.interviewer_persona = """
你是一位资深的技术面试官，拥有10年以上的技术招聘经验。你的特点：

【专业素养】
- 技术功底深厚，能够准确评估候选人的技术能力
- 善于通过行为面试法(STAR)深入了解候选人的实际经验
- 注重考察候选人的逻辑思维和解决问题的能力

【面试风格】
- 态度友好但专业，创造轻松的面试氛围
- 善于根据候选人的回答进行深入追问
- 会根据简历内容提出针对性问题
- 注重引导候选人充分展示自己的能力

【追问策略】
- 当候选人提到项目经验时，会询问具体的技术细节和个人贡献
- 对于技术概念，会要求候选人举例说明或描述实际应用
- 当回答不够深入时，会适当引导候选人更详细地阐述
- 会关注候选人在团队协作中的角色和沟通能力

请按照以上角色设定进行面试，确保每个问题都有明确的考察目标。
"""
    
    def _create_prompt_templates(self):
        """创建提示模板"""
        
        # 问题生成模板
        self.question_prompt = PromptTemplate(
            input_variables=["persona", "context", "current_question"],
            template="""
{persona}

{context}

请作为面试官，提出当前问题。你可以：
1. 直接提出问题
2. 根据之前的对话适当调整问题的表述
3. 在提问前简短地过渡一下话题

当前问题: {current_question}

面试官说:
"""
        )
        
        # 追问生成模板
        self.followup_prompt = PromptTemplate(
            input_variables=["persona", "context", "original_question", "answer"],
            template="""
{persona}

{context}

候选人刚刚回答了问题: "{original_question}"

候选人的回答: "{answer}"

请分析这个回答，如果需要追问以获得更多细节或澄清，请生成一个合适的追问问题。
追问应该：
1. 针对回答中提到的具体项目或技术
2. 要求候选人提供更多技术细节
3. 了解候选人在项目中的具体角色和贡献
4. 探索候选人的思考过程

如果回答已经足够详细和完整，请回复"无需追问"。

追问问题:
"""
        )
    
    def _create_conversation_chains(self):
        """创建对话链"""
        
        # 问题生成链
        self.question_chain = (
            {"persona": lambda x: self.interviewer_persona, 
             "context": RunnablePassthrough(), 
             "current_question": RunnablePassthrough()}
            | self.question_prompt
            | self.llm
            | StrOutputParser()
        )
        
        # 追问生成链
        self.followup_chain = (
            {"persona": lambda x: self.interviewer_persona,
             "context": RunnablePassthrough(),
             "original_question": RunnablePassthrough(),
             "answer": RunnablePassthrough()}
            | self.followup_prompt
            | self.llm
            | StrOutputParser()
        )
    
    def _build_interview_context(self, state: InterviewState) -> str:
        """构建面试上下文"""
        
        user_info = state["user_info"]
        questions = state["questions"]
        current_index = state["current_question_index"]
        
        # 简历摘要
        resume_summary = user_info.resume_summary.get("summary", "无简历信息")
        
        # 当前问题
        current_question = None
        if current_index < len(questions):
            current_question = questions[current_index]
        
        # 对话历史
        conversation_history = state["conversation_history"]
        
        context = f"""
【面试信息】
- 候选人姓名: {user_info.name}
- 应聘岗位: {user_info.target_position}
- 技术领域: {user_info.target_field}

【简历摘要】
{resume_summary}

【当前问题】
"""
        
        if current_question:
            context += f"问题 {current_index + 1}: {current_question.text}\n"
            context += f"问题类型: {current_question.type.value}\n"
            context += f"考察重点: {', '.join(current_question.expected_keywords)}\n"
        else:
            context += "所有预设问题已完成，可以进行总结或额外提问。\n"
        
        # 添加对话历史
        if conversation_history:
            context += "\n【对话历史】\n"
            for i, turn in enumerate(conversation_history[-3:]):  # 只显示最近3轮
                context += f"Q{i+1}: {turn.question}\n"
                context += f"A{i+1}: {turn.answer[:200]}...\n\n"
        
        return context
    
    def _should_ask_follow_up(self, answer: str, question_keywords: List[str]) -> bool:
        """判断是否需要追问"""
        
        # 检查回答长度
        if len(answer.strip()) < 50:
            return True
        
        # 检查是否包含关键词
        answer_lower = answer.lower()
        keyword_matches = sum(1 for keyword in question_keywords 
                            if keyword.lower() in answer_lower)
        
        # 如果关键词匹配度低，需要追问
        if len(question_keywords) > 0 and keyword_matches / len(question_keywords) < 0.3:
            return True
        
        # 检查是否包含具体细节
        detail_indicators = ["具体", "比如", "例如", "实现", "使用", "采用", "负责"]
        if not any(indicator in answer for indicator in detail_indicators):
            return True
        
        return False
    
    def _generate_follow_up_question(
        self, 
        original_question: str, 
        answer: str, 
        context: str
    ) -> Optional[str]:
        """生成追问问题 - 使用LangChain流式处理"""
        
        try:
            # 使用LangChain的追问链
            response = self.followup_chain.invoke({
                "context": context,
                "original_question": original_question,
                "answer": answer
            })
            
            if "无需追问" in response or "不需要追问" in response:
                return None
            
            return response.strip()
            
        except Exception as e:
            print(f"生成追问问题失败: {str(e)}")
            return None
    
    def ask_question(self, state: InterviewState) -> Dict[str, Any]:
        """提出问题 - 使用LangChain流式处理"""
        
        try:
            questions = state["questions"]
            current_index = state["current_question_index"]
            
            # 检查是否还有问题
            if current_index >= len(questions):
                return {
                    "question": "感谢您的时间，面试问题已经全部完成。请问您还有什么想了解的吗？",
                    "question_id": "final",
                    "is_final": True
                }
            
            # 获取当前问题
            current_question = questions[current_index]
            
            # 构建上下文
            context = self._build_interview_context(state)
            
            # 使用LangChain的问题生成链
            response = self.question_chain.invoke({
                "context": context,
                "current_question": current_question.text
            })
            
            return {
                "question": response.strip(),
                "question_id": current_question.id,
                "question_type": current_question.type.value,
                "expected_keywords": current_question.expected_keywords,
                "is_final": False
            }
            
        except Exception as e:
            error_msg = f"生成问题失败: {str(e)}"
            print(f"❌ {error_msg}")
            
            # 返回备用问题
            return {
                "question": "请简单介绍一下您的技术背景和项目经验。",
                "question_id": "backup",
                "question_type": "behavioral",
                "expected_keywords": [],
                "is_final": False
            }
    
    def process_answer(
        self, 
        state: InterviewState, 
        question_data: Dict[str, Any], 
        answer: str
    ) -> Dict[str, Any]:
        """处理候选人的回答"""
        
        try:
            # 记录对话
            conversation_turn = ConversationTurn(
                question_id=question_data["question_id"],
                question=question_data["question"],
                answer=answer,
                timestamp=time.time()
            )
            
            state["conversation_history"].append(conversation_turn)
            
            # 判断是否需要追问
            should_follow_up = self._should_ask_follow_up(
                answer, 
                question_data.get("expected_keywords", [])
            )
            
            follow_up_question = None
            if should_follow_up and not question_data.get("is_final", False):
                context = self._build_interview_context(state)
                follow_up_question = self._generate_follow_up_question(
                    question_data["question"],
                    answer,
                    context
                )
            
            result = {
                "answer_recorded": True,
                "follow_up_question": follow_up_question,
                "should_continue": True
            }
            
            # 如果没有追问，移动到下一个问题
            if not follow_up_question:
                state["current_question_index"] += 1
                
                # 检查是否所有问题已完成
                if state["current_question_index"] >= len(state["questions"]):
                    result["should_continue"] = False
                    result["interview_completed"] = True
            
            return result
            
        except Exception as e:
            error_msg = f"处理回答失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            
            return {
                "answer_recorded": False,
                "follow_up_question": None,
                "should_continue": False,
                "error": error_msg
            }
    
    def conduct_interview(self, state: InterviewState) -> InterviewState:
        """执行完整的面试流程 - 使用LangChain流式处理"""
        
        print("🎤 开始模拟面试...")
        print("=" * 50)
        
        # 开始录制音视频
        try:
            session_id = state.get("session_id", "unknown")
            video_path, audio_path = self.media_recorder.start_recording(session_id)
            state["video_path"] = video_path
            state["audio_path"] = audio_path
            print("🎥 音视频录制已启动")
        except Exception as e:
            print(f"⚠️ 音视频录制启动失败: {e}")
            state["video_path"] = None
            state["audio_path"] = None
        
        try:
            while True:
                # 1. 提出问题
                question_data = self.ask_question(state)
                
                # 使用LangChain流式输出面试官问题
                print(f"\n🤵 面试官: ", end="", flush=True)
                self._stream_question(question_data['question'])
                print()
                
                # 2. 等待用户输入回答
                answer = input("\n👤 您的回答: ").strip()
                
                if not answer:
                    print("请提供您的回答。")
                    continue
                
                # 检查是否要终止面试
                if answer.lower() in ["终止面试", "结束面试", "停止面试", "quit", "exit", "stop"]:
                    print("\n⏹️ 用户主动终止面试")
                    state["stage"] = InterviewStage.ANALYSIS
                    state["errors"].append("用户主动终止面试")
                    return state
                
                # 3. 处理回答
                result = self.process_answer(state, question_data, answer)
                
                if not result["answer_recorded"]:
                    print(f"❌ {result.get('error', '处理回答时出错')}")
                    continue
                
                # 4. 检查是否有追问
                if result.get("follow_up_question"):
                    # 使用LangChain流式输出追问问题
                    print(f"\n🤵 面试官: ", end="", flush=True)
                    self._stream_question(result['follow_up_question'])
                    print()
                    
                    # 等待追问回答
                    follow_up_answer = input("\n👤 您的回答: ").strip()
                    
                    # 检查是否要终止面试
                    if follow_up_answer.lower() in ["终止面试", "结束面试", "停止面试", "quit", "exit", "stop"]:
                        print("\n⏹️ 用户主动终止面试")
                        state["stage"] = InterviewStage.ANALYSIS
                        state["errors"].append("用户主动终止面试")
                        return state
                    
                    if follow_up_answer:
                        # 记录追问对话
                        follow_up_turn = ConversationTurn(
                            question_id=f"{question_data['question_id']}_followup",
                            question=result['follow_up_question'],
                            answer=follow_up_answer,
                            timestamp=time.time()
                        )
                        state["conversation_history"].append(follow_up_turn)
                        
                        # 移动到下一个问题
                        state["current_question_index"] += 1
                
                # 5. 检查是否完成
                if not result.get("should_continue", True):
                    break
                
                # 6. 检查是否所有问题完成
                if state["current_question_index"] >= len(state["questions"]):
                    break
            
            # 面试完成
            state["stage"] = InterviewStage.ANALYSIS
            print("\n✅ 面试完成！正在进行分析...")
            
            # 停止录制
            self.media_recorder.stop_recording()
            
            return state
            
        except KeyboardInterrupt:
            print("\n\n⏹️ 面试被中断")
            state["errors"].append("面试被用户中断")
            # 停止录制
            self.media_recorder.stop_recording()
            return state
        
        except Exception as e:
            error_msg = f"面试过程中出错: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            # 停止录制
            self.media_recorder.stop_recording()
            return state
    
    def _stream_question(self, question: str):
        """使用LangChain流式输出问题"""
        try:
            # 创建带流式回调的LLM
            streaming_llm = self.llm.bind(callbacks=[self.streaming_handler])
            
            # 直接输出问题（模拟流式效果）
            for char in question:
                print(char, end="", flush=True)
                time.sleep(0.02)  # 稍微快一点的打字效果
                
        except Exception as e:
            # 如果流式输出失败，回退到普通输出
            print(question, end="", flush=True)


def create_interviewer_agent() -> InterviewerAgent:
    """创建面试官智能体实例"""
    return InterviewerAgent() 