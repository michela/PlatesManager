#!/usr/bin/env python
# encoding: utf-8
"""
ftp.py

Generate appropriate sftpapplet code (non validating) to log onto FTP site at given directory

Created by Michela Ledwidge on 2008-05-12.
Copyright (c) 2008 MOD Films. All rights reserved.
"""

import sys
import os
import logging
from elementtree import ElementTree
from genshi.template import TemplateLoader

template ='''
<html>
<body bg="#ffffff">
<h2>NOTE - Keep the FTP tab open on this page or you will lose the connection - RIGHT-CLICK any tabs to OPEN IN NEW WINDOW or OPEN IN NEW (Browser) TAB. </h2>
<object width="1200" height="600" classid="clsid:8AD9C840-044E-11D1-B3E9-00805F499D93" codebase="http://java.sun.com/products/plugin/autodl/jinstall-1_4-windows-i586.cab#Version=1,4,2,0">
   <param name="code" value="com.jscape.ftpapplet.FtpApplet.class">
   <param name="archive" value="/sftpapplet/sftpapplet.jar">
   <param name="scriptable" value="false">
   <param name="hostname" value="%s">
   <param name="username" value="%s">
   <param name="password" value="%s">
   <param name="autoConnect" value="true">
   <param name="passive" value="true">
   <param name="remoteDir" value="%s">
   <param name="showAboutButton" value ="false">
   <param name="bgColor" value="FFFFFF">
   <comment>
       <embed \
           type="application/x-java-applet;version=1.4" \
           code="com.jscape.ftpapplet.FtpApplet.class" \
           archive="/sftpapplet/sftpapplet.jar" \
           name="ftpapplet" \
           width="1200" \
           height="600" \
           scriptable="false" \
       showAboutButton="false" \
       bgColor="FFFFFF" \
       hostname="%s" \
       username="%s" \
		password="%s" \
		autoConnect="true" \
		remoteDir="%s" \
		passive ="true" \
                 pluginspage = "http://java.sun.com/products/plugin/index.html#download">
                   <noembed>           
           </noembed>
       </embed>
   </comment>
</object>
</body>
</html>
'''
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


def index(req,remoteDir = '/'):
	global template
	config = loadConfig(req)
	logging.debug(remoteDir)
	hostname = config['ftpServer']
	username = config['ftpUser']
	password = config['ftpPassword']
#	return "%s %s %s %s "% (hostname,username,password,remoteDir)
	logging.debug("%s %s %s %s "% (hostname,username,password,remoteDir))
	result = template % (hostname,username,password,remoteDir,hostname,username,password,remoteDir)
	return result


if __name__ == "__main__":
		sys.exit(index(None))

