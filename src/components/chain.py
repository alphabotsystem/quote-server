from os import environ
from time import time
from traceback import format_exc
import requests
from orjson import loads

from components.abstract import AbstractProvider
from assets import static_storage


class Chain(AbstractProvider):
	name = "On-Chain"

	@classmethod
	def _request_quote(cls, request, ticker):
		symbol = ticker.get("id")
		exchange = ticker["exchange"]

		try:
			url = f"https://pro-api.coingecko.com/api/v3/onchain/networks/{exchange.get('id', 'eth')}/pools/{symbol}"
			response = requests.get(url, headers={"accept": "application/json", "x-cg-pro-api-key": environ["COINGECKO_API_KEY"]})
			rawData = loads(response.text)["data"]["attributes"]
		except:
			print(format_exc())
			return None, None

		price = rawData["base_token_price_usd"][:10]
		rawPrice = rawData["base_token_price_native_currency"][:14]
		volume = rawData["volume_usd"]["h24"]
		priceChange = rawData["price_change_percentage"]["h24"]

		name = rawData["name"]
		if name.count(" / ") == 1:
			base, rest = name.split(" / ")
			quote = rest.split(" ")[0]
		else:
			base, quote = "", ""

		payload = {
			"quotePrice": price + " USD",
			"quoteConvertedPrice": rawPrice + " " + quote,
			"quoteVolume": volume + " USD",
			"title": base + quote,
			"change": priceChange + " %",
			"messageColor": "amber" if float(priceChange) == 0 else ("green" if float(priceChange) > 0 else "red"),
			"sourceText": f"{ticker['id']} on-chain",
			"platform": Chain.name,
			"raw": {
				"quotePrice": [float(price)],
				"quoteVolume": [float(volume)],
				"timestamp": time()
			}
		}

		return payload, None