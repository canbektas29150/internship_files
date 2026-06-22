import os


def process_user_input(user_input):
    command = f"echo {user_input}"
    os.system(command)
    return "Command executed"
