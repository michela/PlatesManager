#!/usr/bin/env python
# encoding: utf-8
"""
ftpmon.py

runs on CGI. Processes actions from Incoming Plates system

Created by Michela Ledwidge on 2008-03-27
Copyright (c) 2008 MOD Films. All rights reserved.
"""

import os
import sys
import getopt
import urllib2
import csv
import crypt
import time
from genshi.template import TemplateLoader
from popen2 import Popen4
import logging
from elementtree import ElementTree
import string
import fnmatch
import json
import shutil
import re
from trac.env import Environment
import smtplib
from htmlEmailer import *
import syslog

help_message = '''
sudo python ftpmon.py

e.g.
sudo python useradmin.py'''

def testconfig(req):
	config = loadConfig(req)
	return config
	
def loadConfig(req):
	'''Set globals and load config values from external XML file'''

	result = {}
	options = req.get_options()
	#options = apache.main_server.get_options()  # mod_python 3.3 apparently
	config = options["MODFILMS_CONFIG"]
	try:
		root = ElementTree.parse(config)
	except OSError, e:
		print "Config error: " + e
		print "Check MODFILMS_CONFIG environment variable is set"
	for i in root.getiterator():
		if i.tag =='config':
			pass
		else:
			result.update({i.tag:i.text})
	logging.info("Config loaded:",result)

	# TODO use /usr/bin/env instead
	if (os.path.exists('/usr/local/bin/gm') == True):
		result['gm'] = '/usr/local/bin/gm'
	elif (os.path.exists('/usr/bin/gm') == True):
			result['gm'] = '/usr/bin/gm'
	else:
		result['gm'] == None
	return result

def testsmtp(req,msg,SENDER="modfilms.net <reception@modfilms.net>",RECIPIENT= "michela@thequality.com"):
	"""testing SMPTP settings"""
	session = smtplib.SMTP('outbound.mailhop.org')
	session.login('modfilms','f@milyman')
	theMsg = createhtmlmail('testing', 'testing', 'testing delivery from /update/ftpmon.py')
	headers = "From: %s\r\nTo: %s\r\n" % (SENDER, RECIPIENT)
	message = headers + theMsg
	smtpresult = session.sendmail(SENDER, RECIPIENT, message)
	if smtpresult:
		errstr = ""
		for recip in smtpresult.keys():
			errstr = """Could not delivery mail to: %s

	Server said: %s
	%s

	%s""" % (recip, smtpresult[recip][0], smtpresult[recip][1], errstr)
		raise smtplib.SMTPException, errstr
	session.quit()
	
def realpath(req,path):
	'''Return real path after security checks'''
	config = loadConfig(req)
	ftpdropbox = config['ftpdropbox']
	path = ftpdropbox + path

	# check for hack
	if path == ftpdropbox + '/':
		return(False,"Unsafe path")
	l = string.find(path,'..')
	if l != -1:
		return (False,"Unsafe path")
	
	# check if exists
	if os.path.exists(path):
		return (True, path)
	else:
		return (False,"Doesn't exist " + path)

def locate(pattern, root):
	for path, dirs, files in os.walk(os.path.abspath(root)):
		for filename in fnmatch.filter(files, pattern):
			yield os.path.join(path, filename)
		
def cleanUp(path,type):
	if type not in ('proxy','all','jpg'):
		return (False, "invalid type")
	if type == 'proxy':
		path = path + '/preview.mov'	
	if os.path.isdir(path) and type == 'all':
		try:
			os.rmdir(path)
			return (True,'all deleted')
		except OSError, s:
			return False, str(s)
	elif not os.path.isdir(path) and type == 'proxy':
		try:
			os.remove(path)
			return (True,'proxy deleted')
		except OSError, s:
			return False, str(s)
	else:
		return False, "Usage error: path = %s, type = %s" % (path, type)
				
