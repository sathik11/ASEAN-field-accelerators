import os

from pathlib import Path

from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration, Prompty
from autogen_core.base import AgentId


from autogen_core.components import DefaultTopicId
from autogen_core.components.models import (
    UserMessage,
)
import asyncio
import tempfile

from autogen_core.application import SingleThreadedAgentRuntime
from autogen_core.components import DefaultSubscription
from autogen_core.components.models import (
    AzureOpenAIChatCompletionClient,
)
from agnext_flow import (
    EditorAgent,
    EmailWriterAgent,
    FacebookPostWriterAgent,
    MarketingManagerAgent,
    ProductInfomationProviderAgent,
    TwitterPostWriterAgent,
    GroupChatMessage,
)

work_dir = tempfile.mkdtemp()

# Create an local embedded runtime.
runtime = SingleThreadedAgentRuntime()

BASE_DIR = Path(__file__).absolute().parent


def log(message: str):
    verbose = os.environ.get("VERBOSE", "false")
    if verbose.lower() == "true":
        print(message, flush=True)


class ChatFlow:
    def __init__(
        self, model_config: AzureOpenAIModelConfiguration, max_total_token=4096
    ):
        self.model_config = model_config
        self.max_total_token = max_total_token

    @trace
    async def __call__(
        self,
        question: str,
        chat_history: list = None,
    ):  # -> Generator[Any, Any, None]:
        """Flow entry function."""

        prompty = Prompty.load(
            source=BASE_DIR / "chat.prompty",
            model={"configuration": self.model_config},
        )

        chat_history = chat_history or []
        # Try to render the prompt with token limit and reduce the history count if it fails
        while len(chat_history) > 0:
            token_count = prompty.estimate_token_count(
                question=question, chat_history=chat_history
            )
            if token_count > self.max_total_token:
                chat_history = chat_history[1:]
                log(
                    f"Reducing chat history count to {len(chat_history)} to fit token limit"
                )
            else:
                break

        # output is a string
        output = prompty(question=question, chat_history=chat_history)

        yield output


class AGNextFlow:
    def __init__(self, model_config: AzureOpenAIModelConfiguration, test_mode=True):
        self.model_config = model_config
        self.output_queue = asyncio.Queue()
        self.test_mode = test_mode

    @trace
    async def __call__(
        self, question: str, chat_history: list = None
    ):  # -> Generator[Any, Any, None]:
        if self.test_mode:
            return "This is a test"

        run_task = asyncio.create_task(self.run(question, self.output_queue))
        while True:
            message = await self.output_queue.get()
            if message is None:
                break
            yield message
            await asyncio.sleep(0.1)
        await run_task

    async def run(self, question: str, output_queue: asyncio.Queue):
        aoai_model_client = AzureOpenAIChatCompletionClient(
            model="gpt-4o",
            api_key=self.model_config.api_key,
            api_version="2024-02-15-preview",
            azure_endpoint="https://ss-cchat-sf-ai-aiservices7wx5mg43sbnl4.openai.azure.com/",
            model_capabilities={
                "vision": True,
                "function_calling": True,
                "json_output": True,
            },
        )

        self.runtime = SingleThreadedAgentRuntime()

        editor_type = await runtime.register(
            "editor",
            lambda: EditorAgent(model_client=aoai_model_client),
            subscriptions=lambda: [DefaultSubscription()],
        )
        product_info_provider_type = await runtime.register(
            "product_info_provider",
            lambda: ProductInfomationProviderAgent(model_client=aoai_model_client),
            subscriptions=lambda: [DefaultSubscription()],
        )
        email_writer_type = await runtime.register(
            "email_writer",
            lambda: EmailWriterAgent(model_client=aoai_model_client),
            subscriptions=lambda: [DefaultSubscription()],
        )
        facebook_writer_type = await runtime.register(
            "facebook_post_writer",
            lambda: FacebookPostWriterAgent(model_client=aoai_model_client),
            subscriptions=lambda: [DefaultSubscription()],
        )
        twitter_writer_type = await runtime.register(
            "twitter_post_writer",
            lambda: TwitterPostWriterAgent(model_client=aoai_model_client),
            subscriptions=lambda: [DefaultSubscription()],
        )

        # Create AgentId instances for each agent
        product_info_provider_id = AgentId(product_info_provider_type, "default")
        email_writer_id = AgentId(email_writer_type, "default")
        facebook_writer_id = AgentId(facebook_writer_type, "default")
        twitter_writer_id = AgentId(twitter_writer_type, "default")
        editor_id = AgentId(editor_type, "default")
        # Register the MarketingManagerAgent
        await runtime.register(
            "marketing_manager",
            lambda: MarketingManagerAgent(
                product_info_provider=product_info_provider_id,
                writers=[email_writer_id, facebook_writer_id, twitter_writer_id],
                editor=editor_id,
                output_queue=output_queue,
            ),
            subscriptions=lambda: [DefaultSubscription()],
        )

        runtime.start()
        await runtime.publish_message(
            GroupChatMessage(
                UserMessage(
                    content=question,
                    source="User",
                )
            ),
            DefaultTopicId(),
        )

        await runtime.stop_when_idle()
        self.output_queue.put_nowait(None)


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    # start_trace()
    config = AzureOpenAIModelConfiguration(connection="aoai", azure_deployment="gpt-4o")
    print(config)
    flow = AGNextFlow(config)
    print(flow("Apple iPhone 16"))
    # flow = ChatFlow(config)
    # result = flow("What's Azure Machine Learning?", [])
    # print(result)
