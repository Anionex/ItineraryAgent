import os
import json
import sys
import requests
import dotenv
from tools.attractions.apis import Attractions
from tools.restaurants.apis import Restaurants
from tools.accommodations.apis import Accommodations
from tools.flights.apis import Flights
from tools.googleDistanceMatrix.apis import GoogleDistanceMatrix
from tools.notebook.apis import Notebook
from plan_checker import PlanChecker
# 将当前目录的父目录添加到Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
dotenv.load_dotenv()

# 实例化所有工具
attractions = Attractions()
restaurants = Restaurants()
accommodations = Accommodations()
flights = Flights()
google_distance_matrix = GoogleDistanceMatrix()
notebook = Notebook()
# plan_checker = PlanChecker()

# def check_plan(query, plan, extra_requirements=''):
#     return plan_checker.check_plan(plan, query, extra_requirements)

def calculator(expression: str):
    return eval(expression)

def google_search(search_query: str):
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": search_query})
    headers = {
        'X-API-KEY': os.getenv('SERPER_API_KEY'),
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload).json()
    return response['organic'][0]['snippet']

def get_attractions(city: str):
    return attractions.run(city=city)

def get_restaurants(city: str):
    return restaurants.run(city=city)

def get_accommodations(city: str):
    return accommodations.run(city=city)

def get_flights(origin: str, destination: str, departure_date: str):
    return flights.run(origin=origin, destination=destination, departure_date=departure_date)

def get_google_distance_matrix(origin: str, destination: str, mode: str):
    return google_distance_matrix.run(origin=origin, destination=destination, mode=mode)

def notebook_write(input_data, short_description: str):
    return notebook.write(input_data, short_description)

# 可以添加其他 Notebook 相关的函数
def notebook_read(index: int):
    return notebook.read(index)

def notebook_list():
    return notebook.list()

def notebook_reset():
    notebook.reset()