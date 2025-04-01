import asyncio
import json
import os

from dataclasses import dataclass
from typing import List
from autogen_core.tools import FunctionTool, Tool
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import AzureCliCredential, get_bearer_token_provider
from agents_tools import get_most_recent_10k_balance_sheet
from autogen_core import (
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    TopicId,
    FunctionCall,
    CancellationToken,
    message_handler,
    type_subscription
)
from autogen_core.models import (
    ChatCompletionClient, 
    SystemMessage, 
    UserMessage,
    LLMMessage, 
    AssistantMessage, 
    FunctionExecutionResult, 
    FunctionExecutionResultMessage
)


MY_AZURE_OPENAI_API_KEY = os.environ.get("MY_AZURE_OPENAI_API_KEY")
MY_AZURE_OPENAI_ENDPOINT = os.environ.get("MY_AZURE_OPENAI_ENDPOINT")


@dataclass
class Message:
    content: str


# Topics
data_extractor_topic_type = "DataExtractorAgent"
financial_analyst_topic_type = "FinancialAnalystAgent"
recommender_topic_type = "RecommenderAgent"

# Agent Tools
most_recent_10k_balance_sheet_tool = FunctionTool(
    get_most_recent_10k_balance_sheet,
    description="Obtains the most recent cash flow statement in the 10-K report filing to the SEC for the given ticker symbol."
)


# Agent Definitions
@type_subscription(topic_type=data_extractor_topic_type)
class DataExtractorAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A financial data extractor agent.")
        self._system_messages: List[LLMMessage] = [SystemMessage(
            content=(
                "You are a corporate financial data analyst.\n"
                "You will be given the ticker symbol of a company, and you are to obtain the most recent cash flow statement in its 10-K filing from the SEC for that company.\n"
                "The data you obtain might be in JSON format, you are to identify and extract the most important financial metrics from the filing.\n"
                "Once you have extracted this information, provide a detailed report including the name of the company, the ticker symbol, and the extracted financial metrics."
            )
        )]
        self._model_client = model_client
        self._tools: List[Tool] = [most_recent_10k_balance_sheet_tool]

    @message_handler
    async def handle_outie_message(self, message: Message, context: MessageContext) -> None:
        # Create session of messages
        session: List[LLMMessage] = self._system_messages + [UserMessage(content=message.content, source="user")]

        # Run chat completion with the tool
        llm_result = await self._model_client.create(
            messages=session,
            tools=self._tools,
            cancellation_token=context.cancellation_token,
        )

        # Add the result to the session
        session.append(AssistantMessage(content=llm_result.content, source=self.id.key))

        # Execute the tool calls
        results = await asyncio.gather(*[self._execute_tool_call(call, context.cancellation_token) for call in llm_result.content])

        # Add the function execution results to the session
        session.append(FunctionExecutionResultMessage(content=results))

        # Run the chat completion again to reflect on the history and function execution results.
        llm_result = await self._model_client.create(
            messages=session,
            cancellation_token=context.cancellation_token
        )
        response = llm_result.content
        assert isinstance(response, str)
        print(f"{'='*80}\n[{self.id.type}]:\n{response}\n")

        await self.publish_message(Message(response), topic_id=TopicId(financial_analyst_topic_type, source=self.id.key))

    async def _execute_tool_call(self, call: FunctionCall, cancellation_token: CancellationToken) -> FunctionExecutionResult:
        # Find the tool that corresponds to the call
        tool = next((tool for tool in self._tools if tool.name == call.name), None)
        assert tool is not None

        # Run the tool and capture the result
        try:
            arguments = json.loads(call.arguments)
            result = await tool.run_json(arguments, cancellation_token)

            return FunctionExecutionResult(
                call_id=call.id,
                content=tool.return_value_as_string(result),
                is_error=False,
                name=tool.name
            )
        except Exception as e:
            return FunctionExecutionResult(
                call_id=call.id,
                content=str(e),
                is_error=True,
                name=tool.name
            )


