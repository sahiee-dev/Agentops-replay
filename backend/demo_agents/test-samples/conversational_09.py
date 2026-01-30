# demo-agents/test-samples/conversational_09.py

class Agent:
    def __init__(self, name="Agent09"):
        self.name = name

    def get_response(self, user_input):
        vowels = sum(1 for c in user_input.lower() if c in "aeiou")
        return f"{self.name}: Your input has {vowels} vowels."

if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
