#!/usr/bin/env python
# encoding: utf-8
"""
video.py

Generate appropriate video code 

Created by Michela Ledwidge on 2008-05-25.
Copyright (c) 2008 MOD Films. All rights reserved.
"""

import sys
import os
import logging
from elementtree import ElementTree
from genshi.template import TemplateLoader

class Page:
	def __init__(self,template, params):
		loader = TemplateLoader(
		    os.path.join(os.path.dirname(__file__), '../../templates'), auto_reload=True
		)
		tmpl = loader.load(template)
		self.render = tmpl.generate(params = params).render('html',doctype='html')

def loadConfig(req):
	'''Set globals and load config values from external XML file'''

	result = {}
	logging.basicConfig(level=logging.DEBUG,
	                    format='%(asctime)s %(levelname)s %(message)s',
	                    filename='/var/log/mod/update.log',
	                    filemode='w')
	# define a Handler which writes INFO messages or higher to the sys.stderr
	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	# set a format which is simpler for console use
	formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
	# tell the handler to use this format
	console.setFormatter(formatter)
	# add the handler to the root logger
	logging.getLogger('').addHandler(console)
	options = req.get_options()
	#options = apache.main_server.get_options()  # mod_python 3.3 apparently
	config = options["MODFILMS_CONFIG"]
	try:
		root = ElementTree.parse(config)
	except OSError, e:
		logging.error("Config error: " + e)
		logging.error("Check MODFILMS_CONFIG environment variable is set")
	for i in root.getiterator():
		if i.tag =='config':
			pass
		else:
			result.update({i.tag:i.text})
#	logging.info("Config loaded" + result)

	# TODO use /usr/bin/env instead
	if (os.path.exists('/usr/local/bin/gm') == True):
		result['gm'] = '/usr/local/bin/gm'
	elif (os.path.exists('/usr/bin/gm') == True):
			result['gm'] = '/usr/bin/gm'
	else:
		result['gm'] == None
	return result


def index(req,url,width=720,height=405,title="Video"):
	config = loadConfig(req)
#	logging.debug("%s %s %s %s "% (hostname,username,password,remoteDir))
	params = {}
	params['url'] = url
	params['width'] = width
	params['height'] = height
	params['title'] = title
	params['src'] = "http://%s%s" % (config['httpServer'], '/swf/player.swf')
	params['movie'] = "http://%s%s" % (config['httpServer'], '/swf/player')
	return Page('video.html',params).render
	return result


if __name__ == "__main__":
		sys.exit(index(None))

