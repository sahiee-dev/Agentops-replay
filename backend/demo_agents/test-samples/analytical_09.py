# demo-agents/test-samples/analytical_09.py


class Agent:
    def __init__(self, name="Analytical09"):
        self.name = name

    def analyze(self, data):
        squared = [x**2 for x in data]
        return f"{self.name}: Squared values = {squared}"


if __name__ == "__main__":
    agent = Agent()
    sample_data = [1, 2, 3, 4]
    print(agent.analyze(sample_data))
