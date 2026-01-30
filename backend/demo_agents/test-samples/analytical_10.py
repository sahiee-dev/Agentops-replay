# demo-agents/test-samples/analytical_10.py

class Agent:
    def __init__(self, name="Analytical10"):
        self.name = name

    def analyze(self, data):
        negative_sum = sum(x for x in data if x < 0)
        return f"{self.name}: Sum of negative numbers = {negative_sum}"

if __name__ == "__main__":
    agent = Agent()
    sample_data = [-5, 2, -3, 4]
    print(agent.analyze(sample_data))
