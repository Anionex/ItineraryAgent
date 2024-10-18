import os
import json
import sys
import requests
import dotenv
dotenv.load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.utils import filter_search_results
# from tools.attractions.apis import Attractions
# from tools.restaurants.apis import Restaurants
# from tools.accommodations.apis import Accommodations
# from tools.flights.apis import Flights
# from tools.googleDistanceMatrix.apis import GoogleDistanceMatrix
# from tools.notebook.apis import Notebook
# from plan_checker import PlanChecker
from tools import web_apis
from config import *

# 实例化所有工具
# attractions = Attractions()
# restaurants = Restaurants()
# accommodations = Accommodations()
# flights = Flights()
# google_distance_matrix = GoogleDistanceMatrix()
# notebook = Notebook()
# plan_checker = PlanChecker()

# def check_plan(query, plan, extra_requirements=''):
#     return plan_checker.check_plan(plan, query, extra_requirements)

def calculator(expression: str):
    return eval(expression)

def google_search(search_query: str, gl: str, ):
    query = search_query
    payload = json.dumps({
        "q": query,
        "num": SEARCH_NUM,
        "gl": gl,
    })
    response = requests.request("POST", "https://google.serper.dev/search", 
    headers={'X-API-KEY': os.getenv("SERPER_API_KEY"),'Content-Type': 'application/json'}, 
    data=payload)
    filtered_search_results, extra_info = filter_search_results(response.text, query) # filter title
    filtered_search_results = filtered_search_results[:SEARCH_REMAIN_NUM]
    # print(filtered_search_results)
    return str([entry["content"] for entry in filtered_search_results])

def get_attractions(city: str, query: str = "must-visit attractions"):
    return web_apis.get_attractions(city=city, query=query)

def get_restaurants(city: str, query: str = "must-visit restaurants"):
    return web_apis.get_restaurants(city=city, query=query)

# def get_accommodations(city: str):
#     return web_apis.get_accommodations(city=city)

def get_accommodations(city: str, check_in_date: str, check_out_date: str, adults: int):
    return web_apis.get_accommodations(city=city, check_in_date=check_in_date, check_out_date=check_out_date, adults=adults)

def get_flights(origin: str, destination: str, departure_date: str):
    return web_apis.get_flights(origin=origin, destination=destination, date=departure_date)

def get_google_distance_matrix(origin: str, destination: str, mode: str):
    return web_apis.get_distance_matrix(origin=origin, destination=destination, mode=mode)

# def notebook_write(input_data, short_description: str):
#     return notebook.write(input_data, short_description)

# # 可以添加其他 Notebook 相关的函数
# def notebook_read(index: int):
#     return notebook.read(index)

# def notebook_list():
#     return notebook.list()

# def notebook_reset():
#     notebook.reset()
    
if __name__ == "__main__":
    # print(get_google_distance_matrix("中山", "广州", "driving"))
    # print(get_restaurants("中山"))
    # print(get_attractions("中山"))
    # print(get_accommodations("中山"))
    print(google_search("孙文公园门票价格"))