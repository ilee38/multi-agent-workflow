# AI Multi-agent Workflow

This is the source code for my blog post [Building AI Multi-agent Workflows](https://stemhash.com/ai-multi-agent-workflows/).

It's a simple implementation of a multi-agent workflow to analyze stock market data and make investment recommendations. It uses the [AutoGen framework](https://microsoft.github.io/autogen/stable/index.html). See my blog post above for more details.

## Pre-requisites and Dependencies

### Azure OpenAI
The AI agents in the workflow use an Azure OpenAI model client. This means that you need to have an Azure subscription and an Azure OpenAI resource with a model deployed (in Azure AI Foundry). In this case, we're using gpt-4o. 

If you want to use a different model, modify the `get_azure_openai_chat_completion_client()` method on line 185 in *agents_workflow.py* to reflect this.

**Important**: Wether you use a different model or not, make sure the parameters to `AzureOpenAIChatCompletionClient()` on line 191 in *agents_workflow.py* match your Azure OpenAI's deployment information.

Once you have your AI model deployment, set an environment variable as:

```bash
MY_AZURE_OPENAI_ENDPOINT="[YOUR_AZURE_OPENAI_SERVICE_ENDPOINT]"
```

Replacing the `"[YOUR_AZURE_OPENAI_SERVICE_ENDPOINT]"` placeholder with your own Azure OpenAI Service endpoint (you can find this information on your Azure AI Foundry dashboard).

#### Azure Auth
Additionally, our model client uses Azure Active Directory (AAD) authentication. You need to assign the *Cognitive Services OpenAI User* role to your Azure user's identity (Microsoft Entra ID).

Once all of the above is configured, make sure you're signed in to your Azure account from your local environment. To sign-in, use the Azure cli on your terminal. Sign-in with the same user that you assigned the above RBAC role to.

### If Not Using Azure OpenAI
However, if you prefer to use other AI model clients—e.g. Gemini, OpenAI, a model hosted on Anthropic, or from Ollama—you'll need to modify the client creation method in the source code.

Refer to [AutoGen's docuementation here](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html) to implement the new client creation method. Then assign the client to the `model_client` variable on line 202 in *agents_workflow.py*.

Note: in this case you don't need to create the environment variable `MY_AZURE_OPENAI_ENDPOINT` as mentioned above.

### Sec-Api Library API Key
The data retrieval tool uses the *sec-api* python library, which requires an API key. You can obtain a free API key from [here](https://sec-api.io/). Once you have your key, create an environment variable as:

```bash
MY_SEC_API_KEY="[YOUR_API_KEY]"
```

Replacing the placeholder with the value of your API key.

Finally, update the value of the constants on lines 7 and 8 in *agents_tools.py* with your name and email address. This is needed in order to query the [SEC's data API](https://www.sec.gov/search-filings).

```python
7 HTTP_USER_AGENT_NAME = "[YOUR NAME]"
8 HTTP_USER_AGENT_EMAIL = "[YOUR EMAIL]"
```

## Running the Code
To run the code, clone this repository to your machine. Then create a python virtual environment as follows.

***Important***: AutoGen requires python version 3.10 or higher.

1. On the terminal, navigate to the repository's directory. Then execute:

   ```bash
   python -m venv <venv_name>
   ```
   where <venv_name> is the name you want to give the virtual environment

2. To activate the environment:

      On MacOS/Linx execute:

   ```bash
   source <venv_name>/bin/activate
   ```
      On Windows execute:

   ```bash
   .\<venv_name>\Scripts\activate
   ```

3. With the virtual environment active, install the required libraries with pip:

    ```bash
    pip install -r ./requirements.txt
    ```

4. Now you can run the `agents_workflow.py` as:

   ```bash
     python3 agents_workflow.py
   ```

5. When you're done, deactivate the venv with:

   ```bash
   deactivate
   ```