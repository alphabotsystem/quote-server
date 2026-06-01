from time import time
from abc import ABCMeta, abstractmethod
from random import random
from orjson import dumps, OPT_SORT_KEYS
from traceback import format_exc

from lark import Tree, Token, Transformer, v_args

from assets import static_storage


class AbstractProvider(object):
	__metaclass__ = ABCMeta

	@classmethod
	def request_quote(cls, request, **kwargs):
		ticker = request.get("ticker")
		tree = ticker.pop("tree")
		if tree is None: return None, None

		tickerTree = cls.build_tree(tree)

		if not ticker.get("isSimple"):
			priceCalculatorTree = AbstractProvider.CalculateTree(cls, request, "quotePrice", **kwargs)
			try:
				price = priceCalculatorTree.transform(tickerTree)
			except ZeroDivisionError:
				price = 0
			except:
				print(format_exc())
				return None, priceCalculatorTree.error

			if priceCalculatorTree.error is not None:
				return None, priceCalculatorTree.error

			volumeCalculatorTree = AbstractProvider.CalculateTree(cls, request, "quoteVolume", **kwargs)
			volumeCalculatorTree.vars = priceCalculatorTree.vars

			try:
				volume = volumeCalculatorTree.transform(tickerTree)
			except ZeroDivisionError:
				volume = 0
			except:
				print(format_exc())
				return None, priceCalculatorTree.error

			if volumeCalculatorTree.error is not None:
				return None, volumeCalculatorTree.error

			payload = {
				"quotePrice": "{:,.8f}".format(price).rstrip("0").rstrip("."),
				"quoteVolume": "{:,.8f}".format(volume).rstrip("0").rstrip("."),
				"title": ticker.get("name"),
				"thumbnailUrl": static_storage.icon,
				"messageColor": "amber",
				"sourceText": "Data provided by Alpha.bot",
				"platform": "Alpha.bot",
				"raw": {
					"quotePrice": [price],
					"quoteVolume": [volume],
					"timestamp": time()
				}
			}
			quoteMessage = None
		else:
			[payload, quoteMessage] = cls._request_quote(request, ticker, **kwargs)

		return payload, quoteMessage

	@classmethod
	@abstractmethod
	def _request_quote(cls, request, ticker, **kwargs):
		raise NotImplementedError

	@v_args(inline=True)
	class CalculateTree(Transformer):
		from operator import add, sub, mul, truediv as div, neg
		number = float
		exp = pow

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
				if not bool(response) or quoteMessage is not None:
					self.error = quoteMessage
					return random()
				else:
					return self.assign_var(hashName, response["raw"]).get(self.requestType, [0])[0]

	@classmethod
	def build_tree(cls, l):
		if l[0] in ["CONSTANT", "NAME", "QUOTED"]: return Token(l[0], l[1])
		else: return Tree(l[0], [cls.build_tree(e) for e in l[1]])