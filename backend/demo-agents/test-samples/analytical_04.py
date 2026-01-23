# demo-agents/test-samples/analytical_04.py

class Agent:
    def __init__(self, name="Analytical04"):
        self.name = name

    def analyze(self, data):
        min_val = min(data) if data else None
        return f"{self.name}: Min value = {min_val}"

if __name__ == "__main__":
    agent = Agent()
    sample_data = [5, 17, 2, 8]
    print(agent.analyze(sample_data))
