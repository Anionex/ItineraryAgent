import sys
import os
print(os.getcwd())
print(os.path.join(os.getcwd(), "tools"))
sys.path.append(os.path.abspath(os.getcwd()))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "tools")))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
import json5
from chat_model import OpenAIChat
from tool_registry import Tools
from prompts import REACT_PROMPT, TOOL_DESC
import os, sys


from tool_funcs import calculator, google_search

THOUGHT_HEADER = "<Analysis:"
ACTION_HEADER = "<Tool Invocation:"
ACTION_INPUT_HEADER = "<Tool Input:"
ACTION_OUTPUT_HEADER = "<Tool Output:"
ANSWER_HEADER = "<Itinerary:"
STOP_WORD = "/>"


class ReactAgent:
    def __init__(self, **kwargs) -> None: 
        self.tools = Tools()
        kwargs['model'] = kwargs.get('model', 'gpt-4o')
        kwargs['stop'] = kwargs.get('stop', ['\n'])
        kwargs['temperature'] = kwargs.get('temperature', 0)
        self.kwargs = kwargs
        self.model = OpenAIChat(**kwargs)
        print("Initializing ReactAgent with model info:", kwargs)
        self.scratchpad = ""
        self.hit_final_answer = False


    def build_system_input(self, query, extra_requirements, system_prompt):
        tool_descs, tool_names = [], []
        for tool in self.tools.toolConfig:
            tool_descs.append(TOOL_DESC.format(**tool))
            tool_names.append(tool['name_for_model'])
        tool_descs = '\n\n'.join(tool_descs)
        tool_names = ','.join(tool_names)
        sys_prompt = system_prompt.format(tool_descs=tool_descs, 
                                         tool_names=tool_names, 
                                         current_date=datetime.now().strftime("%Y-%m-%d"), 
                                         query=query,
                                         extra_requirements=extra_requirements)

        return sys_prompt
    
    def parse_latest_plugin_call(self, text):
        # 查找最后一个 Tool Invocation 和 Tool Input
        tool_invocation = text.split(ACTION_HEADER)[-1].split(STOP_WORD)[0].strip() # 去掉一个加上的STOP_WORD
        tool_input = text.split(ACTION_INPUT_HEADER)[-1].strip()
        # print("tool_invocation:", tool_invocation)
        # print("tool_input:", tool_input)
        return tool_invocation, tool_input
    def call_plugin(self, plugin_name, plugin_args):
        try:
            plugin_args = json5.loads(plugin_args)
        except Exception as e:
            return f'\n{ACTION_OUTPUT_HEADER}' + f"Input parsing error: {str(e)} Please check if the input parameters are correct"
        
        try:
            return f'\n{ACTION_OUTPUT_HEADER}' + str(self.tools.execute_tool(plugin_name, **plugin_args))
        except Exception as e:
            return f'\n{ACTION_OUTPUT_HEADER}' + f"Tool execution error: {str(e)} Please check if the input parameters are correct"

    
    def step(self, scratchpad):
        # return self.model.create_assistant_completion(scratchpad, meta_instruction=self.system_prompt)
        return self.model.chat(scratchpad, [], self.system_prompt)[0]

      
    def run(self, query, extra_requirements="", system_prompt=REACT_PROMPT):
        # 构建系统提示词
        self.system_prompt = self.build_system_input(query, extra_requirements, system_prompt)
        
        # 重新添加停止符号\n
        self.model.kwargs = self.kwargs
        while True:
            response = self.step(self.scratchpad)

            if response.startswith(ANSWER_HEADER):
                print("=====\nGET AN ITINERARY\n=====")
                self.hit_final_answer = True
                
                # 取消只能输出一行的限制(stop=['\n'])，重新获取response
                # self.kwargs['stop'] = None
                # self.model.kwargs = self.kwargs
                self.scratchpad += '\n' + ANSWER_HEADER
                response = self.step(self.scratchpad)
                
            elif response.startswith(THOUGHT_HEADER):
                pass
            elif response.startswith(ACTION_INPUT_HEADER):
                plugin_name, plugin_args = self.parse_latest_plugin_call(self.scratchpad+'\n'+ response)
                delta = self.call_plugin(plugin_name, plugin_args)
                response += STOP_WORD + delta
            elif response.startswith(ACTION_HEADER):
                pass
            elif response.startswith(ACTION_OUTPUT_HEADER):
                response = "Please remember that you shouldn't generate Tool Output by yourself"
            else:
                response = f"Please remember that only the following tags are allowed: [{THOUGHT_HEADER + STOP_WORD}, {ACTION_HEADER + STOP_WORD}, {ACTION_INPUT_HEADER + STOP_WORD}, {ACTION_OUTPUT_HEADER + STOP_WORD}, {ANSWER_HEADER + STOP_WORD}]"
            response += STOP_WORD
            print("[1]" + response)
            self.scratchpad += '\n' + response
            if self.hit_final_answer:
                return response
    
    
            