def redo(req,path,jsoncallback):
	res = {}
	res['good'],res['path'] = realpath(req,path)
	if not res['good']:
		res['err'] = res['path'] 
		syslog.syslog('ftpmon: ' + res['path'])
		return "%s(%s)" % (jsoncallback,json.write(res))
	res['good'],res['err']  = cleanUp(res['path'],'proxy')
	return "%s(%s)" % (jsoncallback,json.write(res))
	
def alert(req,path):
	return "the path is " + path

def test(req,path,jsoncallback):
	config = loadConfig(req)
	msg = config['ftpdropbox'] + '/testing1'
	return config['project']
	#return "%s({\"true\":\"true\",\"msg\":\"%s\"})" % (jsoncallback,msg)

def dump(req):
    req.content_type = "text/html"

    req.add_common_vars()
    env_vars = req.subprocess_env.copy()
    options = req.get_options()

    req.write('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')
    req.write('<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">')
    req.write('<head><title>mod_python.publisher</title></head>')
    req.write('<body>')
    req.write('<h1>Environment Variables</h1>')
    req.write('<table border="1">')
    for key in env_vars:
        req.write('<tr><td>%s</td><td>%s</td></tr>' % (key, env_vars[key]))
    for key in options:
        req.write('<tr><td>%s</td><td>%s</td></tr>' % (key, options[key]))	
    req.write('</table>')
    req.write('</body>')
    req.write('</html>')

def delete(req,path,jsoncallback):
	res = {}
	res['good'],res['path'] = realpath(req,path)
	if not res['good']: 
		res['err'] = res['path'] 
		return "%s(%s)" % (jsoncallback,json.write(res))
	files = []
	for file in locate("*",res['path']):
		try:
			os.remove(file)
		except OSError, s:
			res['err'] = s
			syslog.syslog('ftpmon/delete: ' + s)
			return "%s(%s)" % (jsoncallback,json.write(res))
	#return files
	res['good'],res['err'] = cleanUp(res['path'],'all')
	return "%s(%s)" % (jsoncallback,json.write(res))

def publish(req,path,jsoncallback):
	"""Copy the video using a valid file naming convention (<dir>.mov) so that the monitor will pick it up as a preview render and
publish it to the render tracker"""
	res = {}
	res['good'],res['path'] = realpath(req,path)
	if res['good']:
		dir = res['path'].split('/')[-1]
		preview =res['path'] + '/preview.mov'
		copy = res['path'] + '/' + dir + '.mov' 
		print "renaming  %s to %s" % (preview, copy)
		try:
			shutil.copyfile(preview,copy)
			res['good'] = True
			res['err'] = 'Published to the render tracker'
		except OSError, e:
			res['err'] = e
			res['good'] = False
	return "%s(%s)" % (jsoncallback,json.write(res))


def validateEmail(email):
	"""http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/65215"""
	if len(email) > 7:
		if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email) != None:
			return True
	return False

def isList(l):
	list = []
	if type(l) == type(list):
		return True
	else:
		return False

def emailer(req, fromPage,name, fromAddr, toAddr, subject, msg,jsoncallback):
	"""Perform sanity/security checks, look up usernames from trac and send message as reception@modfilms.net.
req = CGI
name = Friendly
from = email address	
"""
	res = {}
	# bar access to everyone but this server
	#req.add_common_vars()
	#env_vars = req.subprocess_env.copy()
	#env_vars['']	
	config = loadConfig(req)
	text = msg.replace('%0A','\n')
	html = msg.replace('%0A','<br />')
	config['from'] = fromAddr
	config['name'] = name
	config['subject'] = subject
	list = []
	addresses = toAddr.split(',')
	for name in addresses:
		if not validateEmail(name):
			# look up DB
			env = Environment(config['tracRendersEnv'])
			db = env.get_db_cnx()
			cursor = db.cursor()
			sql = "SELECT value from session_attribute where sid = '%s' and name = 'email'" % name
			cursor.execute(sql)
			db.commit()
			for row in cursor:
				list.append(row[0])
		else:
			list.append(name)
	config['smtpserver'] = smtplib.SMTP(config['smtpserver'])
