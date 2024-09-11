import asyncio
from promptflow.connections import CustomConnection, AzureOpenAIConnection
from promptflow.core import tool
from autogen_flow import AutogenFlow


@tool
async def my_python_tool(
    azureOpenAIConnection: AzureOpenAIConnection,
    docIntelligenceConnection: CustomConnection,
    cosmosConnection: CustomConnection,
    storageConnection: CustomConnection,
    question: str,
    customer_id: str = "116",
    test: bool = True,
):
    if test:
        print("This is a test run.")
        yield {"test": "This is a test run."}
        return

    # Create a queue to store the messages
    mesg_queue = asyncio.Queue()

    # flow = SimulateFlow(queue=mesg_queue)
    flow = AutogenFlow(
        agent_config=azureOpenAIConnection,
        docinterpreter_config=docIntelligenceConnection,
        cosmosdb_config=cosmosConnection,
        storage_config=storageConnection,
        mesg_queue=mesg_queue,
        customer_id=customer_id,
    )
    # Create async task for the coroutine to run concurrently
    chat_task = asyncio.create_task(flow.run_chat(question))

    timeout_seconds = 300  # Set timeout to 5 minutes

    # Process the messages from the queue
    while True:
        try:
            message = await asyncio.wait_for(mesg_queue.get(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            print("Timeout while waiting for a message from the queue.")
            break  # or handle timeout appropriately

        if message is None:  # Check for completion signal
            break
        yield message  # Process or yield the message as needed

    # Await the task to get the chat results, with timeout
    try:
        chatResults = await asyncio.wait_for(chat_task, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        # print("Chat task timed out.")
        chatResults = {
            "error": "Chat task timed out."
        }  # or handle timeout appropriately

    # Return the chat results
    yield chatResults
