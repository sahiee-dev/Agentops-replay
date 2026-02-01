# demo-agents/test-samples/analytical_06.py


class Agent:
    def __init__(self, name="Analytical06"):
        self.name = name

    def analyze(self, data):
        evens = [x for x in data if x % 2 == 0]
        return f"{self.name}: Even numbers = {evens}"


if __name__ == "__main__":
    agent = Agent()
    sample_data = [1, 2, 3, 4, 5, 6]
    print(agent.analyze(sample_data))
