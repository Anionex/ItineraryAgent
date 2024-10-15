from chat_model import OpenAIChat
from prompts import PLAN_CHECKER_PROMPT
from config import *

class PlanChecker:
    def __init__(self, **kwargs) -> None: 
        kwargs['model'] = kwargs.get('model', 'gpt-4o')
        kwargs['temperature'] = kwargs.get('temperature', 0.5)
        self.kwargs = kwargs
        self.model = OpenAIChat(**kwargs)
        print("Initializing PlanChecker with model info:", kwargs)


    def build_system_input(self, query, extra_requirements):
        sys_prompt = PLAN_CHECKER_PROMPT.format(query=query, extra_requirements=extra_requirements)
        if GLOBAL_LANGUAGE != "en":
            sys_prompt += f"\n请你使用{GLOBAL_LANGUAGE}（代号）作为输出语言"
        return sys_prompt
    
    def check_plan(self, plan, query, extra_requirements=''):
        sys_prompt = self.build_system_input(query, extra_requirements)
        messages = [
            {"role": "system", "content": sys_prompt},
        ]
        response = self.model.chat(prompt=plan, history=messages, meta_instruction=sys_prompt)
        return response[0]

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

if __name__ == '__main__':
    plan_checker = PlanChecker()
    plan = read_file('2024-9-17-example-plan.txt')
    query = read_file('example_query.txt')
    extra_requirements = ''
    response = plan_checker.check_plan(plan, query, extra_requirements)
    # print(response)
    


