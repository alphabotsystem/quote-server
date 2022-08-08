from os import environ
environ["PRODUCTION_MODE"] = environ["PRODUCTION_MODE"] if "PRODUCTION_MODE" in environ and environ["PRODUCTION_MODE"] else ""

from time import time, sleep
from uuid import uuid4
from fastapi import FastAPI, Request
from uvicorn import Config, Server
from asyncio import new_event_loop, set_event_loop, create_task
from traceback import format_exc

from google.cloud.firestore import AsyncClient as FirestoreClient
from google.cloud.firestore import ArrayUnion
from google.cloud.error_reporting import Client as ErrorReportingClient

from components.alternativeme import Alternativeme
from components.cnnbusiness import CNNBusiness
from components.ccxt import CCXT
from components.coingecko import CoinGecko
from components.iexc import IEXC
from components.serum import Serum


app = FastAPI()
database = FirestoreClient()
logging = ErrorReportingClient(service="details_server")
loop = new_event_loop()
set_event_loop(loop)

async def request_quote(request):
	payload, finalMessage, message = {}, None, None

	for platform in request["platforms"]:
		currentRequest = request.get(platform)

		if platform == "Alternative.me":
			payload, message = await loop.run_in_executor(None, Alternativeme.request_quote, currentRequest)
		elif platform == "CNN Business":
			payload, message = await loop.run_in_executor(None, CNNBusiness.request_quote, currentRequest)
		elif platform == "CoinGecko":
			payload, message = await loop.run_in_executor(None, CoinGecko.request_quote, currentRequest)
		elif platform == "CCXT":
			payload, message = await loop.run_in_executor(None, CCXT.request_quote, currentRequest)
		elif platform == "Serum":
			payload, message = await loop.run_in_executor(None, Serum.request_quote, currentRequest)
		elif platform == "IEXC":
			payload, message = await loop.run_in_executor(None, IEXC.request_quote, currentRequest)
		elif platform == "LLD":
			payload, message = await loop.run_in_executor(None, CCXT.request_lld, currentRequest)

		if bool(payload):
			if not request.get("bot", False) and currentRequest["ticker"].get("base") is not None:
				create_task(database.document(f"dataserver/statistics/{currentRequest.get('parserBias')}/{int(time() // 3600 * 3600)}").set({
					currentRequest["ticker"].get("base"): ArrayUnion([str(request.get("authorId"))]),
				}, merge=True))
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
		elif platform == "IEXC":
			payload, message = await loop.run_in_executor(None, IEXC.request_depth, currentRequest)

		if bool(payload):
			if not request.get("bot", False) and currentRequest["ticker"].get("base") is not None:
				create_task(database.document(f"dataserver/statistics/{currentRequest.get('parserBias')}/{int(time() // 3600 * 3600)}").set({
					currentRequest["ticker"].get("base"): ArrayUnion([str(request.get("authorId"))]),
				}, merge=True))
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
		elif platform == "IEXC":
			payload, message = await loop.run_in_executor(None, IEXC.request_details, currentRequest)

		if bool(payload):
			if not request.get("bot", False) and currentRequest["ticker"].get("base") is not None:
				create_task(database.document(f"dataserver/statistics/{currentRequest.get('parserBias')}/{int(time() // 3600 * 3600)}").set({
					currentRequest["ticker"].get("base"): ArrayUnion([str(request.get("authorId"))]),
				}, merge=True))
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
	config = Config(app=app, port=int(environ.get("PORT", 8080)), host="0.0.0.0", loop=loop)
	server = Server(config)
	loop.run_until_complete(server.serve())