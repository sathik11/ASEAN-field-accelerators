from dataclasses import dataclass, asdict
from typing import List

from autogen_core.components import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
    Image,
)
from autogen_core.components.models import (
    LLMMessage,
    AssistantMessage,
    ChatCompletionClient,
    SystemMessage,
    UserMessage,
)
from autogen_core.base import MessageContext, AgentId

import openai
import asyncio


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
                "You are a marketing email writer. Write a compelling email promoting our new product."
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
                "You are a social media manager. Write an engaging Facebook post promoting our new product."
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
                "You are an editor. Review the draft and reply with 'APPROVE' if it's good, or provide suggestions for improvement. Consider the below guidelines when reviewing:\n\n1. Is the content engaging and informative?\n2. Is the tone appropriate for the target audience?\n3. Are there any grammatical errors or typos?"
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
        self._approved_drafts = 0
        self._output_queue = output_queue

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

            # Start the drafting process with the first writer
            await self.send_message(
                RequestToSpeak(), self._writers[self._current_writer_index]
            )

        elif source in ["EmailWriter", "FacebookPostWriter", "TwitterPostWriter"]:
            # Send draft to Editor
            await self.send_message(
                GroupChatMessage(body=message.body),
                self._editor,
            )
            # Request Editor to speak
            await self.send_message(RequestToSpeak(), self._editor)

        elif source == "Editor":
            content = message.body.content.upper()
            if "APPROVE" in content:
                self._approved_drafts += 1
                if self._approved_drafts < len(self._writers):
                    # Proceed to the next writer
                    self._current_writer_index += 1
                    next_writer = self._writers[self._current_writer_index]
                    await self.send_message(RequestToSpeak(), next_writer)
                else:
                    print("All drafts have been approved.")
            else:
                # Send feedback back to the current writer
                current_writer = self._writers[self._current_writer_index]
                await self.send_message(
                    GroupChatMessage(body=message.body),
                    current_writer,
                )
                # Request writer to revise
                await self.send_message(RequestToSpeak(), current_writer)

        elif source == "User":
            # Handle user messages
            await self.send_message(RequestToSpeak(), self._product_info_provider)
        else:
            # Handle other cases if needed
            # print(f"Received message from {source}: {message.body.content}")
            pass

    @message_handler
    async def handle_request_to_speak(
        self, message: RequestToSpeak, ctx: MessageContext
    ) -> None:
        if self._product_info is None:
            # Start by requesting product information
            await self.send_message(RequestToSpeak(), self._product_info_provider)
        else:
            # Proceed with the drafting process
            await self.send_message(
                RequestToSpeak(), self._writers[self._current_writer_index]
            )
