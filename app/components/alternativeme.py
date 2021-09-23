from time import time
from requests import get

from components.abstract import AbstractProvider
from assets import static_storage


class Alternativeme(AbstractProvider):
	name = "Alternative.me"
	
	@classmethod
	def _request_quote(cls, request, ticker):
		r = get("https://api.alternative.me/fng/?limit=2&format=json").json()
		fearGreedIndex = int(r["data"][0]["value"])

		payload = {
			"quotePrice": fearGreedIndex,
			"quoteConvertedPrice": "≈ {}".format(r["data"][0]["value_classification"].lower()),
			"title": "Fear & Greed Index",
			"change": "{:+.0f} since yesterday".format(fearGreedIndex - int(r["data"][1]["value"])),
			"thumbnailUrl": static_storage.icon,
			"messageColor": "deep purple",
			"sourceText": "Data provided by Alternative.me",
			"platform": Alternativeme.name,
			"raw": {
				"quotePrice": [fearGreedIndex],
				"timestamp": time()
			}
		}
		return [payload, ""]