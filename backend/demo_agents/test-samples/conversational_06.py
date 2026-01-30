# demo-agents/test-samples/conversational_06.py


class Agent:
    def __init__(self, name="Agent06"):
        self.name = name

    def get_response(self, user_input):
        if "?" in user_input:
            return f"{self.name}: That's an interesting question about '{user_input}'."
        return f"{self.name}: You said '{user_input}'."


if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
