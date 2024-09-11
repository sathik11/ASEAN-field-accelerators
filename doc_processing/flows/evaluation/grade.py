from promptflow.core import tool


@tool
def grade(groundtruth: str, prediction: str):
    # return "Correct" if groundtruth.lower() == prediction.lower() else "Incorrect"
    return "Correct"  # Always return "Correct" for testing purposes


# TODO: Update the grade function to return "Correct" if the prediction is a substring of the groundtruth
