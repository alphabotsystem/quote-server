from os import environ
from time import time
from io import BytesIO
from base64 import decodebytes, b64encode
from requests import get
from traceback import format_exc

from PIL import Image
from iexfinance.stocks import Stock

from components.abstract import AbstractProvider
from assets import static_storage


class IEXC(AbstractProvider):
	name = "IEXC"
	chartOverlay = {
		"normal": Image.open("assets/overlays/quotes/depth.png").convert("RGBA")
	}

	@classmethod
	def _request_depth(cls, request, ticker):
		exchange = ticker["exchange"]
		if exchange.get("id") == "forex":
			return None, "Orderbook visualizations are not available for forex markets."
		if not exchange:
			return None, None

		try:
			if ticker.get("quote") is None and exchange is not None: return None, f"Orderbook visualization for `{ticker['name']}` is not available on {exchange['name']}."
			stock = Stock(ticker.get("symbol"), token=environ["IEXC_KEY"])
			depthData = stock.get_book()[ticker.get("symbol")]
			if not depthData["quote"].get("isUSMarketOpen", True): return None, "US stock market is currently not open."
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

		payload = {
			"data": imageData.decode(),
			"width": 1600,
			"height": 1200,
			"platform": "IEXC"
		}

		return payload, None