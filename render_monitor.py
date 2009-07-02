#!/usr/bin/env python
# encoding: utf-8
"""
render_monitor.py

Created by Michela Ledwidge on 2007-09-24.
Copyright (C) 2007 MOD Films
All rights reserved.

Intended as cronjob to monitor a dropbox folder for plates  

Previews are then published and thumbnails extracted.

Apache rewrite convention used to abstract paths to media files from code (enabling instances to decide on their own conventions)

e.g.

RewriteEngine on
RewriteRule     (\w\w)_(\d+_?\w?)/render$       /media/sanctuary/sanc_post_produ
ction/$1_$2_h264.mov [R]
RewriteRule     (\w\w)_(\d+_?\w?)/thumb$        /media/sanctuary/sanc_post_produ
ction/$1_$2.jpg [R]
RewriteRule     (\w\w)_(\d+_?\w?)_(\w+)_([A-Za-z_-]+)/render$    /media/sanctuar
y/sanc_post_production/$1_$2_$3_$4.mov [R]
RewriteRule     (\w\w)_(\d+_?\w?)_(\w+)_([A-Za-z_-]+)/thumb$   /media/sanctuary/
sanc_post_production/$1_$2_$3_$4.jpg [R]
RewriteRule    ^/shot/([a-z][a-z])_(.+)/library$  http://trac.modfilms.com:7861/
trac/sanctuary/browser/sanctuary/trunk/sequences/$1/$1_$2/ [R]

RewriteRule     ^/testing\.html$                nowtesting.html [R]
RewriteLog "/var/log/apache2/rewrite.log"
RewriteLogLevel 9
"""

import sys, stat, re, shutil
import os, fnmatch, time
import smtplib
from trac.core import *
from trac.env import Environment
from trac.ticket.model import Ticket
from elementtree import ElementTree
import logging
import datetime
import urllib
import urllib2
import os.path
from time import gmtime, strftime
from operator import itemgetter
from htmlEmailer import *
import glob

from genshi.template import TemplateLoader

# globals - maintain connection to Trac environments

tracShotsEnv = None
tracRendersEnv = None

def loadConfig():
	'''Set globals and load config values from external XML file'''
	global tracShotsEnv, tracRendersEnv
	
	result = {}
	logging.basicConfig(level=logging.DEBUG,
	                    format='%(asctime)s %(levelname)s %(message)s',
	                    filename='./render_monitor.log',
	                    filemode='w')
	# define a Handler which writes INFO messages or higher to the sys.stderr
	console = logging.StreamHandler()
	console.setLevel(logging.DEBUG)
	# set a format which is simpler for console use
	formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
	# tell the handler to use this format
	console.setFormatter(formatter)
	# add the handler to the root logger
	logging.getLogger('').addHandler(console)
	config = os.environ.get("MODFILMS_CONFIG")
	try:
		root = ElementTree.parse(config)
	except (OSError,IOError), e:
		print "Config error: " + e
		print "Check MODFILMS_CONFIG environment variable is set"
	for i in root.getiterator():
		if i.tag =='config':
			pass
		else:
			result.update({i.tag:i.text})
#	logging.info("Config loaded:",result)
	try:
		tracShotsEnv = Environment(result['tracShotsEnv'])
	except:
		print "Config error: trac environment not specified: " + result['tracShotsEnv']
	if result['tracShotsEnv'] != result['tracRendersEnv'] :
		try:
			tracRendersEnv = Environment(result['tracRendersEnv'])
		except:
			print "Config error: trac environment not specified: " + result['tracRendersEnv']
	else:
		tracRendersEnv = tracShotsEnv
	result['patternsIgnore'] = []
	regexIgnore = eval(result['regexIgnore'])
	for patt in regexIgnore:
#		print patt
		result['patternsIgnore'].append(re.compile(patt))
		
	result['disciplineNames'] = eval(result['disciplines'])

	# TODO use /usr/bin/env instead
	if (os.path.exists('/usr/local/bin/gm') == True):
		result['gm'] = '/usr/local/bin/gm'
	elif (os.path.exists('/usr/bin/gm') == True):
			result['gm'] = '/usr/bin/gm'
	else:
		result['gm'] == None
		
	return result
		
def error_alert(config, summary, owner, msg):
	env = tracShotsEnv
	db = env.get_db_cnx()
	cursor = db.cursor()
	email = config['emailfrom']	
	addressList = []
	RECIPIENTS = []
	if owner == 'artist':
		RECIPIENTS = eval(config['adminUser'])
	else:
		RECIPIENTS.append(owner)
	SENDER = email
	sql = "SELECT time from errors where path = '%s'" % (config['path'])
#	print sql
	cursor.execute(sql)
	db.commit()
	loggedAlready = False
	for row in cursor:
		timeStamp = row[0]
#		print "logged error for " + config['path'] + " at " + str(timeStamp)
		loggedAlready = True
