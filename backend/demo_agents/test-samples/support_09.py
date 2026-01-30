# demo-agents/test-samples/support_09.py


class Agent:
    def __init__(self, name="Support09"):
        self.name = name

    def respond(self, query):
        return f"{self.name}: Thank you for contacting support. Your ticket number is 12345."


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Need help with installation"))
