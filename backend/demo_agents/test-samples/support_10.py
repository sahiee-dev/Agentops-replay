# demo-agents/test-samples/support_10.py


class Agent:
    def __init__(self, name="Support10"):
        self.name = name

    def respond(self, query):
        return f"{self.name}: I am here 24/7 to help you. Please describe your problem."


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Technical issue with my device"))