#	print loggedAlready
	if loggedAlready == False:
		for name in RECIPIENTS:
			if name.find('@') == -1:
				# loop over owner string or array
				sql = "SELECT value from session_attribute where sid = '%s' and name = 'email'" % name
				print sql
				cursor.execute(sql)
				db.commit()
				for row in cursor:
					addressList.append(row[0])
			else:
				addressList.append(name)
		RECIPIENT = addressList
		logging.info("email_alert: " + str(RECIPIENT))
		subject = 'From: ' + SENDER + "\nSubject: ERROR: invalid upload (" + summary + ")"
		msg = """
	The system has rejected your file - %s - as an invalid upload for the following reason:

	%s

	--------------------------------------------------------------------------

	Please rename your uploaded file using the Naming Conventions for your show.

	If you do not understand this message or believe you have received it in error, please reply to this message.
	""" % (summary,msg)
		try:
			# TODO only need to do this once per list of addresses
			session = smtplib.SMTP(config['smtpserver'])		
			smtpresult = session.sendmail(SENDER, RECIPIENT, "%s\n\n%s" % (subject, msg) )
			if smtpresult:
				errstr = ""
				for recip in smtpresult.keys():
					errstr = """Could not delivery mail to: %s

			Server said: %s
			%s

			%s""" % (recip, smtpresult[recip][0], smtpresult[recip][1], errstr)
				raise smtplib.SMTPException, errstr
		except:
			logging.error("cant send mail")
		sql = "INSERT INTO errors VALUES ('%s',%d)" % (config['path'],time.time() )
		print sql
		cursor.execute(sql)
		db.commit()		
	else:
		logging.debug("skip error email, already logged")
		pass
def email_alert(config, summary, recipient):
	"Send email alert"
	env = tracShotsEnv
	db = env.get_db_cnx()
	cursor = db.cursor()
	SENDER = config['emailfrom']	
	ftpUser = config['ftpUser']
	ftpPassword = config['ftpPassword']
	ftpServer = config['ftpServer']
	httpServer = config['httpServer']
	adminUser = eval(config['adminUser'])
	addressList = []
	for name in adminUser:
		if name.find('@') == -1:
			# loop over owner string or array
			sql = "SELECT value from session_attribute where sid = '%s' and name = 'email'" % name
			cursor.execute(sql)
			db.commit()
			for row in cursor:
				addressList.append(row[0])
		else:
			addressList.append(name)
	RECIPIENT = addressList
	logging.info("email_alert: " + str(RECIPIENT))
	subject = "NEW SHOT "+ summary
	#print subject
	ftpUrl = "ftp://%s:%s@%s%s" % (ftpUser,ftpPassword,ftpServer,summary)
	pageURL = "http://%s:%s@%s/plates" % (ftpUser,ftpPassword,httpServer)
	videoUrl = "http://%s:%s@%s/ftp%s/%s" % (ftpUser,ftpPassword,httpServer,summary,config['videoFilename'])
	thumbnailUrl = "http://%s:%s@%s/ftp%s/.tmp.x.000001.jpg" % (ftpUser,ftpPassword,httpServer,summary)
	htmlMsg = '''
<html>
<head>
<link rel="stylesheet" href="http://modfilms.com/js/themes/flora/flora.all.css" type="text/css" media="screen" title="Flora (Default)" />
<link rel="stylesheet" href="http://modfilms.com/js/demos/css/style.css" type="text/css" />
</head>
<body>
<p>This is an automated email alert from <a href="%s">%s</a></p>

<p>NEW SHOT %s</p>

<p><a href="%s"><img border="0" src="%s" width="720" alt="Preview of %s" /></a></p>

<p>The image sequence for %s can be downloaded here:</p>
<p><a href="%s">%s</a></p>
<p>Email <a href="mailto:reception@modfilms.net">reception@modfilms.net</a> if you need assistance</p>
<p><a href="http://modfilms.net"><img border="0" src="http://modfilms.com/images/poweredby.gif" alt="Powered by"></p>
</body>
</html>
''' % (pageURL, pageURL, summary, videoUrl,thumbnailUrl, summary, summary,ftpUrl,ftpUrl)
	textMsg = """
This is an automated email alert from %s

Image sequence %s is available for download here:

%s

Quicktime video preview

%s

Thumbnail image preview

%s

Powered by http://modfilms.net | Contact us at reception@modfilms.net

""" % (pageURL, summary,ftpUrl, videoUrl,thumbnailUrl)
	try:
		session = smtplib.SMTP(config['smtpserver'])
	#	theMsg = createhtmlmail(htmlMsg, textMsg, subject)
		theMsg = createtextmail(textMsg,subject)
		#print "SENDER: " + SENDER
		#print "RECIPIENT: " + str(RECIPIENT)
		#print "theMsg: " + theMsg
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
	except:
		logging.error("email connection failed")
	
	
def new_ticket(env,summary, owner, discipline):
	"""
	Create a new trac ticket
			"""
				
	# Create a new ticket:
	tkt = Ticket(env)
	tkt['summary'] = summary
	tkt['reporter'] = 'modfilms.net'
	if (owner != 'artist'): #hack should be in config, default owner
		tkt['owner'] = owner
	tkt['type'] = 'render'
	tkt['component'] = discipline
	tkt['description'] = ''
	success = tkt.insert()
	if success > 0:
		return True
	else:
		return False

def update_ticket(env,summary, owner, ticket):
	"""
	Update trac ticket if appropriate
			"""

	tkt = Ticket(env, ticket)
	val = tkt.save_changes(comment='shot preview updated',author="modfilms.net")
	#print "Success updating ticket #", ticket
	return val

