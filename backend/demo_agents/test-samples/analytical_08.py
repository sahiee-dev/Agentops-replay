# demo-agents/test-samples/analytical_08.py

class Agent:
    def __init__(self, name="Analytical08"):
        self.name = name

    def analyze(self, data):
        sorted_data = sorted(data)
        return f"{self.name}: Sorted data = {sorted_data}"

if __name__ == "__main__":
    agent = Agent()
    sample_data = [5, 1, 4, 2, 3]
    print(agent.analyze(sample_data))
