import pandas as pd
from pandas import DataFrame
from typing import Optional
from utils.func import extract_before_parenthesis


class Attractions:
    """
    用于管理和查询景点信息的类。

    使用说明:
    1. 初始化时可以指定CSV文件路径，默认路径为"../database/attractions/attractions.csv"
    2. 提供了加载数据、按城市搜索景点等功能
    """

    def __init__(self, path="../database/attractions/attractions.csv"):
        """
        初始化Attractions类。

        参数:
        path (str): CSV文件路径，默认为"../database/attractions/attractions.csv"

        使用说明:
        - 创建Attractions实例时会自动加载并处理CSV文件中的景点数据
        """
        self.path = path
        self.data = pd.read_csv(self.path).dropna()[['Name','Latitude','Longitude','Address','Phone','Website',"City"]]
        print("Attractions loaded.")

    def load_db(self):
        """
        重新加载数据库。

        使用说明:
        - 调用此方法可以重新从CSV文件加载景点数据
        - 用于在CSV文件更新后刷新内存中的数据
        """
        self.data = pd.read_csv(self.path)

    def run(self,
            city: str,
            ) -> DataFrame:
        """
        按城市搜索景点。

        参数:
        city (str): 要搜索的城市名称

        返回:
        DataFrame: 包含该城市所有景点信息的DataFrame，如果没有找到景点则返回提示字符串
        DataFrame: 是pandas库中的数据结构，用于存储和操作表格数据
        使用说明:
        - 输入城市名称，返回该城市的所有景点信息
        - 如果城市没有景点，将返回提示信息
        例子：
        - 输入 "New York"，返回 "New York" 的景点信息
        - 输入 "Paris"，返回 "Paris" 的景点信息
        """
        results = self.data[self.data["City"] == city]
        # the results should show the index
        results = results.reset_index(drop=True)
        if len(results) == 0:
            return "There is no attraction in this city."
        return results  
      
    def run_for_annotation(self,
            city: str,
            ) -> DataFrame:
        """
        用于注释的景点搜索方法。

        参数:
        city (str): 要搜索的城市名称（可能包含括号）

        返回:
        DataFrame: 包含该城市所有景点信息的DataFrame

        使用说明:
        - 输入城市名称（可能包含括号），返回该城市的所有景点信息
        - 会自动提取括号前的城市名进行搜索
        例子：
        - 输入 "New York (Manhattan)"，返回 "New York" 的景点信息
        - 输入 "Paris (Montmartre)"，返回 "Paris" 的景点信息
        """
        results = self.data[self.data["City"] == extract_before_parenthesis(city)]
        # the results should show the index
        results = results.reset_index(drop=True)
        return results