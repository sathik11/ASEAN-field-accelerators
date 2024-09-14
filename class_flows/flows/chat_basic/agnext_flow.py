from dataclasses import dataclass, asdict
from typing import List

from autogen_core.components import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
)
from autogen_core.components.models import (
    LLMMessage,
    AssistantMessage,
    ChatCompletionClient,
    SystemMessage,
    UserMessage,
)
from autogen_core.base import MessageContext, AgentId

import asyncio
from datetime import datetime


@dataclass
class GroupChatMessage:
    body: LLMMessage

    def to_dict(self):
        return asdict(self)


@dataclass
class RequestToSpeak:
    def to_dict(self):
        return asdict(self)


class ProductInfomationProviderAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("ProductInformationProvider")
        self._model_client = model_client
        self._chat_history: List[LLMMessage] = [
            SystemMessage(
                "Based on given product name, provide a brief description of the product and its key features."
            )
        ]

    @message_handler
    async def handle_message(
        self, message: GroupChatMessage, ctx: MessageContext
    ) -> None:
        self._chat_history.append(message.body)

    @message_handler
    async def handle_request_to_speak(
        self, message: RequestToSpeak, ctx: MessageContext
    ) -> None:
        completion = await self._model_client.create(self._chat_history)
        self._chat_history.append(
            AssistantMessage(
                content=completion.content, source="ProductInformationProvider"
            )
        )
        await self.publish_message(
            GroupChatMessage(
                body=UserMessage(
                    content=completion.content, source="ProductInformationProvider"
                )
            ),
            DefaultTopicId(),
        )


class EmailWriterAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("EmailWriter")
        self._model_client = model_client
        self._chat_history: List[LLMMessage] = [
            SystemMessage(
                "You are a marketing email writer. Write a compelling email promoting our new product in less than 200 words."
            )
        ]

    @message_handler
    async def handle_message(
        self, message: GroupChatMessage, ctx: MessageContext
    ) -> None:
        self._chat_history.append(message.body)
        source = message.body.source
        if source == "MarketingManager":
            # Received product information
            pass  # Handled in chat history
        elif source == "Editor":
            # Received feedback from editor
            pass  # Feedback added to chat history
        else:
            pass  # Other messages

    @message_handler
    async def handle_request_to_speak(
        self, message: RequestToSpeak, ctx: MessageContext
    ) -> None:
        completion = await self._model_client.create(self._chat_history)
        self._chat_history.append(
            AssistantMessage(content=completion.content, source="EmailWriter")
        )
        await self.publish_message(
            GroupChatMessage(
                body=UserMessage(content=completion.content, source="EmailWriter")
            ),
            DefaultTopicId(),
        )


class FacebookPostWriterAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("FacebookPostWriter")
        self._model_client = model_client
        self._chat_history: List[LLMMessage] = [
            SystemMessage(
                "You are a social media manager. Write an engaging Facebook post promoting our new product in less than 100 words."
            )
        ]

    @message_handler
    async def handle_message(
        self, message: GroupChatMessage, ctx: MessageContext
    ) -> None:
        self._chat_history.append(message.body)

    @message_handler
    async def handle_request_to_speak(
        self, message: RequestToSpeak, ctx: MessageContext
    ) -> None:
        completion = await self._model_client.create(self._chat_history)
        self._chat_history.append(
            AssistantMessage(content=completion.content, source="FacebookPostWriter")
        )
        await self.publish_message(
            GroupChatMessage(
                body=UserMessage(
                    content=completion.content, source="FacebookPostWriter"
                )
            ),
            DefaultTopicId(),
        )


class TwitterPostWriterAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("TwitterPostWriter")
        self._model_client = model_client
        self._chat_history: List[LLMMessage] = [
            SystemMessage(
                "You are a social media manager. Write a captivating Twitter post promoting our new product, within 280 characters."
            )
        ]

    @message_handler
    async def handle_message(
        self, message: GroupChatMessage, ctx: MessageContext
    ) -> None:
        self._chat_history.append(message.body)

    @message_handler
    async def handle_request_to_speak(
        self, message: RequestToSpeak, ctx: MessageContext
    ) -> None:
        completion = await self._model_client.create(self._chat_history)
        self._chat_history.append(
            AssistantMessage(content=completion.content, source="TwitterPostWriter")
        )
        await self.publish_message(
            GroupChatMessage(
                body=UserMessage(content=completion.content, source="TwitterPostWriter")
            ),
            DefaultTopicId(),
        )


class EditorAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("Editor")
        self._model_client = model_client
        self._chat_history: List[LLMMessage] = [
            SystemMessage(
                f"You are an editor. Review the draft and reply with 'APPROVE' if it's good, or provide suggestions for improvement. Consider the below guidelines when reviewing:\n\n1. Is the content engaging and informative?\n2. Is the tone appropriate for the target audience?\n3. Are there any grammatical errors or typos? 3. Request to include current month and year in the content. Current Month and Year is {datetime.now().strftime('%B %Y')}."  # noqa
            )
        ]

    @message_handler
    async def handle_message(
        self, message: GroupChatMessage, ctx: MessageContext
    ) -> None:
        self._chat_history.append(message.body)

    @message_handler
    async def handle_request_to_speak(
        self, message: RequestToSpeak, ctx: MessageContext
    ) -> None:
        completion = await self._model_client.create(self._chat_history)
        # print(f"Editor: {completion.content}")
        self._chat_history.append(
            AssistantMessage(content=completion.content, source="Editor")
        )
        await self.publish_message(
            GroupChatMessage(
                body=UserMessage(content=completion.content, source="Editor")
            ),
            DefaultTopicId(),
        )


class MarketingManagerAgent(RoutedAgent):
    def __init__(
        self,
        product_info_provider: AgentId,
        writers: List[AgentId],
        editor: AgentId,
        output_queue: asyncio.Queue,
    ) -> None:
        super().__init__("MarketingManager")
        self._product_info_provider = product_info_provider
        self._writers = writers
        self._editor = editor
        self._current_writer_index = 0
        self._chat_history: List[GroupChatMessage] = []
        self._product_info = None
        self._approved_writers = set()
        self._output_queue = output_queue
        self._writer_drafts = {}  # Keep track of drafts per writer

    @message_handler
    async def handle_message(
        self, message: GroupChatMessage, ctx: MessageContext
    ) -> None:
        # print(f"Received message: {message.body.content} from {message.body.source}")
        self._chat_history.append(message)
        self._output_queue.put_nowait(message.to_dict())
        source = message.body.source

        if source == "ProductInformationProvider":
            # Received product information
            self._product_info = message.body.content
            # print(f"Received product information: {self._product_info}")

            # Send product information to all writer agents
            for writer in self._writers:
                await self.send_message(
                    GroupChatMessage(
                        body=UserMessage(
                            content=self._product_info, source="MarketingManager"
                        )
                    ),
                    writer,
                )
                # Request each speaker to speak
                await self.send_message(RequestToSpeak(), writer)

        elif source in ["EmailWriter", "FacebookPostWriter", "TwitterPostWriter"]:
            # Store the draft from the writer
            self._writer_drafts[source] = message.body.content

            # Send draft to Editor along with the writer's identifier
            await self.send_message(
                GroupChatMessage(
                    body=UserMessage(
                        content=message.body.content,
                        source=source,  # Include writer's source
                    )
                ),
                self._editor,
            )
            # Request Editor to speak
            await self.send_message(RequestToSpeak(), self._editor)

        elif source == "Editor":
            # Editor's feedback or approval
            content = message.body.content.upper()
            # Extract the writer's identifier from the previous message
            last_message = self._chat_history[-2]
            writer_source = last_message.body.source  # The writer's identifier

            if "APPROVE" in content:
                # Mark writer as approved
                self._approved_writers.add(writer_source)
                print(f"{writer_source}'s draft has been approved.")

                if len(self._approved_writers) == len(self._writers):
                    print("All drafts have been approved.")
            else:
                # Send feedback back to the specific writer
                print(f"Asking {writer_source} to revise the draft.")
                await self.send_message(
                    GroupChatMessage(body=message.body),
                    AgentId(writer_source, "default"),  # Route to the correct writer
                )
                # Request writer to revise
                await self.send_message(
                    RequestToSpeak(), AgentId(writer_source, "default")
                )

        elif source == "User":
            # Forward the product name to ProductInformationProviderAgent
            await self.send_message(
                GroupChatMessage(
                    body=UserMessage(
                        content=message.body.content, source="MarketingManager"
                    )
                ),
                self._product_info_provider,
            )
            # Request ProductInformationProviderAgent to speak
            await self.send_message(RequestToSpeak(), self._product_info_provider)
        else:
            # Handle other cases if needed
            print(f"Received message from {source}: {message.body.content}")
            pass

    @message_handler
    async def handle_request_to_speak(
        self, message: RequestToSpeak, ctx: MessageContext
    ) -> None:
        if self._product_info is None:
            # Start by requesting product information
            await self.send_message(RequestToSpeak(), self._product_info_provider)
        else:
            print("All agents have spoken. MarketingManager is idle.")
