# demo-agents/test-samples/support_02.py

class Agent:
    def __init__(self, name="Support02"):
        self.name = name

    def respond(self, query):
        return f"{self.name}: Thank you for your message: '{query}'. We will get back shortly."

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("How do I reset my password?"))
