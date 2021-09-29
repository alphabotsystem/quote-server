from time import time

from pycoingecko import CoinGeckoAPI

from TickerParserPy import TickerParserSync as TickerParser
from components.abstract import AbstractProvider
from assets import static_storage


class CoinGecko(AbstractProvider):
	name = "CoinGecko"
	connection = CoinGeckoAPI()

	@classmethod
	def _request_quote(cls, request, ticker):
		try:
			rawData = CoinGecko.connection.get_coin_by_id(id=ticker.get("symbol"), localization="false", tickers=False, market_data=True, community_data=False, developer_data=False)
		except:
			return [{}, ""]

		coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

		if ticker.get("quote").lower() not in rawData["market_data"]["current_price"] or ticker.get("quote").lower() not in rawData["market_data"]["total_volume"]: return [{}, "Requested price for `{}` is not available.".format(ticker.get("name"))]

		price = rawData["market_data"]["current_price"][ticker.get("quote").lower()]
		if ticker.get("isReversed"): price = 1 / price
		volume = rawData["market_data"]["total_volume"][ticker.get("quote").lower()]
		priceChange = rawData["market_data"]["price_change_percentage_24h_in_currency"][ticker.get("quote").lower()] if ticker.get("quote").lower() in rawData["market_data"]["price_change_percentage_24h_in_currency"] else 0
		if ticker.get("isReversed"): priceChange = (1 / (priceChange / 100 + 1) - 1) * 100

		payload = {
			"quotePrice": "{:,.12f}".format(price).rstrip('0').rstrip('.') + " " + ticker.get("quote"),
			"quoteVolume": "{:,.4f}".format(volume).rstrip('0').rstrip('.') + " " + ticker.get("base"),
			"title": ticker.get("name"),
			"change": "{:+.2f} %".format(priceChange),
			"thumbnailUrl": coinThumbnail,
			"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
			"sourceText": "Data from CoinGecko",
			"platform": "CoinGecko",
			"raw": {
				"quotePrice": [price],
				"quoteVolume": [volume],
				"timestamp": time()
			}
		}
		if ticker.get("quote") != "USD":
			payload["quoteConvertedPrice"] = "≈ ${:,.6f}".format(rawData["market_data"]["current_price"]["usd"])
			payload["quoteConvertedVolume"] = "≈ ${:,.4f}".format(rawData["market_data"]["total_volume"]["usd"])

		return [payload, ""]