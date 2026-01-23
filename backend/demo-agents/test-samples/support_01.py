# demo-agents/test-samples/support_01.py

class Agent:
    def __init__(self, name="Support01"):
        self.name = name

    def respond(self, query):
        faq = {
            "hours": "Our working hours are 9am-6pm.",
            "price": "The product costs $99."
        }
        return faq.get(query.lower(), f"{self.name}: I am forwarding your query to support.")

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("hours"))
