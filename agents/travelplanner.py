"""
This module contains the implementation of the ReactAgent class, which is responsible for managing the interaction between the user and the travel planner system.

The ReactAgent class handles the generation of thoughts, actions, and observations based on the user's input and the current state of the system. It uses a language model to generate responses and interacts with various tools for performing specific tasks such as flight search, attraction search, accommodation search, etc.

The ReactAgent class also maintains a scratchpad to keep track of the conversation history and logs the conversation in a JSON format.

Example usage:
    agent = ReactAgent(args, mode='zero_shot', tools=['flights', 'attractions'], max_steps=30)
    answer, scratchpad, json_log = await agent.run(query)

Attributes:
    - max_steps (int): The maximum number of steps the agent can take in the conversation.
    - mode (str): The mode of the agent. Currently supports 'zero_shot'.
    - tools (List[str]): The list of tools (e.g., 'flights', 'attractions') that the agent can use.
    - max_retries (int): The maximum number of retries for a failed action.
    - illegal_early_stop_patience (int): The number of consecutive times the same action can be repeated before stopping.
    - react_llm_name (str): The name of the language model used for generating responses.
    - planner_llm_name (str): The name of the language model used for the planner tool.
    - city_file_path (str): The file path to the city set database.
"""

import re, string, os, sys
import dotenv
import asyncio
import threading
import websockets

# ... (rest of the code)
import re, string, os, sys
import dotenv
import asyncio
import threading
import websockets

dotenv.load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "tools/planner")))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "../tools/planner")))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import importlib
from typing import List, Dict, Any
import tiktoken
from pandas import DataFrame
from langchain.chat_models import ChatOpenAI
from langchain.callbacks import get_openai_callback
from langchain.llms.base import BaseLLM
from langchain.prompts import PromptTemplate

from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)
from prompts import zeroshot_react_agent_prompt
# from utils.func import load_line_json_data, save_file
import json
import openai
import time
import pandas as pd
from datetime import datetime
from tqdm import tqdm
from langchain_google_genai import ChatGoogleGenerativeAI
import argparse
from datasets import load_dataset
import os

pd.options.display.max_info_columns = 200

os.environ['TIKTOKEN_CACHE_DIR'] = './tmp'

actionMapping = {"FlightSearch":"flights","AttractionSearch":"attractions","GoogleDistanceMatrix":"googleDistanceMatrix","AccommodationSearch":"accommodation","RestaurantSearch":"restaurants","Planner":"planner","NotebookWrite":"notebook","CitySearch":"cities"}

class CityError(Exception):
    pass

class DateError(Exception):
    pass

async def catch_openai_api_error():
    error = sys.exc_info()[0]
    if error == openai.error.APIConnectionError:
        await print_to_ws("APIConnectionError")
    elif error == openai.error.RateLimitError:
        await print_to_ws("RateLimitError")
        time.sleep(60)
    elif error == openai.error.APIError:
        await print_to_ws("APIError")
    elif error == openai.error.AuthenticationError:
        await print_to_ws("AuthenticationError")
    else:
        await print_to_ws(f"API error:{error}")

