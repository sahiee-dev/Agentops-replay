# demo-agents/test-samples/analytical_02.py


class Agent:
    def __init__(self, name="Analytical02"):
        self.name = name

    def analyze(self, data):
        return f"{self.name}: Average = {sum(data) / len(data) if data else 0}"


if __name__ == "__main__":
    agent = Agent()
    sample_data = [10, 20, 30, 40]
    print(agent.analyze(sample_data))
