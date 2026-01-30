# demo-agents/test-samples/support_07.py

class Agent:
    def __init__(self, name="Support07"):
        self.name = name

    def respond(self, query):
        if "password" in query.lower():
            return f"{self.name}: You can reset your password using the 'Forgot Password' link."
        return f"{self.name}: Could you provide more details?"

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("I forgot my password"))
