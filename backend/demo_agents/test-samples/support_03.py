# demo-agents/test-samples/support_03.py


class Agent:
    def __init__(self, name="Support03"):
        self.name = name

    def respond(self, query):
        return f"{self.name}: Please provide your order ID for faster support."


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("My order is delayed."))