class ReactAgent:
    def __init__(self,
                 args,
                 mode: str = 'zero_shot',
                 tools: List[str] = None,
                 max_steps: int = 30,
                 max_retries: int = 3,
                 illegal_early_stop_patience: int = 3,
                 react_llm_name = 'gpt-3.5-turbo-1106',
                 planner_llm_name = 'gpt-3.5-turbo-1106',
                #  logs_path = '../logs/',
                 city_file_path = '../database/background/citySet.txt'
                 ) -> None: 

        self.answer = ''
        self.max_steps = max_steps
        self.mode = mode

        self.react_name = react_llm_name
        self.planner_name = planner_llm_name

        if self.mode == 'zero_shot':
            # langchain的带输入变量的prompt
            # 此处需要两个变量，query（查询计划）和scratchpad（上下文）
            # Q为什么直接使用scratchpad当上下文，而不是多轮对话？
            self.agent_prompt = zeroshot_react_agent_prompt

        self.json_log = []

        self.current_observation = ''
        self.current_data = None

        if 'gpt-3.5' in react_llm_name:
            # 设置停止词，遇到停止词就停止生成，因此每次生成一行
            stop_list = ['\n']
            self.max_token_length = 15000
            self.llm = ChatOpenAI(temperature=0, # 改为0，最大程度防止不一样
                     max_tokens=256,
                     model_name=react_llm_name,
                     model_kwargs={"stop": stop_list})
            
        elif 'gpt-4' in react_llm_name:
            stop_list = ['\n']
            self.max_token_length = 30000
            self.llm = ChatOpenAI(temperature=0,
                     max_tokens=256,
                     model_name=react_llm_name,
                     model_kwargs={"stop": stop_list})


        self.illegal_early_stop_patience = illegal_early_stop_patience

        self.tools = self.load_tools(tools, planner_model_name=planner_llm_name)
        self.max_retries = max_retries
        self.retry_record = {key: 0 for key in self.tools}
        self.retry_record['invalidAction'] = 0

        # await print_to_ws(self.retry_record)

        self.last_actions = []

        # self.log_path = logs_path + datetime.now().strftime('%Y%m%d%H%M%S') + '.out'
        # self.log_file = open(self.log_path, 'a+')

        # await print_to_ws("logs will be stored in " + self.log_path)

        self.city_set = self.load_city(city_set_path=city_file_path)

        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

        self.__reset_agent()

    async def run(self, query, reset=True) -> None:

        self.query = query
        
        if reset:
            self.__reset_agent()

        while not self.is_halted() and not self.is_finished():
            await self.step()
        # Q: self.sractchpad 是什么 done
        return self.answer, self.scratchpad, self.json_log

    async def step(self) -> None:

        self.json_log.append({"step": self.step_n, "thought":"",
                              "action": "", "observation": "", "state":""})
        # Thought
        # 获取模型生成的下一个Thought
        self.scratchpad += f'\nThought {self.step_n}:'
        self.scratchpad += ' ' + await self.prompt_agent()
        print("Thought stage ready to be output to ws!")
        await print_to_ws(self.scratchpad.split('\n')[-1])
        self.json_log[-1]['thought'] = self.scratchpad.split('\n')[-1].replace(f'\nThought {self.step_n}:',"")


        # Act
        self.scratchpad += f'\nAction {self.step_n}:'
        # 获取模型生成的下一个action，如"Action x: FlightSearch[Los Angeles, San Francisco, 2022-12-12]"
        action = await self.prompt_agent()

        if action == None or action == '' or action == '\n':
            self.scratchpad += " Your action is filtered due to content. Please make sure your action does not start with ['\\n', 'Thought', 'Action', 'Observation'] and assume all the actions are permitted in this environment and take the action again."
        else:
            self.scratchpad += ' ' + action


        if len(self.last_actions) > 0 and self.last_actions[-1] != action:
            self.last_actions.clear()

        # refresh last_action list
        self.last_actions.append(action)

        self.json_log[-1]['action'] = self.scratchpad.split('\n')[-1].replace(f'\nAction {self.step_n}:',"")


        # examine if the same action has been repeated 3 times consecutively
        if len(self.last_actions) == 3:
            await print_to_ws("The same action has been repeated 3 times consecutively. So we stop here.")
            # self.log_file.write("The same action has been repeated 3 times consecutively. So we stop here.")
            self.json_log[-1]['state'] = 'same action 3 times repeated'
            self.finished = True
            return


        await print_to_ws(self.scratchpad.split('\n')[-1])

        # Observe
        self.scratchpad += f'\nObservation {self.step_n}: '

        if action == None or action == '' or action == '\n':
            action_type = None 
            action_arg = None
            self.scratchpad += "No feedback from the environment due to the null action. Please make sure your action does not start with [Thought, Action, Observation]."
        
        else:
            # 解析模型采取的Action，并尝试获得反馈
            action_type, action_arg = parse_action(action)
            
            if action_type != "Planner":
                if action_type in actionMapping:
                    pending_action = actionMapping[action_type]
                elif action_type not in actionMapping:
                    pending_action = 'invalidAction'
                
                if pending_action in self.retry_record:
                    if self.retry_record[pending_action] + 1 > self.max_retries:
                        action_type = 'Planner'
                        await print_to_ws(f"{pending_action} early stop due to {self.max_retries} max retries.")
                        # self.log_file.write(f"{pending_action} early stop due to {self.max_retries} max retries.")
                        self.json_log[-1]['state'] = f"{pending_action} early stop due to {self.max_retries} max retries."
                        self.finished = True
                        return
                    
                elif pending_action not in self.retry_record:
                    if self.retry_record['invalidAction'] + 1 > self.max_retries:
                        action_type = 'Planner'
                        await print_to_ws(f"invalidAction Early stop due to {self.max_retries} max retries.")
                        # self.log_file.write(f"invalidAction early stop due to {self.max_retries} max retries.")
                        self.json_log[-1]['state'] = f"invalidAction early stop due to {self.max_retries} max retries."
                        self.finished = True
                        return

            if action_type == 'FlightSearch':
                try:
                    if validate_date_format(action_arg.split(', ')[2]) and validate_city_format(action_arg.split(', ')[0],self.city_set ) and validate_city_format(action_arg.split(', ')[1],self.city_set):
                        self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                        self.current_data = self.tools['flights'].run(action_arg.split(', ')[0], action_arg.split(', ')[1], action_arg.split(', ')[2])
                        self.current_observation = str(to_string(self.current_data))
                        self.scratchpad += self.current_observation 
                        self.__reset_record()
                        self.json_log[-1]['state'] = f'Successful'
                # 错误处理，告诉模型错在哪儿
                except DateError:
                    self.retry_record['flights'] += 1
                    self.current_observation = f"'{action_arg.split(', ')[2]}' is not in the format YYYY-MM-DD"
                    self.scratchpad += f"'{action_arg.split(', ')[2]}' is not in the format YYYY-MM-DD"
                    self.json_log[-1]['state'] = f'Illegal args. DateError'

                except ValueError as e:
                    self.retry_record['flights'] += 1
                    self.current_observation = str(e)
                    self.scratchpad += str(e)
                    self.json_log[-1]['state'] = f'Illegal args. City Error'

                except Exception as e:
                    await print_to_ws(e)
                    self.retry_record['flights'] += 1
                    self.current_observation = f'Illegal Flight Search. Please try again.'
                    self.scratchpad += f'Illegal Flight Search. Please try again.'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'

            elif action_type == 'AttractionSearch':

                try:
                    if validate_city_format(action_arg, self.city_set):
                        self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip().strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                        self.current_data = self.tools['attractions'].run(action_arg)
                        self.current_observation = to_string(self.current_data).strip('\n').strip()
                        self.scratchpad += self.current_observation
                        self.__reset_record()
                        self.json_log[-1]['state'] = f'Successful'
                except ValueError as e:
                    self.retry_record['attractions'] += 1
                    self.current_observation = str(e)
                    self.scratchpad += str(e)
                    self.json_log[-1]['state'] = f'Illegal args. City Error'
                except Exception as e:
                    await print_to_ws(e)
                    self.retry_record['attractions'] += 1
                    self.current_observation = f'Illegal Attraction Search. Please try again.'
                    self.scratchpad += f'Illegal Attraction Search. Please try again.'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'

            elif action_type == 'AccommodationSearch':

                try:
                    if validate_city_format(action_arg, self.city_set):
                        self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip().strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                        self.current_data = self.tools['accommodations'].run(action_arg)
                        self.current_observation = to_string(self.current_data).strip('\n').strip()
                        self.scratchpad += self.current_observation
                        self.__reset_record()
                        self.json_log[-1]['state'] = f'Successful'
                except ValueError as e :
                    self.retry_record['accommodations'] += 1
                    self.current_observation = str(e)
                    self.scratchpad += str(e)
                    self.json_log[-1]['state'] = f'Illegal args. City Error'
                except Exception as e:
                    await print_to_ws(e)
                    self.retry_record['accommodations'] += 1
                    self.current_observation = f'Illegal Accommodation Search. Please try again.'
                    self.scratchpad += f'Illegal Accommodation Search. Please try again.'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'

            elif action_type == 'RestaurantSearch':

                try:
                    if validate_city_format(action_arg, self.city_set):
                        self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip().strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                        self.current_data = self.tools['restaurants'].run(action_arg)
                        self.current_observation = to_string(self.current_data).strip()
                        self.scratchpad += self.current_observation
                        self.__reset_record()
                        self.json_log[-1]['state'] = f'Successful'

                except ValueError as e:
                    self.retry_record['restaurants'] += 1
                    self.current_observation = str(e)
                    self.scratchpad += str(e)
                    self.json_log[-1]['state'] = f'Illegal args. City Error'

                except Exception as e:
                    await print_to_ws(e)
                    self.retry_record['restaurants'] += 1
                    self.current_observation = f'Illegal Restaurant Search. Please try again.'
                    self.scratchpad += f'Illegal Restaurant Search. Please try again.'
                    self.json_log = f'Illegal args. Other Error'
                    
            elif action_type == "CitySearch":
                try:
                    self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    # self.current_data = self.tools['cities'].run(action_arg)
                    self.current_observation = to_string(self.tools['cities'].run(action_arg)).strip()
                    self.scratchpad += self.current_observation
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except ValueError as e:
                    self.retry_record['cities'] += 1
                    self.current_observation = str(e)
                    self.scratchpad += str(e)
                    self.json_log[-1]['state'] = f'Illegal args. State Error'

                except Exception as e:
                    await print_to_ws(e)
                    self.retry_record['cities'] += 1
                    self.current_observation = f'Illegal City Search. Please try again.'
                    self.scratchpad += f'Illegal City Search. Please try again.'
                    self.json_log = f'Illegal args. Other Error'


            elif action_type == 'GoogleDistanceMatrix':

                try:
                    self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    self.current_data = self.tools['googleDistanceMatrix'].run(action_arg.split(', ')[0],action_arg.split(', ')[1],action_arg.split(', ')[2])
                    self.current_observation =  to_string(self.current_data)
                    self.scratchpad += self.current_observation 
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    await print_to_ws(e)
                    self.retry_record['googleDistanceMatrix'] += 1
                    self.current_observation = f'Illegal GoogleDistanceMatrix. Please try again.'
                    self.scratchpad += f'Illegal GoogleDistanceMatrix. Please try again.'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'
            
            
            elif action_type == 'NotebookWrite':
                try:
                    self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    self.current_observation = str(self.tools['notebook'].write(self.current_data, action_arg))
                    self.scratchpad  +=  self.current_observation
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    await print_to_ws(e)
                    self.retry_record['notebook'] += 1
                    self.current_observation = f'{e}'
                    self.scratchpad += f'{e}'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'
            

            elif action_type == "Planner":
                # try:

                    self.current_observation = str(self.tools['planner'].run(str(self.tools['notebook'].list_all()),action_arg))
                    self.scratchpad  +=  self.current_observation
                    self.answer = self.current_observation
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

            else:
                self.retry_record['invalidAction'] += 1
                self.current_observation = 'Invalid Action. Valid Actions are  FlightSearch[Departure City, Destination City, Date] / ' \
                                   'AccommodationSearch[City] /  RestaurantSearch[City] / NotebookWrite[Short Description] / AttractionSearch[City] / CitySearch[State] / GoogleDistanceMatrix[Origin, Destination, Mode] and Planner[Query].'
                self.scratchpad += self.current_observation
                self.json_log[-1]['state'] = f'invalidAction'

        if action == None or action == '' or action == '\n':
            await print_to_ws(f'Observation {self.step_n}: ' + "No feedback from the environment due to the null action.")
            # write(f'Observation {self.step_n}: ' + "Your action is filtered due to content. Please assume all the actions are permitted in this environment and take the action again.")
            self.json_log[-1]['observation'] = "No feedback from the environment due to the null action."
        else:
            await print_to_ws(f'Observation {self.step_n}: ' + self.current_observation+'\n')
            # rite(f'Observation {self.step_n}: ' + self.current_observation+'\n')
            self.json_log[-1]['observation'] = self.current_observation

        self.step_n += 1

        # 

        if action_type and action_type == 'Planner' and self.retry_record['planner']==0:
            # 进行最后一步
            self.finished = True
            self.answer = self.current_observation
            self.step_n += 1
            return

    async def prompt_agent(self) -> str:
        while True:
            try:
                # await print_to_ws(self._build_agent_prompt())
                if self.react_name == 'gemini':
                    request = format_step(self.llm.invoke(self._build_agent_prompt(),stop=['\n']).content)
                else:
                    # 获取下一个回复（一行）
                    request = format_step(self.llm([HumanMessage(content=self._build_agent_prompt())]).content)
                # await print_to_ws(request)
                return request
            except:
                await catch_openai_api_error()
                await print_to_ws(self._build_agent_prompt())
                await print_to_ws(len(self.enc.encode(self._build_agent_prompt())))
                time.sleep(5)

    def _build_agent_prompt(self) -> str:
        """
        Build the agent prompt based on the current state
        这种构建prompt的方式是把提示词、模型已经生成的步骤全部一股脑丢进第一个human_message里面，完全不科学
        正确的做法应该是设定系统提示词， 给出反馈是human_message的职责， 而给出步骤是ai_message的职责
        """
        if self.mode == "zero_shot":
            return self.agent_prompt.format(
                query=self.query,
                scratchpad=self.scratchpad)

    def is_finished(self) -> bool:
        return self.finished

    def is_halted(self) -> bool:
        """
        halt the agent when the step number exceeds the max_steps 
        or the token length exceeds the max_token_length
        we can set max_steps and max_token_length in the code at the top
        """
        return ((self.step_n > self.max_steps) or (
                    len(self.enc.encode(self._build_agent_prompt())) > self.max_token_length)) and not self.finished

    def __reset_agent(self) -> None:
        """
        Reset the agent to the initial state
        """
        self.step_n = 1
        self.finished = False
        self.answer = ''
        self.scratchpad: str = ''
        self.__reset_record()
        self.json_log = []
        self.current_observation = ''
        self.current_data = None
        self.last_actions = []

        if 'notebook' in self.tools:
            self.tools['notebook'].reset()
    
    def __reset_record(self) -> None:
        """
        Reset the retry record for all tools and invalidAction
        used when a successful action is performed
        for example, when a successful FlightSearch is performed, reset the retry_record for FlightSearch
        why must we call this method?
        because we need to reset the retry_record for each tool after a successful action is performed
        what is retry_record?
        it's a dictionary that keeps track of the number of times a tool has failed
        why we record the number of times a tool has failed?
        because we want to stop the agent from performing the same action if it has failed too many times
        we can set the threshold in the code at the top
        """
        self.retry_record = {key: 0 for key in self.retry_record}
        self.retry_record['invalidAction'] = 0


    def load_tools(self, tools: List[str], planner_model_name=None) -> Dict[str, Any]:
        """
        Load the tools from the given list of tool names dynamically initially
        """
        tools_map = {}
        for tool_name in tools:
            module = importlib.import_module("tools.{}.apis".format(tool_name))
            
            if tool_name != 'planner':
                tools_map[tool_name] = getattr(module, tool_name[0].upper()+tool_name[1:])() # 这里的代码写的太烂了
            if tool_name == 'planner' and planner_model_name is not None:
                class_name = 'Planner'
                tools_map[tool_name] = getattr(module, class_name)(model_name=planner_model_name)
        return tools_map 

    def load_city(self, city_set_path: str) -> List[str]:
        """
        Load the city set from the given file path(citySet.txt)
        """
        city_set = []
        lines = open(city_set_path, 'r').read().strip().split('\n')
        for unit in lines:
            city_set.append(unit)
        return city_set

