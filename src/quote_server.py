from os import environ
environ["PRODUCTION"] = environ["PRODUCTION"] if "PRODUCTION" in environ and environ["PRODUCTION"] else ""

from time import time, sleep
from uuid import uuid4
from fastapi import FastAPI, Request
from uvicorn import Config, Server
from asyncio import new_event_loop, set_event_loop
from traceback import format_exc

from google.cloud.error_reporting import Client as ErrorReportingClient

from components.alternativeme import Alternativeme
from components.blockchair import Blockchair
from components.cnnbusiness import CNNBusiness
from components.ccxt import CCXT
from components.coingecko import CoinGecko
from components.chain import Chain
from components.twelvedata import Twelvedata


app = FastAPI()
logging = ErrorReportingClient(service="details_server")
loop = new_event_loop()
set_event_loop(loop)

async def request_quote(request):
	payload, finalMessage, message = {}, None, None

	for platform in request["platforms"]:
		currentRequest = request.get(platform)

		if platform == "Alternative.me":
			payload, message = await loop.run_in_executor(None, Alternativeme.request_quote, currentRequest)
		elif platform == "Blockchair":
			payload, message = await loop.run_in_executor(None, Blockchair.request_quote, currentRequest)
		elif platform == "CNN Business":
			payload, message = await loop.run_in_executor(None, CNNBusiness.request_quote, currentRequest)
		elif platform == "CoinGecko":
			payload, message = await loop.run_in_executor(None, CoinGecko.request_quote, currentRequest)
		elif platform == "On-Chain":
			payload, message = await loop.run_in_executor(None, Chain.request_quote, currentRequest)
		elif platform == "CCXT":
			payload, message = await loop.run_in_executor(None, CCXT.request_quote, currentRequest)
		elif platform == "Twelvedata":
			payload, message = await loop.run_in_executor(None, Twelvedata.request_quote, currentRequest)

		if bool(payload):
			return {"response": payload, "message": message}
		elif message is not None:
			finalMessage = message

	return {"response": None, "message": finalMessage}

async def request_depth(request):
	payload, finalMessage, message = {}, None, None

	for platform in request["platforms"]:
		currentRequest = request.get(platform)

		if platform == "CCXT":
			payload, message = await loop.run_in_executor(None, CCXT.request_depth, currentRequest)

		if bool(payload):
			return {"response": payload, "message": message}
		elif message is not None:
			finalMessage = message

	return {"response": None, "message": finalMessage}

async def request_detail(request):
	payload, finalMessage, message = {}, None, None

	for platform in request["platforms"]:
		currentRequest = request.get(platform)

		if platform == "CoinGecko":
			payload, message = await loop.run_in_executor(None, CoinGecko.request_details, currentRequest)
		elif platform == "Twelvedata":
			payload, message = await loop.run_in_executor(None, Twelvedata.request_details, currentRequest)

		if bool(payload):
			return {"response": payload, "message": message}
		elif message is not None:
			finalMessage = message

	return {"response": None, "message": finalMessage}

@app.post("/quote")
async def run(req: Request):
	request = await req.json()
	return await request_quote(request)

@app.post("/depth")
async def run(req: Request):
	request = await req.json()
	return await request_depth(request)

@app.post("/detail")
async def run(req: Request):
	request = await req.json()
	return await request_detail(request)

if __name__ == "__main__":
	print("[Startup]: Quote Server is online")
	# config = Config(app=app, port=int(environ.get("PORT", 8080)), host="0.0.0.0", loop=loop)
	config = Config(app=app, port=6900, host="0.0.0.0", loop=loop)
	server = Server(config)
	loop.run_until_complete(server.serve())