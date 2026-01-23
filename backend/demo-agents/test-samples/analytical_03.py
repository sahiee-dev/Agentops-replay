# demo-agents/test-samples/analytical_03.py

class Agent:
    def __init__(self, name="Analytical03"):
        self.name = name

    def analyze(self, data):
        max_val = max(data) if data else None
        return f"{self.name}: Max value = {max_val}"

if __name__ == "__main__":
    agent = Agent()
    sample_data = [5, 17, 2, 8]
    print(agent.analyze(sample_data))
