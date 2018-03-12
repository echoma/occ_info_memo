#!/usr/bin/env python3

import logging
import configparser
import pathlib
import urllib.request
import urllib.parse
import datetime
import time
import xml.etree.ElementTree as ET
import collections
import os
import re

def tzSetGMT():
    os.environ['TZ'] = 'GMT'
    time.tzset()
def tzSetEAST():
    os.environ['TZ'] = 'US/Eastern'
    time.tzset()

tzSetGMT()

Memo = collections.namedtuple('Memo', ['number', 'url', 'category', 'created_time', 'created_date', 'ex_eff_date', 'last_modified_time', 'title'])

class UrlMaker:
    @staticmethod
    def makeMemoSearchUrl(category=None, start_date=None, end_date=None, page=1, start=0, limit=50):
        if end_date is None:
            today = datetime.date.today()
            end_date = '{:02d}-{:02d}-{:02d}'.format(today.year, today.month, today.day)
        if start_date is None:
            day = datetime.date(int(end_date[0:4]), int(end_date[5:7]), int(end_date[8:10]))
            day = day - datetime.timedelta(days=30)
            start_date = '{:02d}-{:02d}-{:02d}'.format(day.year, day.month, day.day)
        dc = int(time.time()*1000.0)
        u = ' inmeta:MEMOMETA=true'
        if category is not None:
            u = u + ' inmeta:MEMOCATEGORY='+category
        u = u + ' inmeta:MEMOCREATEDONDAY:'+start_date+'..'+end_date
        return 'https://www.theocc.com/webapps/infomemo-search?orderBy=created_desc&query='+urllib.parse.quote(u)+'&_dc='+str(dc)+'&page='+str(page)+'&start='+str(start)+'&limit='+str(limit)+'&sort='+urllib.parse.quote('[{"property":"created","direction":"DESC"}]')

class Crawl:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.save_dir = config['crawl']['dir']
    def crawl(self, category=None):
        with urllib.request.urlopen(UrlMaker.makeMemoSearchUrl(category)) as f:
            tree = ET.fromstring(f.read().decode('utf-8'))
            for r in tree.find('RES').findall('R'):
                pn = int(r.get('N'))
                memo_number = None
                memo_url = None
                memo_category = None
                memo_created_time = None
                memo_created_date = None
                memo_ex_eff_date = 0
                memo_last_modified_time = None
                memo_title = None
                for child in r:
                    if child.tag=='U':
                        memo_url = child.text
                        if memo_number is None:
                            memo_number = int(memo_url[memo_url.rfind('=')+1:])
                    elif child.tag=='FS':
                        if child.get('NAME')=='MEMONUMBER':
                            memo_number = int(child.get('VALUE'))
                    elif child.tag=='MT':
                        mt_n = child.get('N')
                        mt_v = child.get('V')
                        if mt_n=='MEMOCATEGORY':
                            memo_category = mt_v
                        elif mt_n=='MEMOCREATEDON':
                            memo_created_time = int(time.mktime(time.strptime(mt_v[0:19], '%Y-%m-%d %H:%M:%S')))
                        elif mt_n=='MEMOCREATEDONDAY':
                            memo_created_date = int(mt_v[0:4]+mt_v[5:7]+mt_v[8:10])
                        elif mt_n=='MEMOEXEFFDATE':
                            if re.match('\d{4}\-\d{2}\-\d{2}',mt_v):
                                memo_ex_eff_date = int(mt_v[0:4]+mt_v[5:7]+mt_v[8:10])
                        elif mt_n=='MEMOLASTMODIFIED':
                            tzSetEAST()
                            memo_last_modified_time = int(time.mktime(time.strptime(mt_v[0:19], '%Y-%m-%d %H:%M:%S')))
                            tzSetGMT()
                        elif mt_n=='MEMONUMBER':
                            if memo_number<=0 or memo_number is None:
                                memo_number = int(mt_v)
                        elif mt_n=='MEMOTITLE':
                            memo_title = mt_v.replace('%', '%%')
                memo = Memo(memo_number, memo_url, memo_category, memo_created_time, memo_created_date, memo_ex_eff_date, memo_last_modified_time, memo_title)
                logging.info('{}: {} | {} | {} | {}'.format(pn, memo.number, memo_category, memo_created_date, memo_title))
                self.fetchPdf(memo)
    def fetchPdf(self, memo):
        with urllib.request.urlopen(memo.url) as f:
            if int(f.status)!=200:
                return False
            is_pdf = False
            headers = f.getheaders()
            for header in headers:
                if header[0]=='Content-Type':
                    if header[1].find('application/pdf')>=0:
                        is_pdf = True
            if not is_pdf:
                return False
            self.save(memo, f.read())
    def save(self, memo, pdf_data):
        path = self.save_dir+'/'+str(memo.created_date)+'/'+str(memo.number)+'/'
        p = pathlib.Path(path)
        p.mkdir(parents=True, exist_ok=True)
        with open(path+str(memo.number)+'.pdf', 'w+b') as f:
            f.write(pdf_data)
        config = configparser.ConfigParser()
        config.add_section('memo')
        for k,v in memo._asdict().items():
            config['memo'][k] = str(v)
        with open(path+str(memo.number)+'.ini', 'w+t') as f:
            config.write(f)

def main():
    c = Crawl()
    c.crawl()

logging.basicConfig(level=logging.INFO, format='%(message)s @ %(filename)s:%(lineno)s')
main()