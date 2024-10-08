from datetime import datetime
import sys
import os


from agents.planner_two_stage_in_one import planner_two_stage_in_one
from agents.plan_checker import PlanChecker
from agents.prompts import REACT_PLANNER_PROMPT_TWO_STAGE_IN_ONE

ADVICE_HEADER = "<Advice:"

def planner_checker_loop(query, extra_requirements=''):
    while True:
        # 使用 planner 获取旅游路线规划
        plan = planner.run(query, extra_requirements=extra_requirements, system_prompt=REACT_PLANNER_PROMPT_TWO_STAGE_IN_ONE)
        
        print("=====\nChecking result.\n=====")
        
        # 使用 checker 检查计划
        check_result = checker.check_plan(plan, query, extra_requirements)
        print("Check result:\n", check_result)
        
        
        # 如果没有建议，结束循环
        if "No more suggestion" in check_result:
            print("=====\nNo more suggestion.\n=====")
            return plan
        
        # 如果有建议，将其添加到 planner 的 scratchpad 中
        elif ADVICE_HEADER in check_result:
            print("Advice found.")
            advice = check_result.split(ADVICE_HEADER)[1].strip()
            response = f"\nAdvice: Based on the feedback, we need to adjust our plan. Advice is as follows: {advice}"
            print(response)
            planner.scratchpad += response
            
            # 重置 hit_final_answer 标志，以便 planner 可以继续规划
            planner.hit_final_answer = False
        else:
            print("Something wrong.The checker didn't return 'Advice:' or 'No more suggestion:'")
            return plan

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

if __name__ == '__main__':
    planner = planner_two_stage_in_one
    checker = PlanChecker()
    
    query = read_file("example_query.txt")
    final_plan = planner_checker_loop(query)
    print("=====\nFinal Itinerary:\n=====")
    print(final_plan)
    
    ## 创建log文件夹
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    ## 打印scratchpad到文件
    with open("logs/scratchpad" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + ".txt", "w", encoding="utf-8") as file:
        file.write(planner.scratchpad)

