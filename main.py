# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import os
import sys

import aiohttp

from fastapi import Request, FastAPI, HTTPException

from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.tools import MoveFileTool, format_tool_to_openai_function
from langchain.schema import HumanMessage, AIMessage, ChatMessage, FunctionMessage

from linebot import (
    AsyncLineBotApi, WebhookParser
)
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from stock_tool import StockPriceTool
from stock_tool import get_stock_price

import os
import openai
import json

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())  # read local .env file
openai.api_key = os.environ['OPENAI_API_KEY']

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('ChannelSecret', None)
channel_access_token = os.getenv('ChannelAccessToken', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

app = FastAPI()
session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(session)
line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
parser = WebhookParser(channel_secret)

# Langchain
llm = ChatOpenAI(temperature=0.9, model='gpt-3.5-turbo')

# Prepare openai.functions
tools = [StockPriceTool()]
functions = [format_tool_to_openai_function(t) for t in tools]

# test function
print("func=")
print(functions[0])
memory = ConversationBufferWindowMemory(k=5)
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=False
)


# A demo code how to call OpenAI completion
def get_completion(prompt, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    return response.choices[0].message["content"]


@app.post("/callback")
async def handle_callback(request: Request):
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

        print(event.message.text)
        ai_message = llm.predict_messages(
            [HumanMessage(content=event.message.text)], functions=functions)
        print(ai_message)

        # parse args
        _args = json.loads(
            ai_message.additional_kwargs['function_call'].get('arguments'))
        print(_args)
        tool_result = tools[0](_args)
        print(tool_result)

        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=tool_result)
        )

    return 'OK'
