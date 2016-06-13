
# TODO: Remove this when modules get proper localdir support
import sys
sys.path.append("modules/buildapcsales")


import time
import threading
import requests
import re
import bapc_filter as bapcfilter
from halibot import HalModule
from halibot import Message, Context

class BuildAPcSales(HalModule):

	run = False
	thread = None
	url = "http://reddit.com/r/buildapcsales/new.json?before={before}"
	form = "{title} ({domain}) - {short_url}"
	delay = 120
	last = ""
	resp = None
	target = ""

	def init(self):
		self.target = self.config["target"] # Mandatory, let error trickle up

		self.delay = self.config.get("delay",120)

		self.filters = {}
		for line in self.config.get("filters", ["all: .*"]):
			self.add_filter(line)

		self.form = self.config.get("format", self.form)

		self.start_watcher()

	def add_filter(self, line):
		name, fil = bapcfilter.parse_command(line)
		self.filters[name] = fil


	def start_watcher(self):
		self.thread = threading.Thread(target=self._refreshloop)
		self.run = True
		self.thread.start()

	# Join?
	def stop_watcher(self):
		self.run = False
		self.last = ""
		self.oldthread = self.thread
		self.oldthread.join(self.delay)
		if self.oldthread.is_alive():
			self.log.warning("Old thread did not stop!")


	def _refreshloop(self):
		self.first = True
		while self.run:
			r = self.resp = self.make_request(before=self.last)
			if r.ok and r.status_code == 200:
				try:
					new = self.parse(r.json()["data"]["children"], first=self.first)
					self.send_updates(new)
				except Exception as e:
					print("error parsing: " + str(e))
				# apply filters here
				self.first = False
			time.sleep(self.delay)

	# TODO move error checking into here, return only data?
	def make_request(self, **kwargs):
		return requests.get(self.url.format(**kwargs), headers={"User-Agent":"Mozilla/5.0"})


	def parse(self, data, first=False):
		new = []
		for d in data:
			d = d["data"]
			if d["stickied"]:
				continue
			for name, fil in self.filters.items():
				if fil.match(d['title']):
					new.append(d)
					continue # match only one filter for now

		if len(new):
			self.last = new[0]["name"]
		return new if not first else []

	def send_updates(self, new):
		msg = Message(context=Context(agent="irc",whom=self.target))
		for d in new:
			msg.body = self.outform(d)
			self.send_to(msg, ["irc"]) # TODO: Not need this

	def outform(self, entry):
		entry["short_url"] = "http://redd.it/" + entry["id"]
		return self.form.format(**entry)


	def receive(self, msg):
		ls = msg.body.split(' ')
		cmd = ls[0]
		arg = ' '.join(ls[1:]).strip()

		# TODO: Clean this up
		if cmd == "!bapc":
			if arg == "start" and not self.run:
				self.start_watcher()
				self.reply(msg, body="Started watcher")
			elif arg == "stop" and self.run:
				self.stop_watcher()
				self.reply(msg, body="Stopping watcher")
			elif arg == "restart":
				if self.run:
					self.reply(msg, body="Stopping watcher")
					self.stop_watcher()
					#time.sleep(self.delay)
				self.start_watcher()
				self.reply(msg, body="Started watcher")
			elif arg == "reset":
				self.last = ""
				self.first = True
			elif arg == "test":
				self.send_to(Message(context=Context(agent="irc",whom=self.target), body="Hello World!"), ["irc"])
			elif arg.startswith("filter"):
				args = arg.split(" ",2)[1:]
				try:
					if args[0] == "add":
						self.add_filter(args[1])
					elif args[0] == "show":
						for it in self.filters.values():
							self.reply(msg, body=it.line)
					elif args[0] in ("drop","del"):
						self.filters.pop(args[1])
				except:
					pass
