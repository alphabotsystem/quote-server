from os import environ
from signal import signal, SIGINT, SIGTERM
from time import time
from zmq import Context, ROUTER
from orjson import dumps, loads
from traceback import format_exc

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import ArrayUnion
from google.cloud.error_reporting import Client as ErrorReportingClient

from components.alternativeme import Alternativeme
from components.ccxt import CCXT
from components.coingecko import CoinGecko
from components.iexc import IEXC
from components.serum import Serum


database = FirestoreClient()


class QuoteProcessor(object):
	def __init__(self):
		self.isServiceAvailable = True
		signal(SIGINT, self.exit_gracefully)
		signal(SIGTERM, self.exit_gracefully)

		self.logging = ErrorReportingClient(service="quote_server")

		try:
			rawData = CoinGecko.connection.get_coin_by_id(id="bitcoin", localization="false", tickers=False, market_data=True, community_data=False, developer_data=False)
			CoinGecko.lastBitcoinQuote = rawData["market_data"]["current_price"]["usd"]
		except: pass

		self.context = Context.instance()
		self.socket = self.context.socket(ROUTER)
		self.socket.bind("tcp://*:6900")

		print("[Startup]: Quote Server is online")

	def exit_gracefully(self):
		print("[Startup]: Quote Server is exiting")
		self.socket.close()
		self.isServiceAvailable = False

	def run(self):
		while self.isServiceAvailable:
			try:
				response = [dumps({}),  b""]
				message = self.socket.recv_multipart()
				if len(message) != 5: continue
				origin, delimeter, clientId, service, request = message
				request = loads(request)
				if request.get("timestamp") + 60 < time():
					print("Request received too late")
					continue

				if service == b"quote":
					response = self.request_quote(request, clientId)
				elif service == b"depth":
					response = self.request_depth(request, clientId)

			except (KeyboardInterrupt, SystemExit): return
			except Exception:
				print(format_exc())
				print(request)
				if environ["PRODUCTION_MODE"]: self.logging.report_exception()
			finally:
				try: self.socket.send_multipart([origin, delimeter] + response)
				except: pass
				request = None

	def request_quote(self, request, clientId):
		payload, quoteMessage, updatedQuoteMessage = {}, "", ""

		for platform in request["platforms"]:
			currentRequest = request.get(platform)

			if platform == "Alternative.me":
				payload, updatedQuoteMessage = Alternativeme.request_quote(currentRequest)
			elif platform == "CoinGecko":
				payload, updatedQuoteMessage = CoinGecko.request_quote(currentRequest)
			elif platform == "CCXT":
				payload, updatedQuoteMessage = CCXT.request_quote(currentRequest)
			elif platform == "Serum":
				payload, updatedQuoteMessage = Serum.request_quote(currentRequest, context=self.context)
			elif platform == "IEXC":
				payload, updatedQuoteMessage = IEXC.request_quote(currentRequest)
			elif platform == "LLD":
				payload, updatedQuoteMessage = CCXT.request_lld(currentRequest)

			if bool(payload):
				if clientId in [b"discord_alpha"] and currentRequest["ticker"].get("base") is not None:
					database.document("dataserver/statistics/{}/{}".format(currentRequest.get("parserBias"), int(time() // 3600 * 3600))).set({
						currentRequest["ticker"].get("base"): ArrayUnion([str(request.get("authorId"))]),
					}, merge=True)
				return [dumps(payload), updatedQuoteMessage.encode()]
			elif updatedQuoteMessage != "":
				quoteMessage = updatedQuoteMessage

		return [dumps({}), quoteMessage.encode()]

	def request_depth(self, request, clientId):
		payload, quoteMessage, updatedQuoteMessage = {}, "", ""

		for platform in request["platforms"]:
			currentRequest = request.get(platform)

			if platform == "CCXT":
				payload, updatedQuoteMessage = CCXT.request_depth(currentRequest)
			elif platform == "IEXC":
				payload, updatedQuoteMessage = IEXC.request_depth(currentRequest)

			if bool(payload):
				if clientId in [b"discord_alpha"] and currentRequest["ticker"].get("base") is not None:
					database.document("dataserver/statistics/{}/{}".format(currentRequest.get("parserBias"), int(time() // 3600 * 3600))).set({
						currentRequest["ticker"].get("base"): ArrayUnion([str(request.get("authorId"))]),
					}, merge=True)
				return [dumps(payload), updatedQuoteMessage.encode()]
			elif updatedQuoteMessage != "":
				quoteMessage = updatedQuoteMessage

		return [dumps({}), quoteMessage.encode()]


if __name__ == "__main__":
	environ["PRODUCTION_MODE"] = environ["PRODUCTION_MODE"] if "PRODUCTION_MODE" in environ and environ["PRODUCTION_MODE"] else ""
	print("[Startup]: Quote Server is in startup, running in {} mode.".format("production" if environ["PRODUCTION_MODE"] else "development"))
	quoteServer = QuoteProcessor()
	quoteServer.run()