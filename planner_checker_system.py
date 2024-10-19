from datetime import datetime
import json
import sys
import os
from config import *
from agents.planner_two_stage_in_one import planner_two_stage_in_one
from agents.plan_checker import PlanChecker
from agents.prompts import REACT_PLANNER_PROMPT_TWO_STAGE_IN_ONE
from tenacity import retry, stop_after_attempt, wait_fixed

iter_cnt = 0

@retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
def get_plan(planner, query, extra_requirements):
    try:
        return planner.run(query, extra_requirements=extra_requirements, system_prompt=REACT_PLANNER_PROMPT_TWO_STAGE_IN_ONE).strip('<Itinerary:\n').strip('>')
    except Exception as e:
        print(f"error occurred in get_plan: {e}")
        raise

@retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
def check_plan(plan, query, extra_requirements):
    try:
        return checker.check_plan(plan, query, extra_requirements)
    except Exception as e:
        print(f"error occurred in check_plan: {e}")
        raise


def planner_checker_loop(query, extra_requirements=''):
    while True:
        global iter_cnt
        iter_cnt += 1
        
        try:
            plan = get_plan(planner, query, extra_requirements)
        except Exception as e:
            print(f"Failed to get travel itinerary planning: {e}")
            return "Failed to get travel itinerary planning."

        print("=====\nChecking result.\n=====")
        
        try:
            check_result = check_plan(plan, query, extra_requirements)
            print("Check result:\n", check_result)
        except Exception as e:
            print(f"Failed to check plan: {e}")
            check_result = "Failed to check plan."
        
        if iter_cnt >= MAX_CHECK_ITER:
            print("=====\nReach max check iter.\n=====")
            return {"itinerary":plan, 
                    "expense_info": checker.expense_info, 
                    "average_rating": checker.average_rating
                    }
        # 如果没有建议，结束循环
        if "No more suggestion" in check_result or "Something went wrong!!!" in check_result:
            print("=====\nNo more suggestion.\n=====")
            return {"itinerary":plan, 
                    "expense_info": checker.expense_info, 
                    "average_rating": checker.average_rating
                    }
        
        # 如果有建议，将其添加到 planner 的 scratchpad 中
        else:
            print("Advice found.")
            advice = check_result.strip()
            response = f"\nSystem's feedback: \n{advice}"
            print(response)
            planner.scratchpad += response
            
            # 重置 hit_final_answer 标志，以便 planner 可以继续规划
            planner.hit_final_answer = False

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

if __name__ == '__main__':
    
    import time

    start_time = time.time()

    planner = planner_two_stage_in_one
    checker = PlanChecker()
    
    query = read_file("example_query.txt")
    plan_info = planner_checker_loop(query)
    print("=====\nFinal Itinerary:\n=====")
    print(str(plan_info))
    
    ## 创建log文件夹
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    ## 打印scratchpad到文件
    with open("logs/scratchpad" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + ".txt", "w", encoding="utf-8") as file:
        file.write(planner.scratchpad)
        file.write("\n")
        file.write(str(plan_info))

    ## 打印plan_info到json文件
    with open("logs/plan_info" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + ".json", "w", encoding="utf-8") as file:
        json.dump(plan_info, file, ensure_ascii=False)

    end_time = time.time()
    print(f"Runtime: {end_time - start_time:.2f} seconds")