#	config['smtpserver'] = smtplib.SMTP('outbound.mailhop.org')
	config['smtpserver'].set_debuglevel(1)
#	config['smtpserver'].login('modfilms','f@milyman')
	
	toAddrFiltered = ','.join(list)	
	textMsg = """
This was sent from http://%s

%s says "%s"

Powered by http://modfilms.net | Contact us at reception@modfilms.net
""" % (config['httpServer'] + fromPage, config['name'], text)
	htmlMsg = """
<html>
<head>
<link rel="stylesheet" href="http://modfilms.com/js/themes/flora/flora.all.css" type="text/css" media="screen" title="Flora (Default)" />
<link rel="stylesheet" href="http://modfilms.com/js/demos/css/style.css" type="text/css" />
</head>
<body>
<p>This was sent from <a href="%s">http://%s</a></p>
<p>%s says: </p>
<p><i>"%s"</i></p>
<p>Email <a href="mailto:reception@modfilms.net">reception@modfilms.net</a> if you need assistance</p>
<p><a href="http://modfilms.net"><img border="0" src="http://modfilms.com/images/poweredby.gif" alt="Powered by the MOD Films network"></p>
</body>
</html>
""" % (config['httpServer'] + fromPage,config['httpServer'] + fromPage,config['name'], html)
	
#	theMsg = createhtmlmail(htmlMsg, textMsg, subject)
	theMsg = createtextmail(textMsg,subject)
	SENDER = config['from']
	RECIPIENT = toAddrFiltered
	headers = "From: %s\r\nTo: %s\r\n" % (SENDER, RECIPIENT)
	message = headers + theMsg
	try:
		smtpresult = config['smtpserver'].sendmail(SENDER, RECIPIENT, message)
		if smtpresult:
			errstr = ""
			for recip in smtpresult.keys():
				errstr = """Could not delivery mail to: %s

		Server said: %s
		%s

		%s""" % (recip, smtpresult[recip][0], smtpresult[recip][1], errstr)
			raise smtplib.SMTPException, errstr
		config['smtpserver'].quit()
		res['err'] = 'Email sent'
		res['good'] = True
	except smtplib.SMTPRecipientsRefused, recipients:
		res['err'] = 'Message not sent. Check the email addresses or studio usernames are valid.'
		res['good'] = False
	except smtplib.SMTPException, errstr:
		res['err'] = errstr
		res['good'] = False
	return "%s(%s)" % (jsoncallback,json.write(res))


def main(argv=None):
	if argv is None:
		argv = sys.argv
	try:
		try:
			opts, args = getopt.getopt(argv[1:], "u:p:ho:v", ["user=", "password=", "help", "output="])
		except getopt.error, msg:
			raise Usage(msg)
	
		# option processing
		for option, value in opts:
			if option == "-v":
				verbose = True
			else:
				verbose = False
			if option in ("-h", "--help"):
				raise Usage(help_message)
			if option in ("-o", "--output"):
				output = value
			if option in ("-u", "--user"):
				user = value
			if option in ("-p", "--password"):
				password = value
		try:
			# main process
				
			return "Got here!"
			#return Page('group.html','modfilms.net | IAA | User Management | Update Group','User group updated from ZohoSheet').render
			
		except UnboundLocalError, msg:
			raise Usage(msg)
			
	
	except Usage, err:
		print >> sys.stderr, sys.argv[0].split("/")[-1] + ": " + str(err.msg)
		print >> sys.stderr, "\t for help use --help"
		return 2
	
	
# http://sheet.zoho.com/api/private/xls/download/[bookId]?apikey=[apikey]&ticket=[ticket]
	
if __name__ == "__main__":
	sys.exit(main())

