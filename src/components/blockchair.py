from time import time
from datetime import datetime, timezone
from requests import get

from components.abstract import AbstractProvider
from assets import static_storage


CCXT_TO_BLOCKCHAIR = {
	"BTC": "bitcoin",
	"BCH": "bitcoin-cash"
}


class Blockchair(AbstractProvider):
	name = "Blockchair"

	@classmethod
	def _request_quote(cls, request, ticker):
		tickerId = ticker.get("id")

		if tickerId.endswith(".HALVING"):
			r = get("https://api.blockchair.com/tools/halvening").json()
			asset = CCXT_TO_BLOCKCHAIR[ticker.get("base")]
			rawData = r["data"][asset]

			halvingTime = datetime.strptime(rawData["halvening_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

			payload = {
				"quotePrice": f"≈ <t:{int(datetime.timestamp(halvingTime))}:R>",
				"quoteConvertedPrice": f"≈ <t:{int(datetime.timestamp(halvingTime))}>",
				"title": f"{ticker.get('name')} Halving",
				"thumbnailUrl": ticker.get("image"),
				"messageColor": "deep purple",
				"sourceText": "Data provided by Blockchair",
				"platform": Blockchair.name,
				"raw": {
					"quotePrice": [int(datetime.timestamp(halvingTime))],
					"timestamp": time()
				}
			}

			return payload, None

		else:
			return None, None