# module-0: basics

> Source notebook: `../langchain-academy/module-0/basics.ipynb`

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/langchain-ai/langchain-academy/blob/main/module-0/basics.ipynb) [![Open in LangChain Academy](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/66e9eba12c7b7688aa3dbb5e_LCA-badge-green.svg)](https://academy.langchain.com/courses/take/intro-to-langgraph/lessons/56295530-getting-set-up-video-guide)

# LangChain Academy

Welcome to LangChain Academy! 

## Context

At LangChain, we aim to make it easy to build LLM applications. One type of LLM application you can build is an agent. There’s a lot of excitement around building agents because they can automate a wide range of tasks that were previously impossible. 

In practice though, it is incredibly difficult to build systems that reliably execute on these tasks. As we’ve worked with our users to put agents into production, we’ve learned that more control is often necessary. You might need an agent to always call a specific tool first or use different prompts based on its state. 

To tackle this problem, we’ve built [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) — a framework for building agent and multi-agent applications. Separate from the LangChain package, LangGraph’s core design philosophy is to help developers add better precision and control into agent workflows, suitable for the complexity of real-world systems.

## Course Structure

The course is structured as a set of modules, with each module focused on a particular theme related to LangGraph. You will see a folder for each module, which contains a series of notebooks. A video will accompany each notebook to help walk through the concepts, but the notebooks are also stand-alone, meaning that they contain explanations and can be viewed independently of the videos. Each module folder also contains a `studio` folder, which contains a set of graphs that can be loaded into [LangSmith Studio](https://docs.langchain.com/langsmith/quick-start-studio), our IDE for building LangGraph applications.

## Setup

Before you begin, please follow the instructions in the `README` to create an environment and install dependencies.

## Chat models

In this course, we'll use Chat Models, which take a sequence of messages as input and return messages as output. LangChain supports many models via [third-party integrations](https://docs.langchain.com/oss/python/integrations/chat). By default, the course will use  [ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai) because it is both popular and performant. As noted, please ensure that you have an `OPENAI_API_KEY`.

Let's check that your `OPENAI_API_KEY` is set and, if not, you will be asked to enter it.

```python
%%capture --no-stderr
%pip install --quiet -U langchain_openai langchain_core langchain_community langchain-tavily
```

```python
import os, getpass

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("OPENAI_API_KEY")
```

[Here](https://docs.langchain.com/oss/python/langchain/models) is a useful how-to for all the things that you can do with chat models, but we'll show a few highlights below. If you've run `pip install -r requirements.txt` as noted in the README, then you've installed the `langchain-openai` package. With this, we can instantiate our `ChatOpenAI` model object. You can see pricing for various models [here](https://openai.com/api/pricing/). The notebooks will default to `gpt-4o` because it offers a good balance of quality, price, and speed, but you can also opt for the lower-priced `gpt-3.5` series or more recent models.

There are [a few standard parameters](https://docs.langchain.com/oss/python/langchain/models#parameters) that we can set with chat models. Two of the most common are:

* `model`: the name of the model
* `temperature`: the sampling temperature

`Temperature` controls the randomness or creativity of the model's output where low temperature (close to 0) is more deterministic and focused outputs. This is good for tasks requiring accuracy or factual responses. High temperature (close to 1) is good for creative tasks or generating varied responses.

```python
from langchain_openai import ChatOpenAI
gpt4o_chat = ChatOpenAI(model="gpt-4o", temperature=0)
gpt35_chat = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0)
```

Chat models in LangChain have a number of [default methods](https://reference.langchain.com/python/langchain_core/runnables). For the most part, we'll be using:

* [stream](https://docs.langchain.com/oss/python/langchain/models#stream): stream back chunks of the response
* [invoke](https://docs.langchain.com/oss/python/langchain/models#invoke): call the chain on an input

And, as mentioned, chat models take [messages](https://docs.langchain.com/oss/python/langchain/messages) as input. Messages have a role (that describes who is saying the message) and a content property. We'll be talking a lot more about this later, but here let's just show the basics.

```python
from langchain_core.messages import HumanMessage

# Create a message
msg = HumanMessage(content="Hello world", name="Lance")

# Message list
messages = [msg]

# Invoke the model with a list of messages 
gpt4o_chat.invoke(messages)
```

We get an `AIMessage` response. Also, note that we can just invoke a chat model with a string. When a string is passed in as input, it is converted to a `HumanMessage` and then passed to the underlying model.

```python
gpt4o_chat.invoke("hello world")
```

```python
gpt35_chat.invoke("hello world")
```

The interface is consistent across all chat models and models are typically initialized once at the start up each notebooks. 

So, you can easily switch between models without changing the downstream code if you have strong preference for another provider.

## Search Tools

You'll also see [Tavily](https://tavily.com/) in the README, which is a search engine optimized for LLMs and RAG, aimed at efficient, quick, and persistent search results. As mentioned, it's easy to sign up and offers a generous free tier. Some lessons (in Module 4) will use Tavily by default but, of course, other search tools can be used if you want to modify the code for yourself.

```python
_set_env("TAVILY_API_KEY")
```

```python
from langchain_tavily import TavilySearch  # updated at 1.0

tavily_search = TavilySearch(max_results=3)

data = tavily_search.invoke({"query": "What is LangGraph?"})
search_docs = data.get("results", data)
```

```python
search_docs
```
