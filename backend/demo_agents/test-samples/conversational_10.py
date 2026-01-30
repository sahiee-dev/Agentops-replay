# demo-agents/test-samples/conversational_10.py


class Agent:
    def __init__(self, name="Agent10"):
        self.name = name

    def get_response(self, user_input):
        reversed_text = user_input[::-1]
        return f"{self.name}: Reversed input -> '{reversed_text}'"


if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