def update_trac(config, env,shot, user, timestamp, discipline,uploadType):
	# determine trac ticket for each shot
	success = False
	db = env.get_db_cnx()
	cursor = db.cursor()
	ticket = '#'
	sql = "SELECT id from ticket where summary = '%s'" % shot
	print sql
	cursor.execute(sql)
	db.commit()
	for row in cursor:
	        ticket = row[0]
	if ticket == '#':
		print "No existing ticket, trac will create one"
		subject = "Subject: %s" % (shot)
		msg = "owner=%s" % user # this goes in Description field
		ticket = ''
		success = new_ticket(env,shot, user, discipline)
	else:
		# existing ticket
		if uploadType =='shotPreview':
			success = update_ticket(env,shot,user, ticket)
		else:	# not allow to upload replacement render, update version, hack but quietly allow anyhow
			msg = "can't update a published render - new version required"
			print msg
			error_alert(config, shot,user,msg)
			success = False
	print "update_trac status: " + str(success)
	db.close()
	return success

	
def all_files(root, patterns='*', single_level=False, yield_folders=False):
	# Expand patterns from semicolon-searated string to list
	patterns = patterns.split(';')
	for path, subdirs, files in os.walk(root):
		if yield_folders:
			files.extend(subdirs)
		files.sort()
		for name in files:
			for pattern in patterns:
				if fnmatch.fnmatch(name, pattern):
#					print name
					yield os.path.join(path, name)
					break
		if single_level:
			break
			
def videoToThumbnail(config):
	width = config['proxyWidth']
	height = int(config['proxyHeight'])
	if height % 2 == 1:
		height = height + 1 # ffmpeg needs divisible by two
	size = "%sx%s" % (width,height)
	# why doesn't other values than first frame work?? probs with -ss 00:00:01
	cmd = "/usr/local/bin/ffmpeg -y -i %s -vframes 1 -s %s -an -f mjpeg %s" % (config['path'],size,config['thumbnailPath'])
	logging.debug(cmd)
	try:
		result = os.system(cmd)
	except (OSError,IOError), s:
		logging.error(s)
		return False
	return True

def seqToThumbnail(config):
	height = int(config['proxyHeight'])
	precision = 6 # padding - hack - add to config if prob 
	frameRate = config['frameRate']
#	if height % 2 == 1:
#		height = height + 1 # ffmpeg needs divisible by two
#	size = "%sx%s" % (config['proxyWidth'],height)
	# why doesn't other values than first frame work?? probs with -ss 00:00:01
	id, file = os.path.split(config['path'])
	rectWidth = 25 * len(file)
	cmd = "%s convert -quality 100 -font Arial.ttf -fill white -draw \"rectangle 0,0,%d,60\" -fill black -draw 'text 0,50 \"%%f\"' -pointsize 44  %s -resize %s %s" % (config['gm'], rectWidth,config['path'], config['proxyWidth'],config['thumbnailPath'])
	logging.debug(cmd)
	try:
		result = os.system(cmd)
	except s:
		logging.error(s)
	try:
		os.chmod(config['thumbnailPath'],0664)
	except (OSError,IOError), s:
		logging.error(s)
			
def imgseqToVideo(config):
	width = config['proxyWidth']
	height = int(config['proxyHeight'])
	precision = 6 # padding - hack - add to config if prob 
	frameRate = config['frameRate']
	padbottom = 0 # if height not divisible by two then add this
#	print "TEST: %s %% = %s" % (height, str(height % 2) )
	if height % 2 == 1:
		height = height + 1 # ffmpeg needs divisible by two
		padbottom = 2
	size = "%sx%s" % (width,height)
	# why doesn't other values than first frame work?? probs with -ss 00:00:01

	fnames = sorted(os.listdir(config['path']))
	# remove current ffmpeg frames
	#print fnames
	newfnames = []
	path = ''
	for index,fname in enumerate(fnames):
#		print "%d:%s" % (index, fname)
		if fname[:7] == '.tmp.x.':
			try:
				path = '%s/%s' % (config['path'],fname)
#				print "Found old tmp %s, deleting..." % path
				os.remove(path)	
			except (OSError,IOError), s:
				logging.error("Error deleting tmp files: %s" % s)
		else:
			newfnames.append(fname)
	# rename img sequence for ffmpeg= !!
	c = 1
	#print newfnames
	for fname in newfnames:
		if fname[-4:] == '.jpg' and fname[-13:] != 'thumbnail.jpg':
			new = '%s/.tmp.x.%06d.jpg' % (config['path'],c)
			old = '%s/%s' % (config['path'],fname)
			shutil.copyfile(old,new)
			try:
				os.chmod(new,0664)
			except (OSError,IOError), s:
				logging.error(s)
			#print 'renaming',fname,'to',new
			c = int(c + 1)
	
	# transcode video
	files = "%s/.tmp.x.%%0%dd.jpg" % (config['path'], precision) 	
	video = config['videoPath'] 
	cmd = "/usr/local/bin/ffmpeg -r %s -i %s -sameq -padbottom %s %s" % (frameRate,files, padbottom, video)
	print cmd
	try:
		result = os.system(cmd)
	except (OSError,IOError), s:
		logging.error(s)
		return False
		
	# transcode thumbnail
	thumbnail_width = 198
	oldthumbnail = config['thumbnailPath']
	id,file = os.path.split(config['thumbnailPath'])
	config['thumbnailPath'] = id + "/.tmp.thumbnail.jpg"
	cmd = "%s convert -resize %s %s %s" % (config['gm'],thumbnail_width, oldthumbnail, config['thumbnailPath'])
	print cmd
	try:
		result = os.system(cmd)
	except s:
		print s
	try:
		os.chmod(config['thumbnailPath'],0664)
	except (OSError,IOError), s:
		print s
	
	return True




	return True