### String Stuff ###
gpt2_enc = tiktoken.encoding_for_model("text-davinci-003")


def parse_action(string):
    """
    Parse the action string into action type and action argument
    for example:
    "FlightSearch[Los Angeles, San Francisco, 2022-12-12]" 
    -> 
    "FlightSearch", "Los Angeles, San Francisco, 2022-12-12"
    """
    pattern = r'^(\w+)\[(.+)\]$'
    match = re.match(pattern, string)

    try:
        if match:
            action_type = match.group(1)
            action_arg = match.group(2)
            # action_arg is in format of "arg1, arg2, arg3"
            return action_type, action_arg
        else:
            return None, None
        
    except:
        return None, None

def format_step(step: str) -> str:
    """
    ensure that the step is in the correct format
    保证两端没有空白字符，且整个字符串没有换行符
    Q用途？
    """
    return step.strip('\n').strip().replace('\n', '')

def validate_date_format(date_str: str) -> bool:
    """
    check if the date is in the format YYYY-MM-DD
    """
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    
    if not re.match(pattern, date_str):
        raise DateError
    return True

def validate_city_format(city_str: str, city_set: list) -> bool:
    """
    check if the city is in pre-defined city list
    """
    if city_str not in city_set:
        raise ValueError(f"{city_str} is not valid city in {str(city_set)}.")
    return True

