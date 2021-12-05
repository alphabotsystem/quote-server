from os import environ
from time import time
from io import BytesIO
from base64 import decodebytes, b64encode
from requests import get

from PIL import Image
from iexfinance.stocks import Stock

from TickerParser import Exchange
from components.abstract import AbstractProvider
from assets import static_storage


class IEXC(AbstractProvider):
	name = "IEXC"
	chartOverlay = {
		"normal": Image.open("app/assets/overlays/quotes/depth.png").convert("RGBA")
	}

	@classmethod
	def _request_quote(cls, request, ticker):
		payload, quoteMessage, updatedQuoteMessage = {}, "", ""

		for platform in ["Stocks", "Forex"]:
			if platform == "Stocks":
				payload, updatedQuoteMessage = IEXC._request_stocks(request, ticker)
			elif platform == "Forex":
				payload, updatedQuoteMessage = IEXC._request_forex(request, ticker)

			if bool(payload):
				return [payload, updatedQuoteMessage]
			elif updatedQuoteMessage != "":
				quoteMessage = updatedQuoteMessage

		return [{}, quoteMessage]

	@classmethod
	def _request_stocks(cls, request, ticker):
		exchange = Exchange.from_dict(ticker.get("exchange"))

		try:
			stock = Stock(ticker.get("symbol"), token=environ["IEXC_KEY"])
			rawData = stock.get_quote().loc[ticker.get("symbol")]
			if ticker.get("quote") is None and exchange is not None: return [{}, "Price for `{}` is not available on {}.".format(ticker.get("name"), exchange.get("name"))]
			if rawData is None or (rawData["latestPrice"] is None and rawData["delayedPrice"] is None): return [{}, ""]
		except:
			return [{}, ""]

		try: coinThumbnail = stock.get_logo().loc[ticker.get("symbol")]["url"]
		except: coinThumbnail = static_storage.icon

		latestPrice = rawData["delayedPrice"] if rawData["latestPrice"] is None else rawData["latestPrice"]
		price = float(latestPrice if "isUSMarketOpen" not in rawData or rawData["isUSMarketOpen"] or "extendedPrice" not in rawData or rawData["extendedPrice"] is None else rawData["extendedPrice"])
		if ticker.get("isReversed"): price = 1 / price
		priceChange = ((1 / float(rawData["change"]) if ticker.get("isReversed") and float(rawData["change"]) != 0 else float(rawData["change"])) / price * 100) if "change" in rawData and rawData["change"] is not None else 0

		payload = {
			"quotePrice": "{:,.10f}".format(price).rstrip('0').rstrip('.') + ("" if ticker.get("isReversed") else (" USD" if ticker.get("quote") is None else (" " + ticker.get("quote")))),
			"title": ticker.get("name"),
			"change": "{:+.2f} %".format(priceChange),
			"thumbnailUrl": coinThumbnail,
			"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
			"sourceText": "Data provided by IEX Cloud",
			"platform": "IEXC",
			"raw": {
				"quotePrice": [price],
				"timestamp": time()
			}
		}

		if "latestVolume" in rawData:
			volume = float(rawData["latestVolume"])
			payload["quoteVolume"] = "{:,.4f}".format(volume).rstrip('0').rstrip('.') + " " + ticker.get("base")
			payload["raw"]["quoteVolume"] = [volume]

		return [payload, ""]

	@classmethod
	def _request_forex(cls, request, ticker):
		exchange = Exchange.from_dict(ticker.get("exchange"))

		try:
			if exchange is not None: return [{}, ""]
			rawData = get("https://cloud.iexapis.com/stable/fx/latest?symbols={}&token={}".format(ticker.get("id"), environ["IEXC_KEY"])).json()
			if rawData is None or type(rawData) is not list or len(rawData) == 0: return [{}, ""]
		except:
			return [{}, ""]

		price = rawData[0]["rate"]
		if price is None: return [{}, ""]
		if ticker.get("isReversed"): price = 1 / price

		payload = {
			"quotePrice": "{:,.5f} {}".format(price, ticker.get("quote")),
			"title": ticker.get("name"),
			"thumbnailUrl": static_storage.icon,
			"messageColor": "deep purple",
			"sourceText": "Data provided by IEX Cloud",
			"platform": "IEXC",
			"raw": {
				"quotePrice": [price],
				"timestamp": time()
			}
		}
		return [payload, ""]

	@classmethod
	def _request_depth(cls, request, ticker):
		exchange = Exchange.from_dict(ticker.get("exchange"))

		preferences = request.get("preferences")
		forceMode = {"id": "force", "value": "force"} in preferences
		uploadMode = {"id": "upload", "value": "upload"} in preferences

		try:
			stock = Stock(ticker.get("symbol"), token=environ["IEXC_KEY"])
			depthData = stock.get_book()[ticker.get("symbol")]
			rawData = stock.get_quote().loc[ticker.get("symbol")]
			if ticker.get("quote") is None and exchange is not None: return [{}, "Orderbook visualization for `{}` is not available on {}.".format(ticker.get("name"), exchange.get("name"))]
			lastPrice = (depthData["bids"][0]["price"] + depthData["asks"][0]["price"]) / 2
			depthData = {
				"bids": [[e.get("price"), e.get("size")] for e in depthData["bids"] if e.get("price") >= lastPrice * 0.75],
				"asks": [[e.get("price"), e.get("size")] for e in depthData["asks"] if e.get("price") <= lastPrice * 1.25]
			}
			bestBid = depthData["bids"][0]
			bestAsk = depthData["asks"][0]
		except:
			return [{}, ""]

		imageBuffer = BytesIO()
		chartImage = Image.new("RGBA", (1600, 1200))
		chartImage.paste(IEXC._generate_depth_image(depthData, bestBid, bestAsk, lastPrice))
		chartImage = Image.alpha_composite(chartImage, IEXC.chartOverlay["normal"])
		chartImage.save(imageBuffer, format="png")
		imageData = b64encode(imageBuffer.getvalue())
		imageBuffer.close()
		# if uploadMode:
		# 	bucket.blob("uploads/{}.png".format(int(time() * 1000))).upload_from_string(decodebytes(imageData))

		payload = {
			"data": imageData.decode(),
			"platform": "IEXC"
		}

		return [payload, ""]