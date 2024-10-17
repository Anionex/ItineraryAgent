import sys
import os
import re
from typing import Dict
print(os.getcwd())
sys.path.append(os.path.abspath(os.getcwd()))
from chat_model import OpenAIChat
from prompts import *
from config import *

def calculate_budget(response):
    """
    Receives the output that has already been processed by COT
    """
    response = response.split("Summary")[-1].strip('=').strip()
    total_budget = 0
    categories = ['Transportation', 'Attractions', 'Accommodation', 'Dining']
    budget_info = {}

    for category in categories:
        category_total = 0
        expressions = re.findall(f"{category}:(.*)", response)
        if expressions:
            for expr in expressions:
                try:
                    # Remove brackets and calculate the expression
                    expr = expr.replace('[', '').replace(']', '')
                    category_total += eval(expr)
                except:
                    print(f"Unable to calculate expression: {expr}")
                    raise Exception(f"Unable to calculate expression: {expr}")
        
        budget_info[category] = category_total
        total_budget += category_total

    # Extract unit
    unit_pattern = re.compile(r'Unit: (\w+)')
    unit_match = unit_pattern.search(response)
    if unit_match:
        budget_info['Unit'] = unit_match.group(1)
    else:
        budget_info['Unit'] = 'USD'  # Default unit if not specified
    
    budget_info['Attractions'] = round(budget_info['Attractions'], 2) # Round to 2 decimal places
    budget_info['Accommodation'] = round(budget_info['Accommodation'], 2) # Round to 2 decimal places
    budget_info['Dining'] = round(budget_info['Dining'], 2) # Round to 2 decimal places
    budget_info['Total'] = round(total_budget, 2) # Round to 2 decimal places
    print(str(budget_info))
    return budget_info


def calculate_rating(response):
    """
    Receives the output that has already been processed by COT
    """
    response = response.split("Summary")[-1].strip('=').strip()
    total_rating = 0
    categories = ['Total Restaurant Ratings', 'Total Attractions Ratings', 'Total Accommodation Ratings']
    rating_info = {}
    
    lines = response.split('\n')
    for i, category in enumerate(categories):
        if i < len(lines):
            expr = lines[i].split(':', 1)[-1].strip()
            try:
                category_total = eval(expr)
            except:
                print(f"Unable to calculate expression: {expr}")
                category_total = 0
            rating_info[category] = category_total
            total_rating += category_total
    
    rating_info['Total Attractions Ratings'] = round(rating_info['Total Attractions Ratings'], 2)
    rating_info['Total Accommodation Ratings'] = round(rating_info['Total Accommodation Ratings'], 2)
    rating_info['Total Restaurant Ratings'] = round(rating_info['Total Restaurant Ratings'], 2)
    rating_info['Total'] = round(total_rating, 2)
    print(str(rating_info))
    return rating_info
    

class PlanChecker:
    def __init__(self, **kwargs) -> None: 
        kwargs['model'] = kwargs.get('model', 'gemini-1.5-flash-002')
        kwargs['temperature'] = kwargs.get('temperature', 0)
        kwargs['is_verbose'] = True
        self.kwargs = kwargs
        self.model = OpenAIChat(**kwargs)
        
        print("Initializing PlanChecker with model info:", kwargs)
        self.budget_info : Dict[str, float] = {}
        self.rating_info : Dict[str, str] = {}


    def build_system_input(self, query, extra_requirements, check_stage: str):
        if check_stage == 'budget':
            sys_prompt = PLAN_CHECKER_PROMPT_BUDGET.format(extra_requirements=extra_requirements, query=query)
        elif check_stage == 'reasonability':
            sys_prompt = PLAN_CHECKER_PROMPT.format(extra_requirements=extra_requirements, query=query)
        return sys_prompt

        
    def check_plan(self, plan, query, extra_requirements='') -> str:
        """
        1. Budget check + rating summary
        2. Reasonability check
        """
        sys_prompt = self.build_system_input(query, extra_requirements, check_stage='budget')
        history = []
        response, history = self.model.chat(prompt=plan, history=history, meta_instruction=sys_prompt)
        
        self.budget_info = calculate_budget(response)
        self.model.kwargs['model'] = 'gpt-4o'
        response, history = self.model.chat(prompt=JUDGE_BUDGET_PROMPT.format(budget_info="\n"+str(self.budget_info)),
                                   history=history,
                                   meta_instruction="You are a Bugget Analyst.")
        
        
        print("budget check result:", response)
        if not 'approved' in response.splitlines()[-1].lower():
            # Failed budget check
            print("start budget advice")
            response, history = self.model.chat(prompt=BUDGET_ADVICE_PROMPT,
                                   history=history,
                                   meta_instruction=sys_prompt)
            # print("budget advice result:", response)
            return response+f"Current budget for each item is as follows：\n{str(self.budget_info)}\n"
        # Passed budget check, proceed to reasonability check
        print("start reasonability check")
        history = []
        sys_prompt = self.build_system_input(query, extra_requirements, check_stage='reasonability')
        
        self.model.kwargs['model'] = 'gpt-4o'
        response, history = self.model.chat(prompt=JUDGE_REASONABILITY_PROMPT.format(plan=plan, budget_info=self.budget_info), 
                                            history=history, 
                                            meta_instruction=sys_prompt)
        if not 'approved' in response.splitlines()[-1].lower():
            response, history = self.model.chat(prompt=REASONABILITY_ADVICE_PROMPT,
                                                history=history,
                                                meta_instruction=sys_prompt)
            return response
        # extra: rating summary
        self.model.kwargs['model'] = 'gemini-1.5-flash-002'
        response, _ = self.model.chat(prompt=f"Here is the plan:\n{plan}",
                                            history=[],
                                            meta_instruction=RATING_SUMMARY_SYSTEM_PROMPT)
        self.rating_info = calculate_rating(response)
        return "No more suggestion"

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

if __name__ == '__main__':
    plan_checker = PlanChecker()
    plan = read_file('agents/example_plan.txt')
    query = read_file('agents/example_query.txt')
    extra_requirements = ''
    response = plan_checker.check_plan(plan, query, extra_requirements)
    print(str(response))
