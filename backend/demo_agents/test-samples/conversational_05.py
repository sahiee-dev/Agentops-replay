# demo-agents/test-samples/conversational_05.py

class Agent:
    def __init__(self, name="Agent05"):
        self.name = name
        self.memory = []

    def get_response(self, user_input):
        self.memory.append(user_input)
        return f"{self.name}: Got it. You've told me {len(self.memory)} things so far."

if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
