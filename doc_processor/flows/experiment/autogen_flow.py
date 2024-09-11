from promptflow.connections import AzureOpenAIConnection, CustomConnection
import asyncio
from typing import Literal
import os
import tempfile
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
import autogen
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
from autogen import UserProxyAgent, ConversableAgent, ChatResult
from autogen.function_utils import get_function_schema
from azure.cosmos import exceptions, PartitionKey
from azure.cosmos.aio import CosmosClient
import uuid
import copy
from azure.cosmos import CosmosClient as CClient
from autogen.agentchat.contrib.capabilities import transforms
import json
import yaml
from azure.storage.blob import BlobServiceClient


class AutogenFlow:

    def __init__(
        self,
        agent_config: AzureOpenAIConnection,
        docinterpreter_config: CustomConnection,
        cosmosdb_config: CustomConnection,
        storage_config: CustomConnection,
        mesg_queue: asyncio.Queue,
        customer_id: str,
        azure_model_deployment: str = "gpt-4o",
    ):
        # Re-using variables for api_key, base_url, and azure_endpoint
        agent_api_key = agent_config.api_key
        agent_azure_endpoint = agent_config.api_base
        oassistant_api_key = agent_api_key
        oassistant_azure_endpoint = agent_azure_endpoint

        self.cosmos_endpoint = cosmosdb_config.configs["endpoint"]
        os.environ["COSMOSDB_ENDPOINT"] = self.cosmos_endpoint

        self.cosmos_key = cosmosdb_config.secrets["key"]
        os.environ["COSMOSDB_KEY"] = self.cosmos_key

        self.cosmos_db_name = cosmosdb_config.configs["db_name"]
        os.environ["COSMOS_DB_NAME"] = self.cosmos_db_name

        self.cosmos_container_name = cosmosdb_config.configs["container_name"]
        os.environ["COSMOS_CONTAINER_NAME"] = self.cosmos_container_name

        self.storage_account_url = storage_config.configs["url"]
        self.storage_account_key = storage_config.secrets["key"]

        self.conversation_id = str(uuid.uuid4())
        self.customer_id = customer_id
        self.mesg_queue = mesg_queue
        self.doc_assistant_name = "DocumentProcessingAssistant"
        self.customer_profile_qna_name = "CustomerProfileQnAAssistant"
        self.vector_store_name = f"vector_store_{customer_id}"
        self.document_intelligence_endpoint = docinterpreter_config.configs["endpoint"]
        self.document_intelligence_key = docinterpreter_config.secrets["key"]
        self.config_list = [
            {
                "model": azure_model_deployment,
                "api_key": agent_api_key,
                "base_url": agent_azure_endpoint,
                "api_type": "azure",
                "api_version": "2024-05-01-preview",
                # Use the API version that supports Assistant model and avoid
                # Error code: 404 - {'error': {'code': '404', 'message': 'Resource not found'}}
            },
        ]

        self.client = AzureOpenAI(
            api_key=oassistant_api_key,
            api_version="2024-05-01-preview",
            # Use the API version that supports Assistant model and avoid
            # Error code: 404 - {'error': {'code': '404', 'message': 'Resource not found'}}
            azure_endpoint=oassistant_azure_endpoint,
        )

        self.llm_config = {
            "cache_seed": 78645,
            "temperature": 0,
            "config_list": self.config_list,
            "timeout": 120,
        }

        # check of vector store exists
        vector_store = next(
            (
                vector_store
                for vector_store in self.client.beta.vector_stores.list()
                if vector_store.name == self.vector_store_name
            ),
            None,
        )
        # If the vector store exists, use it directly without additional retrieval
        if vector_store:
            self.vector_store_id = vector_store.id
        else:
            vector_store = self.client.beta.vector_stores.create(
                name=self.vector_store_name
            )
            self.vector_store_id = vector_store.id
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Construct the file path relative to the current script's directory
        # read the yaml file for agent configurations
        with open(os.path.join(current_dir, "agents_config.yml"), "r") as file:
            agents_config_yaml = yaml.safe_load(file)
            agents_config = json.loads(
                json.dumps(agents_config_yaml, separators=(",", ":"))
            )

        # Create user proxy agent
        self.user_proxy = UserProxyAgent(
            name="UserProxy",
            max_consecutive_auto_reply=0,
            human_input_mode="NEVER",
            code_execution_config={
                "work_dir": "coding",
                "use_docker": False,
            },
            is_termination_msg=lambda x: x.get("content", "")
            .rstrip()
            .endswith("TERMINATE"),
        )
        # Create QA agent
        self.qa = ConversableAgent(
            name=agents_config["QualityAssurancePlanner"]["name"],
            system_message=agents_config["QualityAssurancePlanner"]["system_message"],
            llm_config=self.llm_config,
        )
        # Create financial agent
        self.finance_agent = ConversableAgent(
            name=agents_config["FinancialAgent"]["name"],
            llm_config=self.llm_config,
            system_message=agents_config["FinancialAgent"]["system_message"],
        )
        # Create medical agent
        self.medical_agent = ConversableAgent(
            name=agents_config["MedicalAgent"]["name"],
            llm_config=self.llm_config,
            system_message=agents_config["MedicalAgent"]["system_message"],
        )
        # Create assistant agent
        getFileContentSchema = get_function_schema(
            self.get_file_content,
            name=self.get_file_content.__name__,
            description="Extract the content of a file in markdown format and upload it to the vector store.",
        )
        getLastMessageSchema = get_function_schema(
            self.get_last_message_v2,
            name=self.get_last_message_v2.__name__,
            description="Get the last message from the chat history for the given customer_id.",
        )
        # Get the list of assistants
        assistants = list(self.client.beta.assistants.list())
        # Find the document processing assistant
        doc_assistant_agent = self.find_assistant_by_name(
            assistants, self.doc_assistant_name
        )
        doc_assistant_config = {
            "assistant_id": doc_assistant_agent.id if doc_assistant_agent else None,
            "tools": [getFileContentSchema],
            "temperature": 1,
        }
        # Create document processing assistant
        self.doc_processing_agent = GPTAssistantAgent(
            name=agents_config["DocumentProcessingAssistant"]["name"],
            instructions=agents_config["DocumentProcessingAssistant"]["system_message"],
            llm_config=self.llm_config,
            assistant_config=doc_assistant_config,
            function_map={
                "get_file_content": self.get_file_content,
                # "get_last_message": self.get_last_message_v2,
            },
            overwrite_tools=True,
            overwrite_instructions=True,
        )
        # Find the customer profile QnA assistant
        customer_profile_qna_agent = self.find_assistant_by_name(
            assistants, self.customer_profile_qna_name
        )
        qna_assistant_config = {
            "assistant_id": (
                customer_profile_qna_agent.id if customer_profile_qna_agent else None
            ),
            "tools": [{"type": "file_search"}],
            "tool_resources": {
                "file_search": {"vector_store_ids": [self.vector_store_id]}
            },
            "temperature": 1,
        }
        # print(f"QnA assistant config: {qna_assistant_config}")

        # Create customer profile QnA assistant
        self.customer_profile_qna = GPTAssistantAgent(
            name=agents_config["CustomerProfileQnAAssistant"]["name"],
            instructions=agents_config["CustomerProfileQnAAssistant"]["system_message"],
            llm_config=self.llm_config,
            assistant_config=qna_assistant_config,
            overwrite_tools=True,
            overwrite_instructions=True,
        )
        # Register reply functions
        self.agents_list = [
            self.user_proxy,
            self.doc_processing_agent,
            self.customer_profile_qna,
            self.qa,
            self.finance_agent,
            self.medical_agent,
        ]
        for agent in self.agents_list:
            agent.register_reply(
                [autogen.Agent, None],
                reply_func=self.log_message,
                config={"callback": None},
            )

    def get_file_content(self, file_paths: list) -> str:
        """
        Extract the content of a file into markdown format and add it to the vector store for RAG.
        """
        document_intelligence_client = DocumentIntelligenceClient(
            endpoint=self.document_intelligence_endpoint,
            credential=AzureKeyCredential(self.document_intelligence_key),
        )
        md_file_paths = []
        for file_path in file_paths:
            # Check if file_path is an Azure Blob link
            if (
                file_path.startswith("https://")
                and "blob.core.windows.net/" in file_path
            ):
                #
                # Assuming you have the storage account URL and the container name

                container_name = "demo-data"
                # get the last part of the URL as the blob name
                blob_name = file_path.split("/")[-1]
                # Authenticate with the storage account
                blob_service_client = BlobServiceClient(
                    account_url=self.storage_account_url,
                    credential=self.storage_account_key,
                )
                # Assuming blob_service_client is already authenticated and available
                blob_client = blob_service_client.get_blob_client(
                    container=container_name, blob=blob_name
                )

                with open("tempfile", "wb") as temp_blob_file:
                    download_stream = blob_client.download_blob()
                    download_stream.readinto(temp_blob_file)

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".md"
                ) as temp_blob_file:
                    download_stream = blob_client.download_blob()
                    download_stream.readinto(temp_blob_file)
                    temp_file_name = temp_blob_file.name

                # condition = True  # Define the condition as needed
                # file_to_read = temp_file_name if condition else file_path

            with open(temp_file_name, "rb") as f:
                poller = document_intelligence_client.begin_analyze_document(
                    "prebuilt-layout",
                    output_content_format="markdown",
                    analyze_request=f,
                    content_type="application/octet-stream",
                )
            result = poller.result()
            # Extract filename without path and create a temp markdown file in the current directory
            base_filename = os.path.splitext(os.path.basename(file_path))[0] + ".md"
            temp_md_path = os.path.join(tempfile.gettempdir(), base_filename)
            with open(temp_md_path, "w") as temp_file:
                temp_file.write(result.content)
                md_file_paths.append(temp_md_path)
        self.client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=self.vector_store_id,
            files=[open(temp_md_path, "rb") for temp_md_path in md_file_paths],
        )
        # If a temporary blob file was created, delete it as well
        if "tempfile" in locals():
            os.remove("tempfile")
        return "Done processing files. Ask **CustomerProfileQnAAssistant** to search for the content."

    def get_last_message_v2(self, customer_id: str) -> str:
        """
        Extract the last chat history message of the chat.
        """
        # Retrieve environment variables
        COSMOSDB_ENDPOINT = os.getenv("COSMOSDB_ENDPOINT", "Default Endpoint")
        COSMOSDB_KEY = os.getenv("COSMOSDB_KEY", "Default Key")
        COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME", "Default DB Name")
        COSMOS_CONTAINER_NAME = os.getenv(
            "COSMOS_CONTAINER_NAME", "Default Container Name"
        )
        client = CClient(COSMOSDB_ENDPOINT, COSMOSDB_KEY)
        database = client.get_database_client(COSMOS_DB_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)
        # get the last message based on timestamp from given customer id
        query = f"SELECT TOP 1 * FROM c WHERE c.customer_id = '{customer_id}' ORDER BY c.timestamp DESC"
        print(f"Query - {query}")
        try:
            item = next(
                container.query_items(query, enable_cross_partition_query=False)
            )
            chat_history = item["chat_history"]
            max_msg_transfrom = transforms.MessageHistoryLimiter(max_messages=5)
            processed_messages = max_msg_transfrom.apply_transform(
                copy.deepcopy(chat_history)
            )
            print(f"processed_messages - {processed_messages}")
            filtered_messages = [
                msg
                for msg in processed_messages
                if msg.get("role") in ["user", "assistant"]
            ]

            return f"Below is last chat history in JSON format {json.dumps(filtered_messages)}"
        except StopIteration:
            print(
                f"No chat history available for the given customer id.- {customer_id} - EXCEPTION"
            )
            return f"There is no chat history available for the given customer id.- {customer_id}"

    def find_assistant_by_name(self, assistants, name):
        return next(
            (assistant for assistant in assistants if assistant.name == name), None
        )

    def log_message(
        self, recipient, messages=[], sender=None, config=None
    ) -> tuple[Literal[False], None]:
        self.mesg_queue.put_nowait(
            {
                "sender": sender.name,
                "receiver": recipient.name,
                "messages": messages,
            }
        )
        return False, None

    async def add_to_cosmos(
        self,
        group_chat_message: list[dict],
    ) -> dict:
        async def get_or_create_database(client, db_name):
            try:
                return await client.create_database(id=db_name)
            except exceptions.CosmosResourceExistsError:
                return client.get_database_client(db_name)

        async def get_or_create_container(database, container_name):
            try:
                return await database.create_container(
                    id=container_name,
                    partition_key=PartitionKey(path="/customer_id"),
                )
            except exceptions.CosmosResourceExistsError:
                return database.get_container_client(container_name)

        async with CosmosClient(self.cosmos_endpoint, self.cosmos_key) as client:
            database = await get_or_create_database(client, self.cosmos_db_name)
            container = await get_or_create_container(
                database, self.cosmos_container_name
            )

            data = {
                "id": str(uuid.uuid4()),
                "conversation_id": self.conversation_id,
                "customer_id": self.customer_id,
                "chat_history": group_chat_message,
            }
            result = await container.upsert_item(data)
            return result

    async def run_chat(
        self, question: str, previous_state: list[dict] = None
    ) -> autogen.ChatResult:
        await self.mesg_queue.put(
            {
                "sender": "GroupChatManager",
                "receiver": "EndUser",
                "messages": [x.name for x in self.agents_list],
            }
        )
        # is_resuming = bool(previous_state)

        # Create group chat
        self.groupchat = autogen.GroupChat(
            agents=self.agents_list,
            messages=[],
            max_round=10,
            send_introductions=True,
        )
        # Create group chat manager
        self.manager = autogen.GroupChatManager(
            groupchat=self.groupchat,
            name="GroupChatManager",
            llm_config=self.llm_config,
            system_message="Group chat manager responsible for managing the group chat between the agents and the user.",
        )

        chat_results: ChatResult = await self.user_proxy.a_initiate_chat(
            self.manager,
            message=question,
            summary_method="reflection_with_llm",
            clear_history=True,
        )

        # Send the chat results to the user
        await self.mesg_queue.put(
            {
                "sender": "GroupChatManager",
                "receiver": "EndUser",
                "messages": chat_results.summary,
                "cost": chat_results.cost,
            }
        )
        await self.mesg_queue.put(None)  # Signal end of chat
        group_chat_messages = self.groupchat.messages
        # print(f"Group chat messages - {group_chat_messages}")
        await self.add_to_cosmos(group_chat_messages)
        return {"summary": chat_results.summary, "cost": chat_results.cost}
