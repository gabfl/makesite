#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2018 Sunaina Pai
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


"""Make static website/blog with Python."""


import os
import shutil
import re
import glob
import sys
import json
import datetime

from jinja2 import Template, Environment, FileSystemLoader
from bs4 import BeautifulSoup
import commonmark

from vars import *


def get_environment_name():
    """Set environment name"""
    if __name__ == '__main__':
        # Parse arguments
        try:
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument("-e", "--env", type=str, help="Environment name",
                                choices=['dev', 'prod', 'default'], default='default')
            args = parser.parse_args()

            return args.env
        except ImportError as e:
            print('`argparse` package missing, defaulting to `default` environment.')
            pass

    return 'default'


def import_additional_parser():
    """Import an eventual parser created by the user"""
    # Parse arguments
    try:
        global add_parser
        import add_parser
    except ImportError as e:
        print('No additional parser found.')
        pass


def fread(filename):
    """Read file and close the file."""
    with open(filename, 'r') as f:
        return f.read()


def fwrite(filename, text):
    """Write content to file and close the file."""
    basedir = os.path.dirname(filename)
    if not os.path.isdir(basedir):
        os.makedirs(basedir)

    with open(filename, 'w') as f:
        f.write(text)


def log(msg, *args):
    """Log message with specified arguments."""
    sys.stderr.write(msg.format(*args) + '\n')


def truncate(text, words=25):
    """Remove tags and truncate text to the specified number of words."""
    return ' '.join((text).split()[:words])


def read_content(filename):
    """Read content and metadata from file into a dictionary."""
    # Read file content.
    text = fread(filename)

    # Read metadata and save it in a dictionary.
    date_slug = os.path.basename(filename).split('.')[0]
    match = re.search('^(?:(\\d\\d\\d\\d-\\d\\d-\\d\\d)-)?(.+)$', date_slug)
    content = {
        'date': format_date(match.group(1) or '1970-01-01'),
        'date_ymd': match.group(1) or '1970-01-01',
        'date_rfc_2822': format_date(match.group(1) or '1970-01-01', date_format_override='%a, %d %b %Y %H:%M:%S +0000'),
        'slug': match.group(2),
    }

    # Convert Markdown content to HTML.
    if filename.endswith(('.md', '.mkd', '.mkdn', '.mdown', '.markdown')):
        # Separate text and template variables
        variables, text = separate_content_and_variables(text)

        text = variables + "{% include 'md_header.html' %}" + \
            commonmark.commonmark(text) + "{% include 'md_footer.html' %}"

    # Optional additional parsing
    if 'add_parser' in sys.modules:
        text = add_parser.parse(text, filename)

    # Update the dictionary with content text and summary text.
    content.update({
        'content': text,
    })

    return content


def separate_content_and_variables(text, boundary='{# /variables #}'):
    """Separate variables and content from a Markdown file"""

    # Find boundary
    pos = text.find(boundary)

    # Text contains variables
    if pos > 0:
        return(text[:pos].strip(), text[(pos + len(boundary)):].strip())

    # Text does not contain variables
    return ('', text)


def format_date(date, date_format_override=None):
    """
        Change the date format
    """

    global date_format

    return datetime.datetime.strptime(date, '%Y-%m-%d').strftime(date_format_override or date_format)


def render(html, **params):
    """Use Jinja to render the template"""

    # Load template
    template = Environment(
        loader=FileSystemLoader('layout'),
    ).from_string(html)

    # Return rendered HTML
    return template.render(params)


def make_pages(src, dst, layout, **params):
    """Generate pages from page content."""
    items = []

    for src_path in glob.glob(src):
        context = read_content(src_path)

        params.update(context)

        dst_path = render(dst, **params)
        output = render(context['content'], **params)

        # Add destination path to context
        context['dest_path'] = dst_path

        # Add item to list
        items.append(context)

        log('Rendering {} => {} ...', src_path, dst_path)
        fwrite(dst_path, output)

    return sorted(items, key=lambda x: x['date_ymd'], reverse=True)


