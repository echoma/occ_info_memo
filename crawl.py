#!/usr/bin/env python3

import configparser
import pathlib
import urllib.request
import urllib.parse
import datetime
import time
import xml.etree.ElementTree as ET

class UrlMaker:
    @staticmethod
    def makeMemoSearchUrl(category=None, start_date=None, end_date=None, page=1, start=0, limit=20):
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
                u = None
                n = None
                d = None
                for child in r:
                    if child.tag=='U':
                        u = child.text
                        n = u[u.rfind('=')+1:]
                    if child.tag=='CRAWLDATE':
                        ds = time.strptime(child.text, '%d %b %Y')
                        d = '{:02d}{:02d}{:02d}'.format(ds.tm_year, ds.tm_mon, ds.tm_mday)
                print("\t\t", pn, n, d, u)
                self.fetch(n, u, d)
    def fetch(self, number, url, date):
        with urllib.request.urlopen(url) as f:
            if int(f.status)!=200:
                return False
            is_pdf = False
            last_modified = None
            headers = f.getheaders()
            for header in headers:
                if header[0]=='Content-Type':
                    if header[1].find('application/pdf')>=0:
                        is_pdf = True
                if header[0]=='Last-Modified':
                    last_modified = int(time.mktime(time.strptime(header[1], '%a, %d %b %Y %H:%M:%S %Z')))
            if not is_pdf:
                return False
            self.save(number, date, last_modified, f.read())
    def save(self, number, date, last_modified, data):
        path = self.save_dir+'/'+str(date)+'/'+str(number)+'/'
        p = pathlib.Path(path)
        p.mkdir(parents=True, exist_ok=True)
        with open(path+str(number)+'.pdf', 'w+b') as f:
            f.write(data)
        config = configparser.ConfigParser()
        config.add_section('crawl')
        config['crawl']['last_modified'] = time.strftime('%a, %d %b %Y %H:%M:%S %z', time.gmtime(last_modified))
        with open(path+str(number)+'.ini', 'w+t') as f:
            config.write(f)

def main():
    c = Crawl()
    c.crawl()
main()