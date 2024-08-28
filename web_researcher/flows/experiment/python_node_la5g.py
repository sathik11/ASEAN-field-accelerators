from promptflow.core import tool


# TODO: update with proper testing and implementation
@tool
async def my_python_tool(input1: str) -> str:
    yield input1
