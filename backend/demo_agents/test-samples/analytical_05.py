# demo-agents/test-samples/analytical_05.py


class Agent:
    def __init__(self, name="Analytical05"):
        self.name = name

    def analyze(self, data):
        positives = [x for x in data if x > 0]
        return f"{self.name}: Positive numbers count = {len(positives)}"


if __name__ == "__main__":
    agent = Agent()
    sample_data = [-5, 2, 0, 7, -1]
    print(agent.analyze(sample_data))