def cleanUp(path):
	try:
		os.remove(path)
	except (OSError,IOError), s:
		print "Error:",s
		
def generateHTML(config,jobs,sortedjobs):
	loader = TemplateLoader(
	    os.path.join(os.path.dirname(__file__), '../templates'),
	    auto_reload=True
	)
	tmpl = loader.load('plates.html')
	# generate XHTML
	try:
		output = config['platesHTML']
		out = open(output,'w')
	except (OSError,IOError), s:
		print "Error: can't open %s : %s" % (output, s)
	saved = sys.stdout 
	sys.stdout = out
	print tmpl.generate(project=config['project'],job=job, sortedjobs=sortedjobs).render('html', doctype='html')
	sys.stdout = saved
	out.close
	
def publishVideo(config,filename,path, uploadType,rendertype,userlabel,env,user,lastmod,discipline,thumbnailPath,shot,renderPath):
	logging.debug("generating thumbnail from video %s" % filename)
	config['path'] = path
	config['thumbnailPath'] = thumbnailPath
	config['uploadType'] = uploadType				
	if rendertype != 'preview':
		shot = "%s_%s_%s" % (shot, rendertype, userlabel)
		# if file labelled with a username, use that rather than FTP username
		user = userlabel
		name = filename[:-4]
	else:
		name = filename[:-9]

	print "update_trac(%s,%s,%s,%s,%s,%s,%s)" % (config,env,name, user, lastmod, discipline,uploadType)
	success = update_trac(config,env,name, user, lastmod, discipline,uploadType)

	# create thumb then move render to publish dir. delete local copy

	if (success == True):
		logging.debug("creating thumbnail")
		videoToThumbnail(config)
		logging.debug("publishing %s to %s" % (filename, renderPath))
		shutil.copyfile(path,renderPath)
	cleanUp(path)		

def getLastModifiedFromFile(path):
	return gmtime(os.stat(path)[8])

def getDateFromPath(path):
	pDateId = re.compile('.*/(\d\d\d\d\d\d)/')
	pDateIdEnd = re.compile('.*/(\d\d\d\d\d\d)$')
	id,file = os.path.split(path)
	# test if date in id string TODO - reduce to one regex
	if pDateId.match(id):
		p = pDateId.match(id)
		idDate = p.group(1)
#		print "Dated " + idDate + " according to naming convention "  # TODO move to config
		# store date as seconds otherwise sorted wrongly as string
		year = 2000 + int(idDate[4:6])
		month = int(idDate[2:4])
		day = int(idDate[:2])
		date = datetime.datetime(year,month,day).timetuple()
	elif pDateIdEnd.match(id):
		p = pDateIdEnd.match(id)
		idDate = p.group(1)
#		print "Dated " + idDate + " according to naming convention"
		year = 2000 + int(idDate[4:6])
		month = int(idDate[2:4])
		day = int(idDate[:2])
		date = datetime.datetime(year,month,day).timetuple()
	else:
		pass
#		logging.debug("Job " + id + " doesn't have a date string")
		return None
#	logging.debug("pulled %s from %s" % (date,id))
	return date

def getSeqFromPath(path):
	pDateId = re.compile('.*/(\d\d\d\d\d\d)/\d\d\d/')
	pDateIdEnd = re.compile('.*/(\d\d\d\d\d\d)$')
	id,file = os.path.split(path)
	# test if date in id string TODO - reduce to one regex
	if pDateId.match(id):
		p = pDateId.match(id)
		idDate = p.group(1)
		print "Dated " + idDate + " according to naming convention "  # TODO move to config
		# store date as seconds otherwise sorted wrongly as string
		year = 2000 + int(idDate[4:6])
		month = int(idDate[2:4])
		day = int(idDate[:2])
		date = datetime.datetime(year,month,day).timetuple()
	elif pDateIdEnd.match(id):
		p = pDateIdEnd.match(id)
		idDate = p.group(1)
		print "Dated " + idDate + " according to naming convention"
		year = 2000 + int(idDate[4:6])
		month = int(idDate[2:4])
		day = int(idDate[:2])
		date = datetime.datetime(year,month,day).timetuple()
	else:
		pass
		logging.warning("Job " + id + " doesn't have a date string")
		return None
	logging.info("pulled %s from %s" % (date,id))
	return date
		

def handleArchives(config):
	id = config['id']
#	logging.info('checking if archive:' + id)
	global job
	for format in ('tif','dpx','tga'):    # TODO move to config
		pattern = id + '/*.' + format
		list = glob.glob(pattern)
		if len(list) > 0:
#			logging.info('there is at least one file matching %r so not archived'%pattern)
			return
	logging.debug('no frames found, assuming archive'+ id)
	job[id] = {}
	job[id]['files']  = []
	for path in all_files(id, '.tmp.*.jpg'):
		id,file = os.path.split(path)
		if file[:6] != '.tmp.x' and file[:6] != '.tmp.t':
			job[id]['files'].append(file[5:])
#			logging.debug('adding %s to files list' % file[5:])
	job[id]['lastmodified'] = getLastModifiedFromFile(config['path'])
	job[id]['user'] = config['adminUser']
	job[id]['errorlog'] = []
	job[id]['date'] = getDateFromPath(config['path'])
	return
		
def main():
	"""TODO - move config up
	"""
	config = loadConfig()
	
	global job
	DEBUG = config['debug']
	dropbox = config['ftpdropbox']
	config['videoFilename'] = 'preview.mov'
	ftpFoldersWhiteList = eval(config['ftpFoldersWhiteList'])
	ftpFoldersBlackList = eval(config['ftpFoldersBlackList'])
	regexIgnore = eval(config['regexIgnore'])
		
	while True:
		job = {}
		
		for path in all_files(dropbox, '*'):
			try:
				st = os.stat(path)
			except (OSError,IOError), s:
				print "%s: probably deleted file %s ... check..." % (s, path)
			#print "file st:" + str(st[8])
			lastmod = time.ctime(st[stat.ST_CTIME])
			try:
			    import pwd # not available on all platforms
			    userinfo = pwd.getpwuid(st[stat.ST_UID])
			except (ImportError, KeyError):
			    print "failed to get the owner name for", file
			else:
			    user = userinfo[0]
			
			config['path'] = path
			id,file = os.path.split(path) # split into job id (file path to directory) and filename 
			config['id'] = id
			bits = path.split('/') 
			filename = bits[-1]

			# only monitor these directories
			validFolder = False
			for s in ftpFoldersWhiteList:
				patt = re.compile(s)
				if patt.search(path):
					validFolder = True
					break
			else:
#				print "skipping: " + path
				continue

			# skip these directories
			invalidFolder = False
			for s in ftpFoldersBlackList:
				patt = re.compile(s)
				if patt.search(path):
					invalidFolder = True
#					print "skipping: " + path
					continue		
			
			# ignore these filename patterns - e.g. proftpd temp files - still uploading and proxies - see config
			ignoreThis = False
			for s in regexIgnore:
				patt = re.compile(s)
				if patt.match(filename):
#					print "ignoring %s as per config..." % filename
					ignoreThis = True
			if ignoreThis:
				continue
		
			# handle archived shots - dpx files removed to save space, leaving jpgs and mov
			if filename == config['videoFilename']:
				handleArchives(config)
				continue
				
				
			# flag any files starting with whitespace
			
			if filename[0] == ' ':
				msg = path + " starts with whitespace!"
				error_alert(config, shot,user,msg)
				continue
				
			discipline = ''
		
			pSimplePreview = re.compile('^(\w\w)_(\d+_?\w?)_h264.mov$')
			# <seq_>_<shot>_<type>_<login>.mov
			pSimpleRender = re.compile('^(\w\w)_(\d+_?\w?)_(\w+)_([A-Za-z_-]+).mov$')
			# <seq>_<shot>_<type>_<discipline>_<optionaldescription>_<login>_<version>.mov
			pPro = re.compile('^(\w\w)_(\d+_?\w?)_([EOI])_(\w+)_?(\w*?)_(\w+?)_v(\d\d\d).mov$')
			# <prefix>(\d\d\d\d).dpx
			# 
			#ftp/ARN/filmgate/inbound/050308/092/HHN_386_010/2048x1156/xxxxxxx.dpx
			#ftp/ARN(film title)/filmgate(FX house)/inbound(FTP
			#folder)/050308(date)/092(reel number)/HHN_386_010(Shot
			#name)/2048x1156(res)/xxxxxxx.dpx(frame number)
		
			pDpx = re.compile('^(.*)(\d+).dpx$')
			pDpxTemp = re.compile("^.in.(.*)(\d+).dpx.$")
			pTga = re.compile('^(.*)(\d+).tga$')
			pTgaTemp = re.compile("^.in.(.*)(\d+).tga.$")
			pTif = re.compile('^(.*)(\d+).tif$')
			pTifTemp = re.compile("^.in.(.*)(\d+).tif.$")
			
			# default environment 
			env = tracRendersEnv

			if pPro.match(filename):
#				print "got here!"
				# check syntax for render - <shot>_<rendertype>_<login>.mov where shot is cr_17_c , rendertype has no spaces, login can contain _ or -
				p = pPro.match(filename)
				sequence = p.group(1)
				shotsuffix = p.group(2)
				rendertype = p.group(3)
				uploadType = 'proRender'
				discipline = p.group(4)
				description = p.group(5)
				userlabel = p.group(6)
				version = p.group(7)
				shot = "%s_%s" % (sequence,shotsuffix)	
				for d in config['disciplineNames']:
					# does discipline start with a known phrase? rest of it would be optional description
					if discipline.find(d) == 0:
						print "matched " + d + " discipline"
						description = discipline[len(d):]
						discipline = d
						break
				else:
					msg = discipline + " didn't match any known disciplines"
					print msg
					print "seq '%s', shot '%s' - render type '%s' - discipline '%s' - description '%s' - user '%s' - version '%s'" % (sequence, shot, rendertype, discipline, description, userlabel, version)
					error_alert(config, filename,user,msg)