@type_subscription(topic_type=financial_analyst_topic_type)
class FinancialAnalystAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A financial analyst agent.")
        self._system_message = SystemMessage(
            content=(
                "You are a financial equities investor. Your investing strategy follows Value Investing.\n"
                "Following this strategy, you will analyze the financial information for a given company that is given to you.\n"
                "You are to perform Fundamental Analysis of the company to determine if it is a good investment.\n"
                "Provide a summary of your analysis and a recommendation on whether to invest in the company or not, based on its current stock price.\n"
                "You should include the following in your report:\n"
                " - A brief description of the company\n"
                " - Key financial ratios\n"
                " - Growth metrics\n"
                " - Industry and Competitive Analysis\n"
                " - Intrinsic Value calculation you performed using the DCF method\n"
                " - Qualitative factors such as management quality, risks, and economic moat\n"
            )
        )
        self._model_client = model_client

    @message_handler
    async def handle_intermediate_text(self, message: Message, context: MessageContext) -> None:
        prompt = f"Here is the financial information for the company:\n\n{message.content}"
        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=context.cancellation_token
        )
        response = llm_result.content
        assert isinstance(response, str)
        print(f"{'='*80}\n[{self.id.type}]:\n{response}\n")

        await self.publish_message(Message(response), topic_id=TopicId(recommender_topic_type, source=self.id.key))


@type_subscription(topic_type=recommender_topic_type)
class RecommenderAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A recommender agent.")
        self._system_message = SystemMessage(
            content=(
                "You are a financial advisor. You have been given a company's financial analysis report.\n"
                "Based on this report, you are to provide a recommendation on whether to invest in the company or not.\n"
                "Your recommendation should be supported by the analysis provided in the report and the current company's stock price.\n"
            )
        )
        self._model_client = model_client

    @message_handler
    async def handle_intermediate_text(self, message: Message, context: MessageContext) -> None:
        prompt = f"Here is the financial analysis report for the company:\n\n{message.content}"
        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=context.cancellation_token
        )
        response = llm_result.content
        assert isinstance(response, str)
        print(f"{'='*80}\n[{self.id.type}]:\n{response}\n")


def get_azure_openai_chat_completion_client() -> AzureOpenAIChatCompletionClient:
    # token_provider = get_bearer_token_provider(
    #     AzureCliCredential(tenant_id="6457b4da-84ce-4712-b20c-0a0dbf25829f"),
    #     "https://cognitiveservices.azure.com/.default"
    # )

    return AzureOpenAIChatCompletionClient(
        azure_deployment="gpt-4o",
        model="gpt-4o-2024-11-20",
        api_version="2024-10-21",
        azure_endpoint=MY_AZURE_OPENAI_ENDPOINT,
        #azure_ad_token_provider=token_provider
        api_key=MY_AZURE_OPENAI_API_KEY
    )
    

# Workflow
async def start_workflow(message : str) -> None:
    model_client = get_azure_openai_chat_completion_client() 

    runtime = SingleThreadedAgentRuntime()

    await DataExtractorAgent.register(
        runtime,
        type=data_extractor_topic_type,
        factory=lambda: DataExtractorAgent(model_client=model_client)
    )

    await FinancialAnalystAgent.register(
        runtime,
        type=financial_analyst_topic_type,
        factory=lambda: FinancialAnalystAgent(model_client=model_client)
    )

    await RecommenderAgent.register(
        runtime,
        type=recommender_topic_type,
        factory=lambda: RecommenderAgent(model_client=model_client)
    )

    runtime.start()

    await runtime.publish_message(
        Message(content=message),
        topic_id=TopicId(data_extractor_topic_type, source="default")
    )

    await runtime.stop_when_idle()


if __name__ == "__main__":
    message = input("What stock are you interested to buy (Enter the ticker symbol): ")
    asyncio.run(start_workflow(message))
