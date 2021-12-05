from time import time
from zmq import Context, Poller, ROUTER, REQ, LINGER, POLLIN
from orjson import dumps, loads

from TickerParser import TickerParserSync as TickerParser
from components.abstract import AbstractProvider
from assets import static_storage


class Serum(AbstractProvider):
	name = "Serum"

	@classmethod
	def _request_quote(cls, request, ticker, context=None):
		try:
			socket = context.socket(REQ)
			socket.connect("tcp://serum-server:6900")
			socket.setsockopt(LINGER, 0)
			poller = Poller()
			poller.register(socket, POLLIN)

			socket.send(bytes(dumps({"endpoint": "quote", "marketAddress": ticker.get("id"), "program": ticker.get("symbol")}), encoding='utf8'))
			responses = poller.poll(5000)

			if len(responses) != 0:
				response = socket.recv()
				socket.close()
				rawData = loads(response)
			else:
				socket.close()
				return [{}, ""]
		except:
			return [{}, ""]

		coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

		price = [float(rawData["price"])]
		priceChange = 0
		volume = 0
		tokenImage = static_storage.icon

		base = "USD" if ticker.get("base") in AbstractProvider.stableCoinTickers else ticker.get("base")
		quote = "USD" if ticker.get("quote") in AbstractProvider.stableCoinTickers else ticker.get("quote")
		payload = {
			"quotePrice": "{:,.10f}".format(price[0]).rstrip('0').rstrip('.') + " " + quote,
			"quoteVolume": "{:,.4f}".format(volume).rstrip('0').rstrip('.') + " " + base,
			"title": ticker.get("name"),
			"thumbnailUrl": coinThumbnail,
			"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
			"sourceText": "Data from Serum DEX",
			"platform": "Serum",
			"raw": {
				"quotePrice": [price[0]],
				"quoteVolume": [volume],
				"timestamp": time()
			}
		}

		return [payload, ""]