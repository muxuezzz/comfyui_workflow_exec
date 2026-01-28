import os


def process_file(file_path):
    pass


data_path = os.path.join(os.getcwd(), "data", "input.csv")
if os.path.isfile(data_path) and os.path.exists(data_path):
    process_file(data_path)
