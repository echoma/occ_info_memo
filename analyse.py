#!/usr/bin/env python3

import logging
import configparser
import pathlib
import datetime
import time
import os
import random
import hmac
import hashlib
import binascii
import base64
import requests

def idxOfPngName(s):
    i = s.rfind('-')
    if -1==i:
        return -1
    j = s.rfind('.')
    return s[i+1:j]

class QCouldApi:
    def __init__(self, appId, secId, secKey):
        self._appid = appId
        self._secretid = secId
        self._secretkey = secKey
        self._bucket = 'test'
        self._sign = None
        self._sign_time = 0
    def getSign(self, bucket, howlong=600):
        """ GET REUSABLE SIGN
        :param bucket: 图片处理所使用的 bucket
        :param howlong: 签名的有效时长，单位 秒
        :return: 签名字符串
        """
        if howlong <= 0:
            raise Exception('Param howlong must be great than 0')
        now = int(time.time())
        rdm = random.randint(0, 999999999)
        text = 'a='+self._appid + '&b='+bucket + '&k='+self._secretid + '&e='+str(now+howlong) + '&t='+str(now) + '&r='+str(rdm) + '&u=0&f='
        hexstring = hmac.new(self._secretkey.encode('utf-8'), text.encode('utf-8'), hashlib.sha1).hexdigest()
        binstring = binascii.unhexlify(hexstring)
        return base64.b64encode(binstring+text.encode('utf-8')).rstrip()
    def ocrGeneral(self, img_file_path, output_to_file=None):
        if time.time()-self._sign_time > 300:
            self._sign = self.getSign(self._bucket, 600)
            self._sign_time = time.time()
        img_data = None
        img_data = open(img_file_path, 'rb')
        #with open(img_file_path, mode='rb') as f:
        #    img_data = f.read()
        data = {}
        data['appid'] = self._appid
        data['bucket'] = self._bucket
        data['image'] = ('1.png',img_data)
        headers = {}
        #headers['Host'] = 'service.image.myqcloud.com'
        headers['Authorization'] = self._sign
        headers['User-Agent'] = 'User('+self._appid+')'
        req = requests.post('http://recognition.image.myqcloud.com/ocr/general', files=data, headers=headers, timeout=30)
        if req.status_code==200:
            if output_to_file is not None:
                output_to_file.write(req.text)
            return True
        else:
            logging.info('    '+str(req.status_code)+' '+req.text)
            return False
class Analyse:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.dir = config['crawl']['dir']
        qcloud_ini = config['qcloud']['ini']
        qcloud_sec = config['qcloud']['section']
        config = configparser.ConfigParser()
        config.read(qcloud_ini)
        section = config[qcloud_sec]
        self.qcapi = QCouldApi(section['ProjectId'], section['SecretId'], section['SecretKey'])
    def getRecentModifiedPdfDir(self, seconds):
        ret = []
        for child_dir in pathlib.Path(self.dir).iterdir():
            if self.gmtDateNeedCheck(int(child_dir.name), seconds):
                for pdf_dir in child_dir.iterdir():
                    n = int(pdf_dir.name)
                    cfg = configparser.ConfigParser()
                    cfg.read(str(pdf_dir)+'/'+str(n)+'.ini')
                    if time.time()-int(cfg['memo']['last_modified_time']) < seconds:
                        ret.append(pdf_dir)
        ret.sort()
        return ret
    def gmtDateNeedCheck(self, date, seconds):
        dt = datetime.datetime(year=int(date/10000), month=int((date%10000)/100), day=date%100, hour=23, minute=59, second=59)
        return time.time()-dt.timestamp() < seconds+86400*5
    def makePng(self, pdf_dir):
        n = int(pdf_dir.name)
        pdf_path = str(pdf_dir)+'/'+str(n)+'.pdf'
        png_path = str(pdf_dir)+'/'+str(n)+'.png'
        os.system('rm '+str(pdf_dir)+'/*.png -rf')
        os.system('convert -density 100 -resize 200% -quality 100 -sharpen 0x1.0 '+pdf_path+' '+png_path)
    def anaPngQcloud(self, pdf_dir):
        png_list = []
        for child_path in pathlib.Path(pdf_dir).iterdir():
            if child_path.name.find('.png')>=0:
                png_list.append(child_path.name)
        png_list.sort(key=idxOfPngName)
        for png in png_list:
            logging.info("    {}".format(png))
            with open(str(pdf_dir)+'/'+png+'.qcloud.ocr.json','w+t') as f:
                if not self.qcapi.ocrGeneral(str(pdf_dir)+'/'+png, f):
                    return False
        return True
    def pdf2txt(self, pdf_dir):
        parent = str(pdf_dir)
        name = pathlib.Path(pdf_dir).name
        cmd = './pdf2txt.py -t xml {dir}/{number}.pdf > {dir}/{number}.pdf2txt.xml'.format(dir=parent, number=name)
        os.system(cmd)
        cmd = './pdf2txt.py -t html {dir}/{number}.pdf > {dir}/{number}.pdf2txt.html'.format(dir=parent, number=name)
        os.system(cmd)
def main():
    a = Analyse()
    dir_list = a.getRecentModifiedPdfDir(86400*10)
    logging.info('analysing with pdf2txt')
    for pdf_dir in dir_list:
        name = pathlib.Path(pdf_dir).name
        logging.info('  {}'.format(name))
        a.pdf2txt(pdf_dir)
        time.sleep(1)
    logging.info('analysing with png')
    for pdf_dir in dir_list:
        name = pathlib.Path(pdf_dir).name
        logging.info('  {}, generating png'.format(name))
        a.makePng(pdf_dir)
        logging.info('    analysing with qcloud ocr')
        if not a.anaPngQcloud(pdf_dir):
            break
        time.sleep(1)

logging.basicConfig(level=logging.INFO, format='%(message)s @ %(filename)s:%(lineno)s')
main()