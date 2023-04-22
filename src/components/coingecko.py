from os import environ
from time import time
from traceback import format_exc

from pycoingecko import CoinGeckoAPI
from markdownify import markdownify

from components.abstract import AbstractProvider
from assets import static_storage


class CoinGecko(AbstractProvider):
	name = "CoinGecko"
	connection = CoinGeckoAPI(api_key=environ["COINGECKO_API_KEY"])

	@classmethod
	def _request_quote(cls, request, ticker):
		preferences = request.get("preferences")
		action = next((e.get("value") for e in preferences if e.get("id") == "lld"), None)

		if action == "dom":
			try: rawData = CoinGecko.connection.get_global()
			except: return None, f"Requested dominance data for `{ticker.get('name')}` is not available."
			if ticker.get("base").lower() not in rawData["market_cap_percentage"]: return None, f"Dominance for {ticker.get('base')} does not exist."
			coinDominance = rawData["market_cap_percentage"][ticker.get("base").lower()]

			coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

			payload = {
				"quotePrice": "{} dominance: {:,.2f} %".format(ticker.get("base"), coinDominance),
				"title": "Market Dominance",
				"thumbnailUrl": coinThumbnail,
				"messageColor": "deep purple",
				"sourceText": "Market information from CoinGecko",
				"platform": CoinGecko.name,
				"raw": {
					"quotePrice": [coinDominance],
					"timestamp": time()
				}
			}
			return payload, None

		else:
			try:
				rawData = CoinGecko.connection.get_coin_by_id(id=ticker.get("symbol"), localization="false", tickers=False, market_data=True, community_data=False, developer_data=False)
			except:
				print(format_exc())
				return None, None

			coinThumbnail = static_storage.icon if ticker.get("image") is None else ticker.get("image")

			if ticker.get("quote").lower() not in rawData["market_data"]["current_price"] or ticker.get("quote").lower() not in rawData["market_data"]["total_volume"]: return None, None

			price = rawData["market_data"]["current_price"][ticker.get("quote").lower()]
			volume = rawData["market_data"]["total_volume"][ticker.get("quote").lower()]
			priceChange = rawData["market_data"]["price_change_percentage_24h_in_currency"][ticker.get("quote").lower()] if ticker.get("quote").lower() in rawData["market_data"]["price_change_percentage_24h_in_currency"] else 0

			priceText = "{:,.8g}".format(price)
			if price < 1 and "e-" in priceText:
				number, exponent = priceText.split("e-", 1)
				priceText = ("{:,.%df}" % (len(number) + int(exponent) - 2)).format(price).rstrip('0')

			payload = {
				"quotePrice": priceText + " " + ticker.get("quote"),
				"quoteVolume": "{:,.4f}".format(volume).rstrip('0').rstrip('.') + " " + ticker.get("base"),
				"title": ticker.get("name"),
				"change": "{:+.2f} %".format(priceChange),
				"thumbnailUrl": coinThumbnail,
				"messageColor": "amber" if priceChange == 0 else ("green" if priceChange > 0 else "red"),
				"sourceText": f"{ticker['id']} data from CoinGecko",
				"platform": CoinGecko.name,
				"raw": {
					"quotePrice": [price],
					"quoteVolume": [volume],
					"timestamp": time()
				}
			}
			if ticker.get("quote") != "USD":
				payload["quoteConvertedPrice"] = "≈ ${:,.6f}".format(rawData["market_data"]["current_price"]["usd"])
				payload["quoteConvertedVolume"] = "≈ ${:,.4f}".format(rawData["market_data"]["total_volume"]["usd"])

			return payload, None

	@classmethod
	def request_details(cls, request):
		ticker = request.get("ticker")

		try:
			assetData = CoinGecko.connection.get_coin_by_id(id=ticker.get("symbol"), localization="false", tickers=False, market_data=True, community_data=True, developer_data=True)
			historicData = CoinGecko.connection.get_coin_ohlc_by_id(id=ticker.get("symbol"), vs_currency="usd", days=365)
		except:
			return None, None

		description = markdownify(assetData["description"].get("en", "No description"))
		descriptionParagraphs = description.split("\r\n\r\n")
		textLength = [len(descriptionParagraphs[0])]
		for i in range(1, len(descriptionParagraphs)):
			nextLength = textLength[-1] + len(descriptionParagraphs[i])
			if nextLength > 500 and textLength[-1] > 300 or nextLength > 1900: break
			textLength.append(nextLength)
		description = "\n".join(descriptionParagraphs[:len(textLength)])[:] + f"\n[Read more on CoinGecko](https://www.coingecko.com/coins/{ticker.get('symbol')})"

		highs = [e[2] for e in historicData]
		lows = [e[3] for e in historicData]

		payload = {
			"name": f"{assetData['name']} ({ticker.get('base')})",
			"description": description,
			"rank": assetData["market_data"]["market_cap_rank"],
			"supply": {},
			"score": {
				"developer": assetData["developer_score"],
				"community": assetData["community_score"],
				"liquidity": assetData["liquidity_score"],
				"public interest": assetData["public_interest_score"]
			},
			"price": {
				"current": assetData["market_data"]["current_price"].get("usd"),
				"ath": assetData["market_data"]["ath"].get("usd"),
				"atl": assetData["market_data"]["atl"].get("usd")
			},
			"change": {
				"past day": assetData["market_data"]["price_change_percentage_24h_in_currency"].get("usd"),
				"past month": assetData["market_data"]["price_change_percentage_30d_in_currency"].get("usd"),
				"past year": assetData["market_data"]["price_change_percentage_1y_in_currency"].get("usd")
			},
			"sourceText": "Data from CoinGecko",
			"platform": "CoinGecko",
		}

		if assetData["image"]["large"].startswith("http"): payload["image"] = assetData["image"]["large"]
		if assetData["links"]["homepage"][0] != "": payload["url"] = assetData["links"]["homepage"][0].replace(" ", "") if assetData["links"]["homepage"][0].replace(" ", "").startswith("http") else "https://" + assetData["links"]["homepage"][0].replace(" ", "")
		if assetData["market_data"]["total_volume"] is not None: payload["volume"] = assetData["market_data"]["total_volume"].get("usd")
		if assetData["market_data"]["market_cap"] is not None: payload["marketcap"] = assetData["market_data"]["market_cap"].get("usd")
		if assetData["market_data"]["total_supply"] is not None: payload["supply"]["total"] = assetData["market_data"]["total_supply"]
		if assetData["market_data"]["circulating_supply"] is not None: payload["supply"]["circulating"] = assetData["market_data"]["circulating_supply"]
		if len(highs) != 0: payload["price"]["1y high"] = max(highs)
		if len(lows) != 0: payload["price"]["1y low"] = min(lows)

		return payload, None