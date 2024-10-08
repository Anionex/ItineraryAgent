from react_agent.react_agent import ReactAgent

if __name__ == "__main__":
    agent = ReactAgent(model="gpt-4o")
    agent.run("你好")