#					cleanUp(path)
					continue
			
				# TODO for each displines sequence item , parse discipline field and if it starts with that, shave off ending into description field
			
				logging.info("matched pro syntax for renders db")
				print "seq '%s', shot '%s' - render type '%s' - discipline '%s' - description '%s' - user '%s' - version '%s'" % (sequence, shot, rendertype, discipline, description, userlabel, version)
			elif pSimplePreview.match(filename):
				# check syntax for shot - <shot>_h264.mov where shot is cr_17_c
				p = pSimplePreview.match(filename)
				sequence = p.group(1)
				shotsuffix = p.group(2)
				shot = "%s_%s" % (sequence,shotsuffix)
				rendertype = 'preview'
				uploadType = 'shotPreview'
				logging.info("matched simplePreview (shot) syntax for shots db")
				env = tracShotsEnv	# exception for handling shot preview updates
				print "seq '%s', shot '%s' - render type '%s' - user '%s'" % (sequence, shot, rendertype, user)	
			elif pSimpleRender.match(filename):
				# check syntax for render - <shot>_<rendertype>_<login>.mov where shot is cr_17_c , rendertype has no spaces, login can contain _ or -
				p = pSimpleRender.match(filename)
				sequence = p.group(1)
				shotsuffix = p.group(2)
				rendertype = p.group(3)
				uploadtype = "simpleRender"
				userlabel = p.group(4)
				shot = "%s_%s" % (sequence,shotsuffix)
				for d in DISCIPLINES:
					pDiscipline = re.compile('^' + d + '_(\w+)$')
					if pDiscipline.match(rendertype):
						print "matched " + d + " discipline"
						break
				else:
					msg = "%s not valid filename, skipping..." % filename
					print msg + " , user is " + user	
					error_alert(config, filename,user, msg)
#					cleanUp(path)
					continue
				logging.info("matched simple render syntax")
				print "seq '%s', shot '%s' - render type '%s' - user '%s'" % (sequence, shot, rendertype, userlabel)
			elif pDpx.match(filename):
				p = pDpx.match(filename)
				prefix = p.group(1)
				frame = p.group(2)
				uploadType ="dpxSequence"
				format = "dpx"
				sequence = ''
				rendertype = ''
				shot = ''
				userlabel = ''
#				print "matched DPX image sequence syntax"
			elif pTga.match(filename):
				p = pTga.match(filename)
				prefix = p.group(1)
				frame = p.group(2)
				uploadType ="tgaSequence"
				format = 'tga'
				sequence = ''
				rendertype = ''
				shot = ''
				userlabel = ''
#				print "matched TGA image sequence syntax"
			elif pTif.match(filename):
				p = pTif.match(filename)
				prefix = p.group(1)
				frame = p.group(2)
				uploadType ="tifSequence"
				format = 'tif'
				sequence = ''
				rendertype = ''
				shot = ''
				userlabel = ''
#				print "matched TIF image sequence syntax"
			else:
				msg = "%s not valid filename, skipping..." % filename
				#print msg
				error_alert(config, filename,user,msg)
#				cleanUp(path)
				continue
		
			if rendertype == 'preview':
				# keep files compatible with existing convention
				renderPath = "%s/%s_h264.mov" % (config['publishPrefix'], shot) 
				thumbnailPath = "%s/%s.jpg" % (config['publishPrefix'], shot) 
				renderUrl = "%s/%s_h264.mov" % (config['urlPrefix'],shot)
				thumbnailUrl = "%s/%s.jpg" % (config['urlPrefix'], shot)
				userlabel = '' # hack 
			else: 	
				renderPath = "%s/%s" % (config['publishPrefix'], filename) 
				thumbnailPath = "%s/%s.jpg" % (config['publishPrefix'], filename[:-4]) 
				renderUrl = "%s/%s" % (config['urlPrefix'], filename)
				thumbnailUrl = "%s/%s.jpg" % (config['urlPrefix'], filename[:-4])			

		
			if (uploadType != 'dpxSequence' and uploadType !='tgaSequence' and uploadType !='tifSequence'):
				publishVideo(config,filename,path,uploadType,rendertype,userlabel,env,user,lastmod,discipline, thumbnailPath,shot,renderPath)
			else:
#				print "Sequence handler - convert frame and add img sequence to job queue for latest video conversion"
				user = config['adminUser']  #
				id,file = os.path.split(path) # split into job id (file path to directory) and filename
				if job.has_key(id):
					if job[id].has_key('files'):
						job[id]['files'].append(file)
					else:
						job[id]['files'] = [file]
				else:
					job[id] = {}
					job[id]['files']  = [file]
					job[id]['user'] = user
					job[id]['errorlog'] = []
					
				# keep track of last modified timestamps and parent folder name for sorting
				fileState = gmtime(st[8])
				if uploadType[3:] == 'Sequence':	# only sequences count
					job[id]['date'] = getDateFromPath(id)