def to_string(data) -> str:
    """
    Convert the given data to a string representation.

    Parameters:
    data (object): The data to be converted.

    Returns:
    str: The string representation of the data.

    """
    if data is not None:
        if type(data) == DataFrame:
            return data.to_string(index=False)
        else:
            return str(data)
    else:
        return str(None)
    

tools_list = ["notebook","flights","attractions","accommodations","restaurants","googleDistanceMatrix","planner","cities"]

llm_model = os.environ["MODEL"]

agent = ReactAgent(None, tools=tools_list,max_steps=30,react_llm_name=llm_model,planner_llm_name=llm_model)

import asyncio
import websockets
import threading

ws = None

# WebSocket 服务器
async def websocket_server(websocket, path):
    global ws
    ws = websocket
    try:
        query = await websocket.recv()
        if query != "heartbeat":
            await run_agent(query)
        else:
            print("Received heartbeat")
    except websockets.ConnectionClosedError:
        print("WebSocket connection closed")
    finally:
        await websocket.close()

async def print_to_ws(message):
    if ws is not None:
        print(f"ws send: {str(message)}")
        await ws.send(str(message))

async def run_agent(query):
    await print_to_ws("output1")
    await asyncio.sleep(0.1)
    await print_to_ws("output2")
    with get_openai_callback() as cb:
        while True:
            planner_results, _, _ = await agent.run(query)
            if planner_results is not None:
                break
    await print_to_ws("output2")
    await print_to_ws(str(cb))

async def send_heartbeat():
    while True:
        await asyncio.sleep(1)  # 每1秒发送一次心跳
        try:
            if ws is not None:
                await ws.send("heartbeat")
        except websockets.ConnectionClosed:
            break

async def main():
    # 启动WebSocket服务器和心跳任务
    server = await websockets.serve(websocket_server, "localhost", 8765)
    heartbeat_task = asyncio.create_task(send_heartbeat())
    
    await server.wait_closed()
    await heartbeat_task

if __name__ == "__main__":
    # 在主线程中运行事件循环
    asyncio.run(main())