def make_list(posts, dst, list_layout, item_layout, limit=None, **params):
    """Generate list page for a blog."""
    items = []
    for k, post in enumerate(posts):
        item_params = dict(params, **post)

        # Get title and summary
        title, summary = get_title_and_summary(item_params['dest_path'])
        item_params['title'] = title
        item_params['summary'] = summary

        item = render(item_layout, **item_params)
        items.append(item)

        # Limit to `limit` items
        if limit is not None and k + 1 >= limit:
            break

    params['content'] = ''.join(items)
    dst_path = render(dst, **params)
    output = render(list_layout, **params)

    log('Rendering list => {} ...', dst_path)
    fwrite(dst_path, output)


def get_title_and_summary(path):
    """Parse post content to retrieve title and a truncated version of the content"""
    soup = BeautifulSoup(fread(path), 'html.parser')
    return (soup.find(id="title").text, truncate(soup.find(id="post").text))


def get_content_path(section, path=None):
    """
        Returns the directory used to store a section sources
        Used to prevent the case where somebody would rename the path for the
        blog section for not rename the `blog` directory in `content/`
    """

    if path and os.path.isdir(path):
        return 'content/' + path
    elif section == 'blog' and os.path.isdir('content/blog'):
        return 'content/blog'
    elif section == 'news' and os.path.isdir('content/news'):
        return 'content/news'

    return 'content/' + path


def main():
    global date_format

    # Get environment name
    env = get_environment_name()

    # Import optional additional parser
    import_additional_parser()

    # Set document root
    documentroot = site_vars['envs'][env]['documentroot']

    # Create a new document root directory from scratch.
    if os.path.isdir(documentroot):
        shutil.rmtree(documentroot)
    shutil.copytree('static', documentroot)

    # Set date format
    date_format = site_vars['date_format']

    # Default parameters.
    params = {
        'base_path': site_vars['envs'][env]['base_path'],
        'subtitle': site_vars['subtitle'],
        'author': site_vars['author'],
        'html_lang': site_vars['html_lang'],
        'site_url': site_vars['envs'][env]['site_url'],
        'current_year': datetime.datetime.now().year,
        # Blog vars
        'blog_path': site_vars['blog']['path'],
        'blog_name': site_vars['blog']['name'],
        # News vars
        'news_path': site_vars['news']['path'],
        'news_name': site_vars['news']['name'],
        # Contact vars
        'contact_path': site_vars['contact']['path'],
        'contact_name': site_vars['contact']['name'],
        # About vars
        'about_path': site_vars['about']['path'],
        'about_name': site_vars['about']['name'],
    }

    # Load layouts.
    list_layout = fread('layout/list.html')
    list_layout_recent = fread('layout/list_recent.html')
    item_layout = fread('layout/item.html')
    item_layout_recent = fread('layout/item_recent.html')
    feed_xml = fread('layout/feed.xml')
    item_xml = fread('layout/item.xml')

    # Create blogs.
    for section in site_vars['sections']:
        log('Rendering section => {} ...', section)

        # Retrieve section dict
        section_vars = site_vars.get(section, {})

        # Set section vats or defaults
        s_path = section_vars.get('path', section)
        s_ext = section_vars.get('files_extension', '.html')
        s_name = section_vars.get('name', section.title())
        s_recent_items = section_vars.get('recent_items', 5)

        # Make pages
        section_pages = make_pages(get_content_path(section, s_path) + '/*' + s_ext,
                                   documentroot + '/' + s_path + '/{{ slug }}/index.html', None, blog=s_path, **params)

        # Section index
        make_list(section_pages, documentroot + '/' + s_path + '/index.html',
                  list_layout, item_layout, None, blog=s_path, title=s_name, **params)

        # Section RSS
        make_list(section_pages, documentroot + '/' + s_path + '/rss.xml',
                  feed_xml, item_xml, None, blog=s_path, title=s_name, **params)

        # Recent items
        make_list(section_pages, documentroot + '/' + s_path + '/recent.html', list_layout_recent,
                  item_layout_recent, s_recent_items, blog=s_path, title=s_name, **params)

        # Add the recent items to the params
        params['recent_' + section] = \
            fread(documentroot + '/' + s_path + '/recent.html')

    # Create site pages.
    make_pages('content/_index.html', documentroot + '/index.html',
               None, **params)
    make_pages('content/[!_]*.html', documentroot + '/{{ slug }}/index.html',
               None, **params)


if __name__ == '__main__':
    main()
