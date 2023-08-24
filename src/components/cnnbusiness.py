from time import time
from requests import get

from components.abstract import AbstractProvider
from assets import static_storage


class CNNBusiness(AbstractProvider):
	name = "CNN Business"

	@classmethod
	def _request_quote(cls, request, ticker):
		r = get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", headers={
			"Accept": "application/json",
			"Origin": "https://edition.cnn.com",
			"Accept-Encoding": "gzip, deflate, br",
			"Host": "production.dataviz.cnn.io",
			"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
			"Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
			"Referer": "https://edition.cnn.com/",
		}).json()
		fearGreedIndex = int(round(r["fear_and_greed"]["score"]))

		payload = {
			"quotePrice": str(fearGreedIndex),
			"quoteConvertedPrice": f"≈ {r['fear_and_greed']['rating']}",
			"title": "Stock market Fear & Greed Index",
			"change": "{:+.0f} since yesterday".format(fearGreedIndex - int(r["fear_and_greed"]["previous_close"])),
			"thumbnailUrl": "https://cdn1.iconfinder.com/data/icons/metro-ui-dock-icon-set--icons-by-dakirby/512/CNN.png",
			"messageColor": "deep purple",
			"sourceText": "Data provided by Alternative.me",
			"platform": CNNBusiness.name,
			"raw": {
				"quotePrice": [fearGreedIndex],
				"timestamp": time()
			}
		}
		return payload, None