#					print "comparing lastmodified: " + str(job[id]['lastmodified']) + " to this file's st " + str(fileState) 
					if job[id].has_key('lastmodified'):
						if job[id]['lastmodified'] < fileState:
#							print '%s is most recent modification in %s ' % (strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime(st[8])),job[id])
							job[id]['lastmodified'] = fileState
					else:
#						print "first file in job, setting lastmodified"
						job[id]['lastmodified'] = fileState
				config['path'] = path
				config['thumbnailPath'] = "%s/.tmp.%s.jpg" % (id,file[:-4])
				config['videoPath'] = "%s/%s" % (id,config['videoFilename'])
				# to do  - test if thumb is valid
#				if (os.path.exists(config['videoPath']) == False):
#					#print config['videoPath'], " doesn't exist"
				if (os.path.exists(config['thumbnailPath']) == False):
					d = config['thumbnailPath'] + " doesn't exist"
					logging.debug(d)
					logging.debug("generating proxy for %s" % filename)
					seqToThumbnail(config)

		# end of processing all files in FTP				
		# now process img sequences as .tmp.<file.jpg>
		
		try:
			output = config['platesXML']
			out = open(output,'w')
		except (OSError,IOError), s:
			logging.error("Can't open %s : %s" % (output, s))
		out.write("<?xml version='1.0' encoding='utf-8'?>\n<?xml-stylesheet type='text/xsl' href='plates.xsl'?>\n")
		out.write("<plates>\n")
		out.write("<project>%s</project>\n" % config['project'])
		sorttemp = {}
		# what sort key?
		sortBy = 'lastmodification'
		for id in job.keys():
			if job[id].has_key('date'):
				sortBy = 'idDate'
				break
		logging.debug("sorting shots by " + sortBy)
		for id in job.keys():
			if sortBy == 'idDate':
				logging.debug("Using date as default sort key")
				if not job[id].has_key('date'): 
					job[id]['date'] = job[id]['lastmodified']
				sorttemp[id] = job[id]['date']
			else:
				logging.debug("No date, using lastmodified")
				sorttemp[id] = job[id]['lastmodified']
			job[id]['sortByValue'] = sorttemp[id]
			logging.debug("%s: %s" % (id, job[id]['sortByValue']))
		sortedjobs = sorted(sorttemp.iteritems(), key=itemgetter(1), reverse = True)
#		print sortedjobs
#		logging.debug("----- JOBS ------ %s ------" % strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime()))
		for item in sortedjobs:
			id = item[0]
			config['path'] = id
			config['videoPath'] = "%s/%s" % (id,config['videoFilename'])
			config['thumbnailPath'] = "%s/.tmp.x.000001.jpg" % (id)
			lastModified = job[id]['lastmodified']
#			print lastModified
			files = sorted(job[id]['files'])
#			for index,f in enumerate(files):
#				logging.info("%d) %s" % (index+1,f))
			pFrameNum = re.compile('(\d+).\w\w\w$')
			if id == 'ARN/filmgate/outbound/200508/arn2_HHN_030_cmp_v007_hb/2048x1556':
				print pFrameNum
			if len(files) > 0:
				if pFrameNum.search(files[0]):
					p = pFrameNum.search(files[0])
					start = int(p.group(1))
				if pFrameNum.search(files[-1]):
					p = pFrameNum.search(files[-1])
					end = int(p.group(1))
			else:
				start = 0
				end = 0
			jobCheckDiff = int(end) - int(start) + 1
			jobLength = len(job[id]['files'])
#			logging.info("JOB: %s\n\t%d files (%s - %s) dated %s" % (id, jobLength, start,end, job[id]['sortByValue']))
			trim = len(config['ftpdropbox'])
			summary = id[trim:]
			out.write("<job>\n<id>%s</id>\n" % summary)
			thisFolder = ''
			ftpFolders = eval(config['ftpFoldersDisplay'])
			for folder in ftpFolders:
#				print "checking folder " + folder + " , length = " + str(len(folder)) + " against " + summary[:len(folder)]
				if summary[:len(folder)] == folder:
#					print summary + " is in folder " + folder
					thisFolder = folder
					break
			out.write("<folder>%s</folder>\n" % thisFolder)
			out.write("<framesLength>%s</framesLength>\n" %  jobLength)
			out.write("<startFrame>%s</startFrame>\n" %  start)
			out.write("<endFrame>%s</endFrame>\n" %  end)
			ftpUrl = "ftp://%s:%s@%s%s" % (config['ftpUser'],config['ftpPassword'],config['ftpServer'],summary)
#			ftpUrl = "ftp://%s%s" % (config['ftpServer'],summary)
			out.write("<ftpDir>%s</ftpDir>\n" % summary)
			out.write("<ftpURL>%s</ftpURL>\n" % ftpUrl)
			httpUrl = "http://%s/ftp%s" % (config['httpServer'],summary)
			out.write("<httpURL>%s</httpURL>\n" % httpUrl)
			out.write("<lastModified>%s</lastModified>\n" % lastModified)
			# TODO replace with XML via GEnshi print "<job>"
			# transcode to JPEG		
		
			# test: gaps in sequence
		
			if jobCheckDiff != jobLength:
