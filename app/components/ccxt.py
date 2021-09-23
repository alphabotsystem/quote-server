from time import time
from io import BytesIO
from math import ceil
from datetime import datetime
from pytz import utc
from base64 import decodebytes, b64encode

from PIL import Image

from TickerParserPy import Exchange, TickerParserSync as TickerParser
from components.abstract import AbstractProvider
from components.coingecko import CoinGecko
from assets import static_storage


class CCXT(AbstractProvider):
	name = "CCXT"
	chartOverlay = {
		"normal": Image.open("app/assets/overlays/quotes/depth.png").convert("RGBA")
	}

	@classmethod
	def _request_quote(cls, request, ticker):
		exchange = Exchange.from_dict(ticker.get("exchange"))

		if exchange is None: return [{}, ""]

		tf, limitTimestamp, candleOffset = CCXT.get_highest_supported_timeframe(exchange.properties, datetime.now().astimezone(utc))
		try:
			rawData = exchange.properties.fetch_ohlcv(ticker.get("symbol"), timeframe=tf.lower(), since=limitTimestamp, limit=300)
			if len(rawData) == 0 or rawData[-1][4] is None or rawData[0][1] is None: return [{}, ""]
		except:
			return [{}, ""]

		price = [rawData[-1][4], rawData[0][1]] if len(rawData) < candleOffset else [rawData[-1][4], rawData[-candleOffset][1]]
		if ticker.get("isReversed"): price = [1 / price[0], 1 / price[1]]
		volume = None if price[0] is None else sum([candle[5] for candle in rawData if int(candle[0] / 1000) >= int(exchange.properties.milliseconds() / 1000) - 86400]) / (price[0] if exchange.id == "bitmex" else 1)
		priceChange = 0 if tf == "1m" or price[1] == 0 else (price[0] / price[1]) * 100 - 100
		coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

		base = "USD" if ticker.get("base") in AbstractProvider.stableCoinTickers else ticker.get("base")
		quote = "USD" if ticker.get("quote") in AbstractProvider.stableCoinTickers else ticker.get("quote")
		payload = {
			"quotePrice": "{:,.10f}".format(price[0]).rstrip('0').rstrip('.') + " " + quote,
			"quoteVolume": "{:,.4f}".format(volume).rstrip('0').rstrip('.') + " " + base,
			"title": ticker.get("name"),
			"change": "{:+.2f} %".format(priceChange),
			"thumbnailUrl": coinThumbnail,
			"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
			"sourceText": "Data from {}".format(exchange.name),
			"platform": CCXT.name,
			"raw": {
				"quotePrice": [price[0]] if tf == "1m" else price[:1],
				"quoteVolume": [volume],
				"timestamp": time()
			}
		}
		if ticker.get("quote") == "BTC":
			payload["quoteConvertedPrice"] = "≈ ${:,.6f}".format(price[0] * CoinGecko.lastBitcoinQuote)
			payload["quoteConvertedVolume"] = "≈ ${:,.4f}".format(volume * CoinGecko.lastBitcoinQuote)

		return [payload, ""]

	@classmethod
	def _request_depth(cls, request, ticker):
		exchange = Exchange.from_dict(ticker.get("exchange"))

		preferences = request.get("preferences")
		forceMode = {"id": "force", "value": "force"} in preferences
		uploadMode = {"id": "upload", "value": "upload"} in preferences

		if exchange is None: return [{}, ""]

		try:
			depthData = exchange.properties.fetch_order_book(ticker.get("symbol"))
			bestBid = depthData["bids"][0]
			bestAsk = depthData["asks"][0]
			lastPrice = (bestBid[0] + bestAsk[0]) / 2
		except:
			return [{}, ""]

		imageBuffer = BytesIO()
		chartImage = Image.new("RGBA", (1600, 1200))
		chartImage.paste(CCXT._generate_depth_image(depthData, bestBid, bestAsk, lastPrice))
		chartImage = Image.alpha_composite(chartImage, CCXT.chartOverlay["normal"])
		chartImage.save(imageBuffer, format="png")
		imageData = b64encode(imageBuffer.getvalue())
		imageBuffer.close()
		# if uploadMode:
		# 	bucket.blob("uploads/{}.png".format(int(time() * 1000))).upload_from_string(decodebytes(imageData))

		payload = {
			"data": imageData.decode(),
			"platform": "CCXT"
		}

		return [payload, ""]

	@classmethod
	def request_lld(cls, request):
		ticker = request.get("ticker")
		exchange = Exchange.from_dict(ticker.get("exchange"))
		preferences = request.get("preferences")
		action = [e.get("value") for e in preferences if e.get("id") == "lld"]
		if len(action) == 0: return [{}, ""]
		action = action[0]

		if action == "funding":
			if exchange.id in ["bitmex"]:
				try: rawData = exchange.properties.public_get_instrument({"symbol": ticker.get("id")})[0]
				except: return [{}, "Requested funding data for `{}` is not available.".format(ticker.get("name"))]

				if rawData["fundingTimestamp"] is not None:
					fundingDate = datetime.strptime(rawData["fundingTimestamp"], "%Y-%m-%dT%H:%M:00.000Z").replace(tzinfo=utc)
				else:
					fundingDate = datetime.now().replace(tzinfo=utc)
				indicativeFundingTimestamp = datetime.timestamp(fundingDate) + 28800
				indicativeFundingDate = datetime.utcfromtimestamp(indicativeFundingTimestamp).replace(tzinfo=utc)
				deltaFunding = fundingDate - datetime.now().astimezone(utc)
				deltaIndicative = indicativeFundingDate - datetime.now().astimezone(utc)

				hours1, seconds1 = divmod(deltaFunding.days * 86400 + deltaFunding.seconds, 3600)
				minutes1 = int(seconds1 / 60)
				hoursFunding = "{:d} {} ".format(hours1, "hours" if hours1 > 1 else "hour") if hours1 > 0 else ""
				minutesFunding = "{:d} {}".format(minutes1 if hours1 > 0 or minutes1 > 0 else seconds1, "{}".format("minute" if minutes1 == 1 else "minutes") if hours1 > 0 or minutes1 > 0 else ("second" if seconds1 == 1 else "seconds"))
				deltaFundingText = "{}{}".format(hoursFunding, minutesFunding)

				hours2, seconds2 = divmod(deltaIndicative.days * 86400 + deltaIndicative.seconds, 3600)
				minutes2 = int(seconds2 / 60)
				hoursIndicative = "{:d} {} ".format(hours2, "hours" if hours2 > 1 else "hour") if hours2 > 0 else ""
				minutesIndicative = "{:d} {}".format(minutes2 if hours2 > 0 or minutes2 > 0 else seconds2, "{}".format("minute" if minutes2 == 1 else "minutes") if hours2 > 0 or minutes2 > 0 else ("second" if seconds2 == 1 else "seconds"))
				deltaIndicativeText = "{}{}".format(hoursIndicative, minutesIndicative)

				fundingRate = float(rawData["fundingRate"]) * 100
				predictedFundingRate = float(rawData["indicativeFundingRate"]) * 100
				averageFundingRate = (fundingRate + predictedFundingRate) / 2

				coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

				payload = {
					"quotePrice": "Funding Rate: {:+.4f} %".format(fundingRate),
					"quoteConvertedPrice": "Predicted Rate: {:+.4f} % *(in {})*".format(predictedFundingRate, deltaIndicativeText),
					"title": ticker.get("name"),
					"change": "in {}".format(deltaFundingText),
					"thumbnailUrl": coinThumbnail,
					"messageColor": "yellow" if averageFundingRate == 0.01 else ("light green" if averageFundingRate < 0.01 else "deep orange"),
					"sourceText": "Funding on {}".format(exchange.name),
					"platform": CCXT.name,
					"raw": {
						"quotePrice": [fundingRate, predictedFundingRate],
						"timestamp": time()
					}
				}
				return [payload, ""]
			return [{}, "Funding data is only available on BitMEX."]
		elif action == "oi":
			if exchange.id in ["bitmex"]:
				try: rawData = exchange.properties.public_get_instrument({"symbol": ticker.get("id")})[0]
				except: return [{}, "Requested open interest data for `{}` is not available.".format(ticker.get("name"))]

				coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

				payload = {
					"quotePrice": "Open interest: {:,.0f} contracts".format(float(rawData["openInterest"])),
					"quoteConvertedPrice": "Open value: {:,.4f} XBT".format(float(rawData["openValue"]) / 100000000),
					"title": ticker.get("name"),
					"thumbnailUrl": coinThumbnail,
					"messageColor": "deep purple",
					"sourceText": "Open interest on {}".format(exchange.name),
					"platform": CCXT.name,
					"raw": {
						"quotePrice": [float(rawData["openInterest"]), float(rawData["openValue"]) / 100000000],
						"timestamp": time()
					}
				}
				return [payload, ""]
			return [{}, "Open interest and open value data is only available on BitMEX."]
		elif action == "ls":
			if exchange.id in ["bitfinex2"]:
				try:
					longs = exchange.properties.publicGetStats1KeySizeSymbolLongLast({"key": "pos.size", "size": "1m", "symbol": "t{}".format(ticker.get("id")), "side": "long", "section": "last"})
					shorts = exchange.properties.publicGetStats1KeySizeSymbolShortLast({"key": "pos.size", "size": "1m", "symbol": "t{}".format(ticker.get("id")), "side": "long", "section": "last"})
					ratio = longs[1] / (longs[1] + shorts[1]) * 100
				except:
					return [{}, ""]

				coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

				payload = {
					"quotePrice": "{:.1f} % longs / {:.1f} % shorts".format(ratio, 100 - ratio),
					"title": ticker.get("name"),
					"change": "in {}".format(deltaFundingText),
					"thumbnailUrl": coinThumbnail,
					"messageColor": "deep purple",
					"sourceText": "Longs/shorts on {}".format(exchange.name),
					"platform": CCXT.name,
					"raw": {
						"quotePrice": [longs[1], shorts[1]],
						"timestamp": time()
					}
				}
				return [payload, ""]
			return [{}, "Longs and shorts data is only available on Bitfinex."]
		elif action == "dom":
			try: rawData = CoinGecko.connection.get_global()
			except: return [{}, "Requested dominance data for `{}` is not available.".format(ticker.get("name"))]
			if ticker.get("base").lower() not in rawData["market_cap_percentage"]: return [{}, "Dominance for {} does not exist.".format(ticker.get("base"))]
			coinDominance = rawData["market_cap_percentage"][ticker.get("base").lower()]

			coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

			payload = {
				"quotePrice": "{} dominance: {:,.2f} %".format(ticker.get("base"), coinDominance),
				"title": "Market Dominance",
				"thumbnailUrl": coinThumbnail,
				"messageColor": "deep purple",
				"sourceText": "Market information from CoinGecko",
				"platform": CCXT.name,
				"raw": {
					"quotePrice": [coinDominance],
					"timestamp": time()
				}
			}
			return [payload, ""]
		else:
			return [{}, ""]

	@staticmethod
	def get_highest_supported_timeframe(exchange, n):
		if exchange.timeframes is None: return ("1m", int(exchange.milliseconds() / 1000) - 60, 2)
		dailyOpen = (int(exchange.milliseconds() / 1000) - (n.second + n.minute * 60 + n.hour * 3600)) * 1000
		rolling24h = (int(exchange.milliseconds() / 1000) - 86400) * 1000
		availableTimeframes = ["5m", "10m", "15m", "20m", "30m", "1H", "2H", "3H", "4H", "6H", "8H", "12H", "1D"]
		for tf in availableTimeframes:
			if tf.lower() in exchange.timeframes:
				return tf, min(rolling24h, dailyOpen), ceil(int((exchange.milliseconds() - dailyOpen) / 1000) / CCXT.get_frequency_time(tf))
		return ("1m", int(exchange.milliseconds() / 1000) - 60, 2)

	@staticmethod
	def get_frequency_time(t):
		if t == "1D": return 86400
		elif t == "12H": return 43200
		elif t == "8H": return 28800
		elif t == "6H": return 21600
		elif t == "4H": return 14400
		elif t == "3H": return 10800
		elif t == "2H": return 7200
		elif t == "1H": return 3600
		elif t == "30m": return 1800
		elif t == "20m": return 1200
		elif t == "15m": return 900
		elif t == "10m": return 600
		elif t == "5m": return 300
		elif t == "3m": return 180
		elif t == "2m": return 120
		elif t == "1m": return 60