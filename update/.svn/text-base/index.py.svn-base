#!/usr/bin/env python
# encoding: utf-8
"""
index.py

User Management index

Created by Michela Ledwidge on 2008-01-04.
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

class Page:
	def __init__(self,template, pagetitle=''):
		if pagetitle == '':
			pagetitle = template
		loader = TemplateLoader(
		    os.path.join(os.path.dirname(__file__), 'templates'), auto_reload=True
		)
		tmpl = loader.load(template)
		self.render = tmpl.generate(title=pagetitle).render('html',doctype='html')

def index():
	return Page('index.html','modfilms.net | IAA | User Management').render
	
if __name__ == "__main__":
		sys.exit(index())