#				logging.info("jobCheckDiff (%s), jobLength (%s) differenct - testing for gaps in sequence between %s and %s: %s" % (jobCheckDiff,jobLength,start,end,id))
				for i in range (start,end):
					file = "%d.%s" % (i,format)
#					logging.info("file (%s), len(%d)" % (file,len(file)))
					lengthFile = len(file)
					foundFile = False
					for f in files:
#						logging.info('comparing %s to %s ' % (f[-lengthFile:],file))
						if f[-lengthFile:] == file:
							foundFile = True
					if not foundFile:
						logging.warning("Missing frame with suffix %s" % file)
						msg = "Missing frame with suffix %s" % file
						job[id]['errorlog'].append(msg)
		
			# test: files still uploading - .in. files in same dir
		
#			logging.info("Testing dir " + id + " to make sure no tmp files b4 transcode")
			completeMarkerFilename = '.tmp.maybecomplete'
			ftpWaitThreshold = 120 # TODO config var - hardcoded to 2 minutes
			completeMarker = "%s/%s" % (id,completeMarkerFilename)
			# check if file upload in progress
			for path in all_files(id, '*'):
				id,file = os.path.split(path) 
#				print file
				if (pDpxTemp.match(file) or pTgaTemp.match(file) or pTifTemp.match(file)):
					logging.info("file upload in progress:" + file + " : " + id)
					job[id]['status'] = 'file upload in progress...'
					if (os.path.exists(completeMarker) == True):
						logging.info("still uploading, remove this")
						cleanUp(completeMarker)
					break
			else: # will crash if there is a subdir inside a job - TODO cope and email warning
				# may be complete, create marker and check again in a bit to be sure... cope with large uploads gracefully
				# if there is a marker older than ftpWaitThreshold = 60secs then delete marker and say job complete 
				if (os.path.exists(completeMarker) == True):
					logging.info('found ' + completeMarker)
					completeSt = os.stat(completeMarker)
					age = completeSt[stat.ST_MTIME]
					if time.time() - age > ftpWaitThreshold:
						logging.info('no new files uploaded in a while, upload looks complete:' + id)
						job[id]['status']  = 'upload complete'
						cleanUp(completeMarker)
					else:
						# if marker less than threshold in age, then skip this round just in case
						logging.info("recent marker - skip this round")
						job[id]['status']  = 'processing upload'
				else:
					# if no marker and no video then create one and skip this round
					logging.debug(config['videoPath'] + ' ' + id + ' ' + str(os.path.exists(config['videoPath']) ) )
					if (os.path.exists(config['videoPath']) == False):
						logging.info("create marker - could be complete: " + id)
						try:
						 	completeFile = open(completeMarker,'w')
						except (OSError,IOError), s:
							logging.error("Error: can't open %s : %s" % (completeMarker, s))
						completeFile.write("\n")
						completeFile.close()
						job[id]['status']  = 'processing upload'
					else:
						logging.debug("upload complete: " + id)
						job[id]['status']  = 'upload complete'
#			print "\t%s" % job[id]['status']
			if job[id]['errorlog'] != []:
				logging.debug("\t%s" % job[id]['errorlog'])
			if job[id]['errorlog'] != []:
				out.write("<errorlog>%s</errorlog>\n" % ','.join(job[id]['errorlog']))
				job[id]['status'] = job[id]['errorlog']
			elif job[id]['status'] == 'upload complete':
				# transcode entire img sequence to video and save thumbnail
				if (os.path.exists(config['videoPath']) == False):
					logging.debug(config['videoPath'] + " doesn't exist")
					imgseqToVideo(config)
					#/tmp/dropbox/

					if (os.path.exists(config['videoPath']) == True):
						email_alert(config, summary, job[id]['user'])
						httpServer = config['httpServer']
						videoUrl = "http://%s/ftp%s/%s" % (httpServer,summary,config['videoFilename'])
						thumbnailUrl = "http://%s/ftp%s/.tmp.thumbnail.jpg" % (httpServer, summary)
						out.write("<videoURL>%s</videoURL>\n" % videoUrl)
						out.write("<thumbnailURL>%s</thumbnailURL>\n" % thumbnailUrl)
				else:
					logging.debug(config['videoPath'] + " exists")
					httpServer = config['httpServer']
					videoUrl = "http://%s/ftp%s/%s" % (httpServer,summary,config['videoFilename'])
					thumbnailUrl = "http://%s/ftp%s/.tmp.thumbnail.jpg" % (httpServer, summary)
					out.write("<videoURL>%s</videoURL>\n" % videoUrl)
					out.write("<thumbnailURL>%s</thumbnailURL>\n" % thumbnailUrl)
			out.write("<status>%s</status>\n" % job[id]['status'])
			out.write("</job>\n")
		out.write("</plates>\n")
		out.close()
		
		# generate XHTML

		generateHTML(config, job, sortedjobs)


#		print "Finished processing DPX"

		time.sleep(30)
#		print "restarting..."
	
				
if __name__ == '__main__':
	try:
		if sys.argv[1] == "-d":
			DEBUG = True
	except:
		pass
	main()


