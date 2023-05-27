from os import environ
from time import time
from io import BytesIO
from base64 import decodebytes, b64encode
from requests import get
from traceback import format_exc

from PIL import Image
from twelvedata import TDClient

from components.abstract import AbstractProvider
from assets import static_storage


td = TDClient(apikey=environ["TWELVEDATA_KEY"])


class Twelvedata(AbstractProvider):
	name = "Twelvedata"

	@classmethod
	def _request_quote(cls, request, ticker):
		exchange = ticker["exchange"]
		if not exchange:
			return None, None

		try:
			if ticker.get("quote") is None: return None, f"Price for `{ticker.get('name')}` is not available on {exchange['name']}."
			if exchange.get("id") is not None and exchange["id"] != "forex":
				rawData = td.time_series(
					symbol=ticker.get("symbol"),
					exchange=exchange.get("name"),
					interval="1day",
					outputsize=2,
					timezone="UTC",
				).as_pandas()
			else:
				rawData = td.time_series(
					symbol=ticker.get("symbol"),
					interval="1day",
					outputsize=2,
					timezone="UTC",
				).as_pandas()
			if rawData is None: return None, None
		except:
			print(format_exc())
			return None, None

		try:
			if exchange.get("id") is not None and exchange["id"] != "forex":
				stockLogoThumbnail = td.get_logo(
					symbol=ticker.get("symbol"),
					exchange=exchange.get("name"),
				).as_json()["url"]
			else:
				stockLogoThumbnail = td.get_logo(
					symbol=ticker.get("symbol")
				).as_json()["url"]
		except:
			stockLogoThumbnail = static_storage.icon

		price = rawData["close"].tolist()
		volume = rawData["volume"].tolist()
		priceChange = ((price[0] / price[1] - 1) * 100) if len(price) > 1 else 0

		payload = {
			"quotePrice": "{:,.10f}".format(price[0]).rstrip('0').rstrip('.') + (" USD" if ticker.get("quote") is None else (" " + ticker.get("quote"))),
			"quoteVolume": "{:,.4f}".format(volume[0]).rstrip('0').rstrip('.') + " " + ticker.get("base"),
			"title": ticker.get("name"),
			"change": "{:+.2f} %".format(priceChange),
			"thumbnailUrl": stockLogoThumbnail,
			"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
			"sourceText": f"{ticker['id']} data on {exchange['name']}",
			"platform": "Twelvedata",
			"raw": {
				"quotePrice": price,
				"quoteVolume": volume,
				"timestamp": time()
			}
		}

		return payload, None

	@classmethod
	def request_details(cls, request):
		ticker = request.get("ticker")
		exchange = ticker["exchange"]
		if not exchange:
			return None, None

		try:
			companyData = td.get_profile(
				symbol=ticker.get("symbol"),
				exchange=ticker["exchange"].get("name"),
			).as_json()
			statsData = td.get_statistics(
				symbol=ticker.get("symbol"),
				exchange=exchange.get("name"),
			).as_json()
			rawData = td.time_series(
				symbol=ticker.get("symbol"),
				exchange=exchange.get("name"),
				interval="1day",
				outputsize=21,
				timezone="UTC",
			).as_pandas()
		except:
			print(format_exc())
			return None, None

		try:
			stockLogoThumbnail = td.get_logo(
				symbol=ticker.get("symbol"),
				exchange=exchange.get("name"),
			).as_json()["url"]
		except:
			stockLogoThumbnail = None

		closePrice = rawData["close"].tolist()
		openPrice = rawData["open"].tolist()

		payload = {
			"name": f"{companyData['name']} ({companyData['symbol']})",
			"description": companyData["description"],
			"industry": companyData["industry"],
			"url": companyData["website"] if companyData["website"].startswith("http") else "https://" + companyData["website"],
			"info": {
				"employees": companyData["employees"],
				"location": f"{companyData['address']}, {companyData['city']}, {companyData['state']}, {companyData['country']}"
			},
			"price": {
				"current": closePrice[0],
				"52w high": statsData["statistics"]["stock_price_summary"]["fifty_two_week_high"],
				"52w low": statsData["statistics"]["stock_price_summary"]["fifty_two_week_low"],
				"beta": statsData["statistics"]["stock_price_summary"]["beta"]
			},
			"valuation": {
				"enterprise value": statsData["statistics"]["valuations_metrics"]["enterprise_value"],
				"trailing PE": statsData["statistics"]["valuations_metrics"]["trailing_pe"],
				"forward PE": statsData["statistics"]["valuations_metrics"]["forward_pe"],
				"PEG": statsData["statistics"]["valuations_metrics"]["peg_ratio"],
				"P/S": statsData["statistics"]["valuations_metrics"]["price_to_sales_ttm"],
				"P/B": statsData["statistics"]["valuations_metrics"]["price_to_book_mrq"],
				"EV/R": statsData["statistics"]["valuations_metrics"]["enterprise_to_revenue"],
				"EV/EBITDA": statsData["statistics"]["valuations_metrics"]["enterprise_to_ebitda"]
			},
			"financials": {
				"profit margin": statsData["statistics"]["financials"]["profit_margin"],
				"operating margin": statsData["statistics"]["financials"]["operating_margin"],
				"ROS": statsData["statistics"]["financials"]["return_on_assets_ttm"],
				"ROE": statsData["statistics"]["financials"]["return_on_equity_ttm"],
			},
			"marketcap": statsData["statistics"]["valuations_metrics"]["market_capitalization"],
			"change": {
				"past day": (closePrice[0] / openPrice[0] - 1) * 100,
				"past month": (closePrice[0] / openPrice[-1] - 1) * 100,
				"past 52w": statsData["statistics"]["stock_price_summary"]["fifty_two_week_change"] * 100
			},
			"sourceText": "Data provided by Twelvedata",
			"platform": "Twelvedata",
		}

		if stockLogoThumbnail is not None: payload["image"] = stockLogoThumbnail

		return payload, None