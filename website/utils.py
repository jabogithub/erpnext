# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import os
import conf
import webnotes
from webnotes.utils import cstr

template_map = {
	'Web Page': 'html/web_page.html',
	'Blog': 'html/blog_page.html',
	'Item': 'html/product_page.html',
}

def render(page_name):
	"""render html page"""
	try:
		if page_name:
			html = get_html(page_name)
		else:
			html = get_html('index')
	except Exception, e:
		html = get_html('404')

	from webnotes.handler import eprint, print_zip
	eprint("Content-Type: text/html")
	print_zip(html)

def get_html(page_name):
	"""get page html"""
	page_name = scrub_page_name(page_name)
	comments = get_comments(page_name)
	
	html = ''
	
	# load from cache, if auto cache clear is falsy
	if not (hasattr(conf, 'auto_cache_clear') and conf.auto_cache_clear or 0):
		html = webnotes.cache().get_value("page:" + page_name)
		comments += "\nload status: fresh"

	if not html:
		html = load_into_cache(page_name)
		comments += "\nload status: cache"
	
	# insert comments
	html += """\n<!-- %s -->""" % webnotes.utils.cstr(comments)

	return html

def get_comments(page_name):	
	if page_name == '404':
		comments = """error: %s""" % webnotes.getTraceback()
	else:
		comments = """page: %s""" % page_name
		
	return comments
	
def scrub_page_name(page_name):
	if page_name.endswith('.html'):
		page_name = page_name[:-5]

	return page_name

def page_name(title):
	"""make page name from title"""
	import re
	name = title.lower()
	name = re.sub('[~!@#$%^&*()<>,."\']', '', name)
	return '-'.join(name.split()[:4])

def update_page_name(doc, title):
	"""set page_name and check if it is unique"""
	webnotes.conn.set(doc, "page_name", page_name(title))
	
	res = webnotes.conn.sql("""\
		select count(*) from `tab%s`
		where page_name=%s and name!=%s""" % (doc.doctype, '%s', '%s'),
		(doc.page_name, doc.name))
	if res and res[0][0] > 0:
		webnotes.msgprint("""A %s with the same title already exists.
			Please change the title of %s and save again."""
			% (doc.doctype, doc.name), raise_exception=1)

	delete_page_cache(doc.page_name)

def load_into_cache(page_name):
	args = prepare_args(page_name)
	html = build_html(args)
	webnotes.cache().set_value("page:" + page_name, html)
	return html

def build_html(args):
	from jinja2 import Environment, FileSystemLoader

	templates_path = os.path.join(os.path.dirname(conf.__file__), 
		'app', 'website', 'templates')
	
	jenv = Environment(loader = FileSystemLoader(templates_path))
	html = jenv.get_template(args['template']).render(args)
	
	return html
	
def prepare_args(page_name):
	if page_name == 'index':
		page_name = get_home_page()
	
	if page_name in get_template_pages():
		args = {
			'template': 'pages/%s.html' % page_name,
			'name': page_name,
		}
	else:
		args = get_doc_fields(page_name)
	
	args.update(get_outer_env())
	
	return args	

def get_template_pages():	
	pages_path = os.path.join(os.path.dirname(conf.__file__), 'app', 
		'website', 'templates', 'pages')
	page_list = []
	for page in os.listdir(pages_path):
		page_list.append(scrub_page_name(page))

	return page_list

def get_doc_fields(page_name):
	doc_type, doc_name = get_source_doc(page_name)
	
	obj = webnotes.get_obj(doc_type, doc_name)
	
	if hasattr(obj, 'prepare_template_args'):
		obj.prepare_template_args()
		
	args = obj.doc.fields
	args['template'] = template_map[doc_type]
	
	return args

def get_source_doc(page_name):
	"""get source doc for the given page name"""
	for doctype in [('Web Page', 'published'), ('Blog', 'published'), 
		('Item', 'show_in_website')]:
		name = webnotes.conn.sql("""select name from `tab%s` where 
			page_name=%s and ifnull(`%s`, 0)=1""" % (doctype[0], "%s", doctype[1]), 
			page_name)
		if name:
			return doctype[0], name[0][0]
			
	return None, None
	
def get_outer_env():
	all_top_items = webnotes.conn.sql("""\
		select * from `tabTop Bar Item`
		where parent='Website Settings' and parentfield='top_bar_items'
		order by idx asc""", as_dict=1)
		
	top_items = [d for d in all_top_items if not d['parent_label']]
	
	# attach child items to top bar
	for d in all_top_items:
		if d['parent_label']:
			for t in top_items:
				if t['label']==d['parent_label']:
					if not 'child_items' in t:
						t['child_items'] = []
					t['child_items'].append(d)
					break
	
	return {
		'top_bar_items': top_items,
	
		'footer_items': webnotes.conn.sql("""\
			select * from `tabTop Bar Item`
			where parent='Website Settings' and parentfield='footer_items'
			order by idx asc""", as_dict=1),
			
		'brand': webnotes.conn.get_value('Website Settings', None, 'brand_html') or 'ERPNext',
		'copyright': webnotes.conn.get_value('Website Settings', None, 'copyright'),
		'favicon': webnotes.conn.get_value('Website Settings', None, 'favicon')
	}

def get_home_page():
	doc_name = webnotes.conn.get_value('Website Settings', None, 'home_page')
	if doc_name:
		page_name = webnotes.conn.get_value('Web Page', doc_name, 'page_name')
	else:
		page_name = 'login'

	return page_name
	
def clear_cache(page_name):
	if page_name:
		delete_page_cache(page_name)
	else:
		webnotes.cache().delete_keys("page:")
	
def delete_page_cache(page_name):
	webnotes.cache().delete_value("page:" + page_name)