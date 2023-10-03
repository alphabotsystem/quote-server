from os import environ
from time import time
from io import BytesIO
from math import ceil
from datetime import datetime, timezone
from base64 import decodebytes, b64encode
from traceback import format_exc

from PIL import Image
from elasticsearch import Elasticsearch

from components.abstract import AbstractProvider
import ccxt
from ccxt.base.errors import NotSupported, BadSymbol
from components.coingecko import CoinGecko
from assets import static_storage


elasticsearch = Elasticsearch(
	cloud_id=environ["ELASTICSEARCH_CLOUD_ID"],
	api_key=environ["ELASTICSEARCH_API_KEY"],
)


CCXT_TO_CACHE_MAP = {
	"binance": "binance:s:",
	"binanceusdm": "binance:f:",
	"binancecoinm": "binance:i:",
}


class CCXT(AbstractProvider):
	name = "CCXT"

	@classmethod
	def _request_quote(cls, request, ticker):
		preferences = request.get("preferences")
		action = next((e.get("value") for e in preferences if e.get("id") == "lld"), None)

		exchange = ticker["exchange"]
		if not exchange:
			return None, None
		esDocId = CCXT_TO_CACHE_MAP.get(exchange["id"])

		if exchange["id"] == "binance":
			ccxtInstance = ccxt.binance({
				"proxies": {
					"http": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}",
					"https": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}"
				}
			})
		elif exchange["id"] == "binanceusdm":
			ccxtInstance = ccxt.binanceusdm({
				"proxies": {
					"http": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}",
					"https": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}"
				}
			})
		elif exchange["id"] == "binancecoinm":
			ccxtInstance = ccxt.binancecoinm({
				"proxies": {
					"http": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}",
					"https": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}"
				}
			})
		else:
			ccxtInstance = getattr(ccxt, exchange["id"])()

		tf, limitTimestamp, candleOffset = CCXT.get_highest_supported_timeframe(ccxtInstance, datetime.now().astimezone(timezone.utc))

		if action == "funding":
			try:
				rawData = ccxtInstance.fetchFundingRate(ticker.get("symbol"))
			except NotSupported:
				return None, f"Funding is not supported by {exchange['name']}. The requested ticker is likely a spot market."
			except:
				print(format_exc())
				return None, None

			fundingRate = rawData["fundingRate"]
			predictedFundingRate = rawData.get("nextFundingRate")
			if rawData["fundingTimestamp"] is not None:
				fundingDate = datetime.fromtimestamp(rawData["fundingTimestamp"] / 1000).astimezone(timezone.utc)
			elif rawData["fundingDatetime"] is not None:
				fundingDate = datetime.strptime(rawData["fundingDatetime"], "%Y-%m-%dT%H:%M:00.000Z").replace(tzinfo=timezone.utc)
			else:
				fundingDate = None
			averageFundingRate = fundingRate if predictedFundingRate is None else (fundingRate + predictedFundingRate) / 2
			coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

			payload = {
				"quotePrice": "Funding Rate: {:+.4f} %".format(fundingRate * 100),
				"quoteConvertedPrice": None if predictedFundingRate is None else "Predicted Rate: {:+.4f} %".format(predictedFundingRate * 100),
				"title": ticker.get("name"),
				"change": None if fundingDate is None else f"<t:{int(datetime.timestamp(fundingDate))}:R>",
				"thumbnailUrl": coinThumbnail,
				"messageColor": "yellow" if averageFundingRate == 0.01 else ("light green" if averageFundingRate < 0.01 else "deep orange"),
				"sourceText": f"Funding on {exchange['name']}",
				"platform": CCXT.name,
				"raw": {
					"quotePrice": [fundingRate, predictedFundingRate],
					"timestamp": time()
				}
			}
			return payload, None

		elif action == "oi":
			try:
				rawData = ccxtInstance.fetchOpenInterestHistory(ticker.get("symbol"), limit=1)
			except (NotSupported, BadSymbol):
				return None, f"Funding is not supported by {exchange['name']}. The requested ticker is likely a spot market."
			except:
				print(format_exc())
				return None, None

			openInterest = rawData[0]["openInterestAmount"]
			openValue = rawData[0]["openInterestValue"]
			coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

			payload = {
				"quotePrice": "Open interest: {:,.0f} contracts".format(openInterest),
				"quoteConvertedPrice": "Open value: {:,.4f}".format(openValue),
				"title": ticker.get("name"),
				"thumbnailUrl": coinThumbnail,
				"messageColor": "deep purple",
				"sourceText": f"Open interest on {exchange['name']}",
				"platform": CCXT.name,
				"raw": {
					"quotePrice": [openInterest, openValue],
					"timestamp": time()
				}
			}
			return payload, None

		elif action == "ls":
			if exchange["id"] == "bitfinex2":
				try:
					longs = ccxtInstance.publicGetStats1KeySizeSymbolLongLast({"key": "pos.size", "size": "1m", "symbol": f"t{ticker.get('id')}", "side": "long", "section": "last"})
					shorts = ccxtInstance.publicGetStats1KeySizeSymbolShortLast({"key": "pos.size", "size": "1m", "symbol": f"t{ticker.get('id')}", "side": "long", "section": "last"})
					ratio = longs[1] / (longs[1] + shorts[1]) * 100
				except:
					return None, None

				coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

				payload = {
					"quotePrice": "{:.1f} % longs / {:.1f} % shorts".format(ratio, 100 - ratio),
					"title": ticker.get("name"),
					"change": f"in {deltaFundingText}",
					"thumbnailUrl": coinThumbnail,
					"messageColor": "deep purple",
					"sourceText": f"Longs/shorts on {exchange['name']}",
					"platform": CCXT.name,
					"raw": {
						"quotePrice": [longs[1], shorts[1]],
						"timestamp": time()
					}
				}
				return payload, None
			return None, "Longs and shorts data is only available on Bitfinex."

		elif esDocId is not None:
			# Get document by id
			response = elasticsearch.search(index="cache", body={"query": {"match": {"_id": esDocId + ticker.get("id")}}})
			if len(response["hits"]["hits"]) == 0:
				return None, None

			data = response["hits"]["hits"][0]["_source"]

			priceChange = (data["close"] / data["open"]) * 100 - 100
			coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

			payload = {
				"quotePrice": "{:,.10f}".format(data["close"]).rstrip('0').rstrip('.') + " " + ticker.get("quote"),
				"quoteVolume": "{:,.4f}".format(data["volume"]).rstrip('0').rstrip('.') + " " + ticker.get("base"),
				"title": ticker.get("name"),
				"change": "{:+.2f} %".format(priceChange),
				"thumbnailUrl": coinThumbnail,
				"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
				"sourceText": f"{ticker['id']} data from {exchange['name']}",
				"platform": CCXT.name,
				"raw": {
					"quotePrice": [data["open"], data["close"]],
					"quoteVolume": [data["volume"]],
					"timestamp": time()
				}
			}

			return payload, None

		else:
			try:
				rawData = ccxtInstance.fetch_ohlcv(ticker.get("symbol"), timeframe=tf, since=limitTimestamp, limit=150)
				if len(rawData) == 0 or rawData[-1][4] is None or rawData[0][1] is None: return None, None
			except:
				print(format_exc())
				return None, f"Data from {exchange['name']} is currently unavailable."

			price = [rawData[-1][4], rawData[0][1]] if len(rawData) < candleOffset else [rawData[-1][4], rawData[-candleOffset][1]]
			volume = None if price[0] is None else sum([candle[5] for candle in rawData if int(candle[0] / 1000) >= int(ccxtInstance.milliseconds() / 1000) - 86400]) / (price[0] if exchange["id"] == "bitmex" else 1)
			priceChange = 0 if tf == "1m" or price[1] == 0 else (price[0] / price[1]) * 100 - 100
			coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

			payload = {
				"quotePrice": "{:,.10f}".format(price[0]).rstrip('0').rstrip('.') + " " + ticker.get("quote"),
				"quoteVolume": "{:,.4f}".format(volume).rstrip('0').rstrip('.') + " " + ticker.get("base"),
				"title": ticker.get("name"),
				"change": "{:+.2f} %".format(priceChange),
				"thumbnailUrl": coinThumbnail,
				"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
				"sourceText": f"{ticker['id']} data from {exchange['name']}",
				"platform": CCXT.name,
				"raw": {
					"quotePrice": [price[0]] if tf == "1m" else price[:1],
					"quoteVolume": [volume],
					"timestamp": time()
				}
			}

			return payload, None

	@classmethod
	def _request_depth(cls, request, ticker):
		preferences = request.get("preferences")
		action = next((e.get("value") for e in preferences if e.get("id") == "lld"), None)
		if action is not None: return None, "Support for lower level data like funding rates and open interest is not supported by the depth command."

		exchange = ticker["exchange"]
		if exchange is None:
			return None, None

		if exchange["id"] == "binance":
			ccxtInstance = ccxt.binance({
				"proxies": {
					"http": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}",
					"https": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}"
				}
			})
		elif exchange["id"] == "binanceusdm":
			ccxtInstance = ccxt.binanceusdm({
				"proxies": {
					"http": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}",
					"https": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}"
				}
			})
		elif exchange["id"] == "binancecoinm":
			ccxtInstance = ccxt.binancecoinm({
				"proxies": {
					"http": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}",
					"https": f"http://{environ['PROXY_AUTH']}@{environ['PROXY_IP']}"
				}
			})
		else:
			ccxtInstance = getattr(ccxt, exchange["id"])()

		try:
			depthData = ccxtInstance.fetch_order_book(ticker.get("symbol"))
			bestBid = depthData["bids"][0]
			bestAsk = depthData["asks"][0]
			lastPrice = (bestBid[0] + bestAsk[0]) / 2
		except:
			return None, None

		imageData = b64encode(CCXT._generate_depth_image(depthData, bestBid, bestAsk, lastPrice))

		# imageBuffer = BytesIO()
		# chartImage = Image.new("RGBA", (1600, 1200))
		# chartImage.paste(CCXT._generate_depth_image(depthData, bestBid, bestAsk, lastPrice))
		# chartImage = Image.alpha_composite(chartImage, CCXT.chartOverlay["normal"])
		# chartImage.save(imageBuffer, format="png")
		# imageData = b64encode(imageBuffer.getvalue())
		# imageBuffer.close()

		payload = {
			"data": imageData.decode(),
			"width": 1600,
			"height": 1200,
			"platform": "CCXT"
		}

		return payload, None

	@staticmethod
	def get_highest_supported_timeframe(exchange, n):
		if exchange.timeframes is None: return ("1m", int(exchange.milliseconds() / 1000) - 60, 2)
		dailyOpen = (int(exchange.milliseconds() / 1000) - (n.second + n.minute * 60 + n.hour * 3600)) * 1000
		rolling24h = (int(exchange.milliseconds() / 1000) - 86400) * 1000
		availableTimeframes = ["10m", "15m", "20m", "30m", "1h", "2h", "3h", "4h", "6h", "8h", "12h", "1d"]
		for tf in availableTimeframes:
			if tf in exchange.timeframes:
				return tf, rolling24h, ceil(int((exchange.milliseconds() - dailyOpen) / 1000) / CCXT.get_frequency_time(tf))
		return ("1m", int(exchange.milliseconds() / 1000) - 60, 2)

	@staticmethod
	def get_frequency_time(t):
		if t == "1d": return 86400
		elif t == "12h": return 43200
		elif t == "8h": return 28800
		elif t == "6h": return 21600
		elif t == "4h": return 14400
		elif t == "3h": return 10800
		elif t == "2h": return 7200
		elif t == "1h": return 3600
		elif t == "30m": return 1800
		elif t == "20m": return 1200
		elif t == "15m": return 900
		elif t == "10m": return 600