# demo-agents/test-samples/support_04.py

class Agent:
    def __init__(self, name="Support04"):
        self.name = name

    def respond(self, query):
        if "refund" in query.lower():
            return f"{self.name}: Refunds are processed within 5–7 business days."
        return f"{self.name}: We have received your request."

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("I want a refund"))
