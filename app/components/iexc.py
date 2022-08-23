from os import environ
from time import time
from io import BytesIO
from base64 import decodebytes, b64encode
from requests import get
from traceback import format_exc

from PIL import Image
from iexfinance.stocks import Stock

from TickerParser import Exchange
from components.abstract import AbstractProvider
from assets import static_storage


class IEXC(AbstractProvider):
	name = "IEXC"
	chartOverlay = {
		"normal": Image.open("assets/overlays/quotes/depth.png").convert("RGBA")
	}

	@classmethod
	def _request_quote(cls, request, ticker):
		if ticker.get("exchange").get("id") == "fx":
			return IEXC._request_forex(request, ticker)
		else:
			return IEXC._request_stocks(request, ticker)

	@classmethod
	def _request_stocks(cls, request, ticker):
		exchange = Exchange.from_dict(ticker.get("exchange"))

		try:
			stock = Stock(ticker.get("symbol"), token=environ["IEXC_KEY"])
			rawData = stock.get_quote().loc[ticker.get("symbol")]
			if ticker.get("quote") is None and exchange is not None: return None, f"Price for `{ticker.get('name')}` is not available on {exchange.name}."
			if rawData is None or (rawData["latestPrice"] is None and rawData["delayedPrice"] is None): return None, None
		except:
			print(format_exc())
			return None, None

		try: coinThumbnail = stock.get_logo().loc[ticker.get("symbol")]["url"]
		except: coinThumbnail = static_storage.icon

		latestPrice = rawData["delayedPrice"] if rawData["latestPrice"] is None else rawData["latestPrice"]
		price = float(latestPrice if "isUSMarketOpen" not in rawData or rawData["isUSMarketOpen"] or "extendedPrice" not in rawData or rawData["extendedPrice"] is None else rawData["extendedPrice"])
		priceChange = (float(rawData["change"]) / price * 100) if "change" in rawData and rawData["change"] is not None else 0

		payload = {
			"quotePrice": "{:,.10f}".format(price).rstrip('0').rstrip('.') + (" USD" if ticker.get("quote") is None else (" " + ticker.get("quote"))),
			"title": ticker.get("name"),
			"change": "{:+.2f} %".format(priceChange),
			"thumbnailUrl": coinThumbnail,
			"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
			"sourceText": f"Price on {exchange.name}",
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

		return payload, None

	@classmethod
	def _request_forex(cls, request, ticker):
		try:
			rawData = get(f"https://cloud.iexapis.com/stable/fx/latest?symbols={ticker.get('id')}&token={environ['IEXC_KEY']}").json()
			if rawData is None or type(rawData) is not list or len(rawData) == 0: return None, None
		except:
			print(format_exc())
			return None, None

		price = rawData[0]["rate"]
		if price is None: return None, None

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
		return payload, None

	@classmethod
	def _request_depth(cls, request, ticker):
		if ticker.get("exchange").get("id") == "fx":
			return None, "Orderbook visualizations are not available for forex markets."

		exchange = Exchange.from_dict(ticker.get("exchange"))

		preferences = request.get("preferences")
		forceMode = {"id": "force", "value": "force"} in preferences

		try:
			stock = Stock(ticker.get("symbol"), token=environ["IEXC_KEY"])
			depthData = stock.get_book()[ticker.get("symbol")]
			rawData = stock.get_quote().loc[ticker.get("symbol")]
			if ticker.get("quote") is None and exchange is not None: return None, f"Orderbook visualization for `{ticker.get('name')}` is not available on {exchange.get('name')}."
			if not depthData["quote"].get("isUSMarketOpen", True): return None, "US market is currently not open."
			lastPrice = (depthData["bids"][0]["price"] + depthData["asks"][0]["price"]) / 2
			depthData = {
				"bids": [[e.get("price"), e.get("size")] for e in depthData["bids"] if e.get("price") >= lastPrice * 0.75],
				"asks": [[e.get("price"), e.get("size")] for e in depthData["asks"] if e.get("price") <= lastPrice * 1.25]
			}
			bestBid = depthData["bids"][0]
			bestAsk = depthData["asks"][0]
		except:
			print(format_exc())
			return None, None

		imageBuffer = BytesIO()
		chartImage = Image.new("RGBA", (1600, 1200))
		chartImage.paste(IEXC._generate_depth_image(depthData, bestBid, bestAsk, lastPrice))
		chartImage = Image.alpha_composite(chartImage, IEXC.chartOverlay["normal"])
		chartImage.save(imageBuffer, format="png")
		imageData = b64encode(imageBuffer.getvalue())
		imageBuffer.close()
		# AbstractProvider.bucket.blob(f"uploads/{int(time() * 1000)}.png").upload_from_string(decodebytes(imageData))

		payload = {
			"data": imageData.decode(),
			"platform": "IEXC"
		}

		return payload, None

	@classmethod
	def request_details(cls, request):
		ticker = request.get("ticker")

		try:
			stock = Stock(ticker.get("id"), token=environ["IEXC_KEY"])
			companyData = stock.get_company().loc[ticker.get("id")]
			rawData = stock.get_quote().loc[ticker.get("id")]
			historicData = stock.get_historical_prices(range="1y")
		except:
			print(format_exc())
			return None, None

		try: stockLogoThumbnail = stock.get_logo().loc[ticker.get("id")]["url"]
		except: stockLogoThumbnail = None

		payload = {
			"name": companyData["symbol"] if companyData["companyName"] is None else f"{companyData['companyName']} ({companyData['symbol']})",
			"info": {
				"employees": companyData["employees"]
			},
			"price": {
				"current": rawData["delayedPrice"] if rawData["latestPrice"] is None else rawData["latestPrice"],
				"1y high": historicData.high.max(),
				"1y low": historicData.low.min(),
				"per": rawData["peRatio"]
			},
			"change": {
				"past day": ((historicData.close[-1] / historicData.close[-2] - 1) * 100 if historicData.shape[0] >= 2 and historicData.close[-2] != 0 else None) if rawData["changePercent"] is None else rawData["changePercent"] * 100,
				"past month": (historicData.close[-1] / historicData.close[-21] - 1) * 100 if historicData.shape[0] >= 21 and historicData.close[-21] != 0 else None,
				"past year": (historicData.close[-1] / historicData.close[0] - 1) * 100 if historicData.shape[0] >= 200 and historicData.close[0] != 0 else None
			},
			"sourceText": "Data provided by IEX Cloud",
			"platform": "IEXC",
		}

		if stockLogoThumbnail is not None: payload["image"] = stockLogoThumbnail
		if companyData["description"] is not None: payload["description"] = companyData["description"]
		if companyData["industry"] is not None and companyData["industry"] != "": payload["industry"] = companyData["industry"]
		if "marketCap" in rawData: payload["marketcap"] = rawData["marketCap"]
		if companyData["website"] is not None and companyData["website"] != "": payload["url"] = companyData["website"] if companyData["website"].startswith("http") else "https://" + companyData["website"]
		if companyData["country"] is not None: payload["info"]["location"] = f"{companyData['address']}{'' if companyData['address2'] is None else ', ' + companyData['address2']}, {companyData['city']}, {companyData['state']}, {companyData['country']}"

		return payload, None