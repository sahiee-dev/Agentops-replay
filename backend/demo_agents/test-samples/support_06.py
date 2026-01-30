# demo-agents/test-samples/support_06.py


class Agent:
    def __init__(self, name="Support06"):
        self.name = name

    def respond(self, query):
        return f"{self.name}: I can help you with billing, orders, and technical issues. Please specify."


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("I have a billing problem."))
