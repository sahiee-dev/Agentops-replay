# demo-agents/test-samples/conversational_08.py

class Agent:
    def __init__(self, name="Agent08"):
        self.name = name

    def get_response(self, user_input):
        words = user_input.split()
        return f"{self.name}: Your input has {len(words)} words."

if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
