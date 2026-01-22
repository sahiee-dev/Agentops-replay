# demo-agents/test-samples/analytical_07.py

class Agent:
    def __init__(self, name="Analytical07"):
        self.name = name

    def analyze(self, data):
        total_len = len(data)
        unique_len = len(set(data))
        return f"{self.name}: Total items = {total_len}, Unique items = {unique_len}"

if __name__ == "__main__":
    agent = Agent()
    sample_data = [1, 2, 2, 3, 3, 3]
    print(agent.analyze(sample_data))
