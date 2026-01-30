# demo-agents/test-samples/support_05.py

class Agent:
    def __init__(self, name="Support05"):
        self.name = name

    def respond(self, query):
        keywords = ["delay", "late", "status"]
        if any(k in query.lower() for k in keywords):
            return f"{self.name}: Your order is being processed and will arrive soon."
        return f"{self.name}: Can you clarify your issue?"

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Where is my package?"))
