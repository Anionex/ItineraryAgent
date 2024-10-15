from typing import Dict, List, Optional, Tuple, Union
import dotenv
import os
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI, AsyncOpenAI
from openai import APIError, RateLimitError

dotenv.load_dotenv()

class BaseModel:
    def __init__(self, path: str = '') -> None:
        self.path = path

    def chat(self, prompt: str, history: List[dict]):
        pass

    def load_model(self):
        pass
    
# if os.getenv('LANGFUSE_SECRET_KEY'):
#     from langfuse.openai import OpenAI
# else:
#     from openai import OpenAI
from openai import OpenAI, AsyncOpenAI
class OpenAIChat(BaseModel):
    def __init__(self, path: str = '', **kwargs) -> None:
        super().__init__(path)
        self.load_model(**kwargs)
        self.kwargs = kwargs

    def load_model(self, **kwargs):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
        )
        self.async_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _make_api_call(self, messages):
        try:
            return self.client.chat.completions.create(
                messages=messages,
                stream=True,
                **self.kwargs
            )
        except (APIError, RateLimitError) as e:
            print(f"API调用出错: {str(e)}. 正在重试...")
            raise  # 重新抛出异常以触发重试

    def chat(self, prompt: str, history: List[dict], meta_instruction:str ='') -> Tuple[str, List[dict]]:
        """
        normal chat
        """
        is_verbose = self.kwargs.get('is_verbose', False)
        messages = []
        if meta_instruction:
            messages.append({"role": "system", "content": meta_instruction})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self._make_api_call(messages)
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    if is_verbose:
                        print(chunk.choices[0].delta.content, end="")
                    full_response += chunk.choices[0].delta.content
            if is_verbose:
                print()
            return full_response, history
        except Exception as e:
            print(f"聊天过程中发生错误: {str(e)}")
            return f"抱歉,发生了错误: {str(e)}", history
    
    """
    异步版本的聊天函数
    """
    async def achat(self, prompt: str, history: List[dict], meta_instruction:str ='') -> Tuple[str, List[dict]]:

        messages = []
        if meta_instruction:
            messages.append({"role": "system", "content": meta_instruction})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        response = await self.async_client.chat.completions.create(
            messages=messages,
            **self.kwargs
        )
        
        return response.choices[0].message.content, history
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def create_assistant_completion(self, scratchpad:str, meta_instruction:str ='') -> str:
        """
        just get the ai's completion of its own response
        """
        is_verbose = self.kwargs.get('is_verbose', False)
        messages = []
        if meta_instruction:
            messages.append({"role": "system", "content": meta_instruction})
        messages.append({"role": "assistant", "content": scratchpad})
        
        try:
            response = self._make_api_call(messages)
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    if is_verbose:
                        print(chunk.choices[0].delta.content, end="")
                    full_response += chunk.choices[0].delta.content
            if is_verbose:
                print()
            return full_response
        except Exception as e:
            print(f"创建助手完成时发生错误: {str(e)}")
            return f"抱歉,发生了错误: {str(e)}"

if __name__ == '__main__':

    model = OpenAIChat(model='gpt-4o', temperature=0, stop=['\n'])
    # print(model.chat('输出一个唐诗', [])[0])
    print(model.create_assistant_completion('山重水复疑无路, 柳暗花明又一', '你是一个诗人'))
