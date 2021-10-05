from time import time
from abc import ABCMeta, abstractmethod
from io import BytesIO
from random import random
from orjson import dumps, OPT_SORT_KEYS

from google.cloud.storage import Client as StorageClient
from PIL import Image
from matplotlib import pyplot as plt
from matplotlib import ticker as tkr
import matplotlib.transforms as mtransforms
from lark import Tree, Token, Transformer, v_args

from assets import static_storage


storage_client = StorageClient()

plt.switch_backend("Agg")
plt.ion()
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams['figure.figsize'] = (8, 6)
plt.rcParams["figure.dpi"] = 200.0
plt.rcParams['savefig.facecolor'] = "#131722"


class AbstractProvider(object):
	__metaclass__ = ABCMeta
	bucket = storage_client.get_bucket("nlc-bot-36685.appspot.com")
	stableCoinTickers = ["USD", "USDT", "USDC", "DAI", "HUSD", "TUSD", "PAX", "USDK", "USDN", "BUSD", "GUSD", "USDS"]

	@classmethod
	def request_quote(cls, request, **kwargs):
		ticker = request.get("ticker")
		tree = ticker.pop("tree")
		if tree is None: return [{}, ""]

		tickerTree = cls.build_tree(tree)

		if not ticker.get("isSimple"):
			priceCalculatorTree = AbstractProvider.CalculateTree(cls, request, "quotePrice", **kwargs)
			try: price = priceCalculatorTree.transform(tickerTree)
			except: return [{}, priceCalculatorTree.error]
			if priceCalculatorTree.error is not None:
				return [{}, priceCalculatorTree.error]

			volumeCalculatorTree = AbstractProvider.CalculateTree(cls, request, "quoteVolume", **kwargs)
			volumeCalculatorTree.vars = priceCalculatorTree.vars
			try: volume = volumeCalculatorTree.transform(tickerTree)
			except: return [{}, priceCalculatorTree.error]
			if volumeCalculatorTree.error is not None:
				return [{}, volumeCalculatorTree.error]

			payload = {
				"quotePrice": "{:,.8f}".format(price).rstrip("0").rstrip("."),
				"quoteVolume": "{:,.8f}".format(volume).rstrip("0").rstrip("."),
				"title": ticker.get("name"),
				"thumbnailUrl": static_storage.icon,
				"messageColor": "amber",
				"sourceText": "Data provided by Alpha",
				"platform": "Alpha",
				"raw": {
					"quotePrice": [price],
					"quoteVolume": [volume],
					"timestamp": time()
				}
			}
			quoteMessage = ""
		else:
			[payload, quoteMessage] = cls._request_quote(request, tickerTree.children[0].value, **kwargs)
		
		return [payload, quoteMessage]

	@classmethod
	@abstractmethod
	def _request_quote(cls, request, ticker, **kwargs):
		raise NotImplementedError

	@classmethod
	def request_depth(cls, request, **kwargs):
		ticker = request.get("ticker")
		tree = ticker.pop("tree")
		if tree is None: return [{}, ""]

		tickerTree = cls.build_tree(tree)

		if not ticker.get("isSimple"):
			payload = {}
			quoteMessage = "Aggregated depth chart is not available yet."
		else:
			[payload, quoteMessage] = cls._request_depth(request, tickerTree.children[0].value, **kwargs)

		return [payload, quoteMessage]

	@classmethod
	@abstractmethod
	def _request_depth(cls, request, ticker, **kwargs):
		raise NotImplementedError

	@v_args(inline=True)
	class CalculateTree(Transformer):
		from operator import add, sub, mul, truediv as div, neg
		number = float

		def __init__(self, cls, request, requestType, **kwargs):
			self.cls = cls
			self.request = request
			self.requestType = requestType
			self.kwargs = kwargs
			self.vars = {}
			self.error = None

		def assign_var(self, name, value):
			self.vars[name] = value
			return value

		def var(self, name):
			hashName = dumps(name.value, option=OPT_SORT_KEYS)
			try:
				return self.vars[hashName][self.requestType][0]
			except KeyError:
				[response, quoteMessage] = self.cls._request_quote(self.request, name.value, **self.kwargs)
				if not bool(response) or quoteMessage != "":
					self.error = quoteMessage
					return random()
				else:
					return self.assign_var(hashName, response["raw"])[self.requestType][0]

	@classmethod
	def build_tree(cls, l):
		if l[0] in ["NUMBER", "NAME"]: return Token(l[0], l[1])
		else: return Tree(l[0], [cls.build_tree(e) for e in l[1]])

	@classmethod
	def _generate_depth_image(cls, depthData, bestBid, bestAsk, lastPrice):
		bidTotal = 0
		xBids = [bestBid[0]]
		yBids = [0]
		for bid in depthData['bids']:
			if len(xBids) < 10 or bid[0] > lastPrice * 0.9:
				bidTotal += bid[1]
				xBids.append(bid[0])
				yBids.append(bidTotal)

		askTotal = 0
		xAsks = [bestAsk[0]]
		yAsks = [0]
		for ask in depthData['asks']:
			if len(xAsks) < 10 or ask[0] < lastPrice * 1.1:
				askTotal += ask[1]
				xAsks.append(ask[0])
				yAsks.append(askTotal)

		fig = plt.figure(facecolor="#131722")
		ax = fig.add_subplot(1, 1, 1)
		ax.tick_params(color="#787878", labelcolor="#D9D9D9")
		ax.step(xBids, yBids, where="mid", color="#27A59A")
		ax.step(xAsks, yAsks, where="mid", color="#EF534F")
		ax.fill_between(xBids, yBids, 0, facecolor="#27A59A", interpolate=True, step="mid", alpha=0.33, zorder=2)
		ax.fill_between(xAsks, yAsks, 0, facecolor="#EF534F", interpolate=True, step="mid", alpha=0.33, zorder=2)
		plt.axvline(x=lastPrice, color="#758696", linestyle="--")

		ax.set_facecolor("#131722")
		for spine in ax.spines.values():
			spine.set_edgecolor("#787878")
		ax.autoscale(enable=True, axis="both", tight=True)

		def on_draw(event):
			bboxes = []
			for label in ax.get_yticklabels():
				bbox = label.get_window_extent()
				bboxi = bbox.transformed(fig.transFigure.inverted())
				bboxes.append(bboxi)

			bbox = mtransforms.Bbox.union(bboxes)
			if fig.subplotpars.left < bbox.width:
				fig.subplots_adjust(left=1.1 * bbox.width)
				fig.canvas.draw()
			return False

		ax.yaxis.set_major_formatter(tkr.FuncFormatter(lambda x, p: format(int(x), ',')))
		plt.setp(ax.get_xticklabels(), rotation=45, horizontalalignment='right')
		lastPriceLabel = bestAsk[0] if bestAsk[1] >= bestBid[1] else bestBid[0]
		xLabels = list(plt.xticks()[0][1:])
		yLabels = list(plt.yticks()[0][1:])
		for label in xLabels:
			plt.axvline(x=label, color="#363C4F", linewidth=1, zorder=1)
		for label in yLabels:
			plt.axhline(y=label, color="#363C4F", linewidth=1, zorder=1)
		diffLabels = 1 - xLabels[0] / xLabels[1]
		bottomBound, topBound = lastPriceLabel * (1 - diffLabels * (1/4)), lastPriceLabel * (1 + diffLabels * (1/4))
		xLabels = [l for l in xLabels if not (bottomBound <= l <= topBound)]

		plt.xticks(xLabels + [lastPriceLabel])
		plt.yticks(yLabels)
		ax.set_xlim([xBids[-1], xAsks[-1]])
		ax.set_ylim([0, max(bidTotal, askTotal)])

		fig.canvas.mpl_connect("draw_event", on_draw)
		plt.tight_layout()

		rawImageData = BytesIO()
		plt.savefig(rawImageData, format="png", edgecolor="none")
		plt.close(fig)
		rawImageData.seek(0)
		return Image.open(rawImageData)