from typing import Dict, List, Optional, Tuple, Union
import dotenv
import os
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI
from openai import APIError, RateLimitError

dotenv.load_dotenv()

if os.getenv('LANGFUSE_SECRET_KEY'):
    from langfuse.openai import OpenAI
else:
    from openai import OpenAI
class OpenAIChat():
    def __init__(self, path: str = '', **kwargs) -> None:
        self.load_model(**kwargs)
        self.kwargs = kwargs

    def load_model(self, **kwargs):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _make_api_call(self, messages):
        # 去除is_verbose
        kwargs = self.kwargs.copy()
        kwargs.pop('is_verbose', None)
        try:
            return self.client.chat.completions.create(
                messages=messages,
                stream=True,
                **kwargs
            )
        except (APIError, RateLimitError) as e:
            print(f"error: {str(e)}. retry...")
            raise  # 重新抛出异常以触发重试

    def chat(self, prompt: str, history: List[dict] = [], meta_instruction:str ='') -> Tuple[str, List[dict]]:
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
            history.append({"role": "user", "content": prompt})
            history.append({"role": "assistant", "content": full_response})
            return full_response, history
        except Exception as e:
            print(f"error: {str(e)}")
            return f"error: {str(e)}", history
    
    
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
            print(f"error: {str(e)}")
            return f"error: {str(e)}"

if __name__ == '__main__':

    model = OpenAIChat(model='gpt-4o', temperature=0, stop=['\n'])
    # print(model.chat('输出一个唐诗', [])[0])
    print(model.create_assistant_completion('山重水复疑无路, 柳暗花明又一', '你是一个诗人'))
