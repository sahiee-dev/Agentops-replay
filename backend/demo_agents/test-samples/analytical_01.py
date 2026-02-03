# demo-agents/test-samples/analytical_01.py


class Agent:
    def __init__(self, name="Analytical01"):
        self.name = name

    def analyze(self, data):
        return f"{self.name}: Sum of data = {sum(data)}"


if __name__ == "__main__":
    agent = Agent()
    sample_data = [1, 2, 3, 4, 5]
    print(agent.analyze(sample_data))
