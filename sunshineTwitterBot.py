#! /usr/bin/ python
"""
modified version of funding bot created by the chicago tribune using source 
code from aepton
@ilcampaigncash
http://blog.apps.chicagotribune.com/2014/01/06/scraping-illinois-campaign-finance-data-for-fun-if-not-profit/
https://github.com/newsapps/ilcampaignfinance
"""

from twitter import *
import sys
import os
import time
import requests
from bs4 import BeautifulSoup
import feedparser
import urlparse

# ISBE Recently-filed reports
ISBE_REPORTS_FEED = 'http://elections.il.gov/rss/SBEReportsFiledWire.aspx'

# Scraper for the Reports Filed list
def scrape_reports_filed(reports_url=ISBE_REPORTS_FEED):
    """
    Reads the reports_filed list and returns list of parsed reports metadata.
    """
    feed = feedparser.parse(reports_url)
    reports_list = []
    for f in feed['entries']:
        indx = f['summary'].index('/')
# new formatting for date search
        report_date = f['summary'][(indx-2):(indx+8)].strip(' ')
# old fomatting for date search
#        report_date = f['summary'].split('<br />')[2].split(' ')[0]     
        if 'href' not in f['links'][0]:
            continue
        report_url = f['links'][0]['href']
        parsed_url = urlparse.parse_qs(urlparse.urlparse(report_url).query)
#        print parsed_url
        if report_url.startswith(
                'http://www.elections.il.gov/CampaignDisclosure/A1'):
            report_type = 'A1'
            report_id = parsed_url['FiledDocID'][0]
        elif report_url.startswith(
                'http://www.elections.il.gov/CampaignDisclosure/B1'):
            report_type = 'B1'
            report_id = parsed_url['FiledDocID'][0]
        elif report_url.startswith(
                'http://www.elections.il.gov/CampaignDisclosure/D2'):
            report_type = 'D2'
            report_id = f['summary'][:(indx-2)].strip(' ')
        elif report_url.startswith(
                'http://www.elections.il.gov/CampaignDisclosure/CDPdfViewer'):
            report_type = 'PDF'
            report_id = f['summary'][:(indx-2)].strip(' ')
        else:
            report_type = 'UNK'  # Unknown/unhandled report type
            report_id = -1
        reports_list.append({
            'report_id': report_id,
            'report_type': report_type,
            'report_url': report_url,
            'report_date': report_date,
            'post_date': f['published_parsed']
        })
#        print reports_list
    return reports_list

def page_index(page_n,report_type):
    """
    Get salted page index
    """
    key = ''
    if report_type.lower() == 'a1':
        typ = 1
    elif report_type.lower() == 'b1':
        typ = 2
    else:
        print 'error in page_index(): unrecognized report_type'
        sys.exit()
    f_loc = os.getcwd()+'/SBEHash.txt'
    with open(f_loc,'r') as hash_file:
        first_line = True
        for line in hash_file.readlines():
            if first_line:
                first_line = False
            else:
                if line.split(',')[0] == str(page_n):
                    key = line.split(',')[typ]
                    break
    return key

# Scraper interfaces for specific report types
def scrape_a1(report_id, report_url, report_date):
    """
    Given a report_id, attempts to download it and scrape it.
    Unlike with D2s, we need the URL and date up front, because they're tougher
    to extract from the body of the A1 report itself.
    """
    req = requests.get(report_url)
    soups = [BeautifulSoup(req.text,"html5lib")]
    rec_counts = soups[0].findAll('span',id='ctl00_ContentPlaceHolder1_lbRecordsInfo')[0]
    rec_counts = soups[0].findAll('span',id='ctl00_ContentPlaceHolder1_lbRecordsInfo')[0]
    if rec_counts.contents==[]:
        a1_list=['empty']
    else:
        n1 = int(rec_counts.contents[0].split(' ')[-3])
        n2 = int(rec_counts.contents[0].split(' ')[-1])
        page_count = n2/n1+(n2%n1>0)
        for page in range(1,page_count+1):
            if page == 1:
                a1_list = _process_a1_page(soups,report_url,report_id,report_date)
            else:
                page_url = '%s&pageindex=%s' % (report_url,page_index(page,'a1'))
                req = requests.get(page_url)
                soups = [BeautifulSoup(req.text,"html5lib")]
                a1 = _process_a1_page(soups,page_url,report_id,report_date)
                a1_list = [a1_list[0],a1_list[1]+a1[1]]
    return a1_list
    
        
# Scraper interfaces for specific report types
def scrape_b1(report_id, report_url, report_date):
    """
    Given a report_id, attempts to download it and scrape it.
    """
    req = requests.get(report_url)
    soups = [BeautifulSoup(req.text,"html5lib")]
    rec_counts = soups[0].findAll('span',id='ctl00_ContentPlaceHolder1_lbRecordsInfo')[0]
#    sys.exit()
    n1 = int(rec_counts.contents[0].split(' ')[-3])
    n2 = int(rec_counts.contents[0].split(' ')[-1])
    page_count = n2/n1+(n2%n1>0)
    for page in range(1,page_count+1):
        if page == 1:
            b1_list = _process_b1_page(soups,report_url,report_id,report_date) 
        else:
            page_url = '%s&pageindex=%s'%(report_url,page_index(page,'b1'))
            req = requests.get(page_url)
            soups = [BeautifulSoup(req.text,"html5lib")]
            b1 = _process_b1_page(soups,page_url,report_id,report_date)
            for b in b1:
                b1_list.append(b)
    return b1_list
        

# Scraper "backends" for specific report types
def _process_a1_page(soups, url, report_id, report_date):
    """
    Does the heavy lifting of actually looking at the report HTML, extracting
    the data we care about and saving it to the db.
    """
    amt = []
    date = []
    cmte_name = ''    
    name = soups[0].findAll('span', id='ctl00_ContentPlaceHolder1_lblName')
    if name[0].contents:
        cmte_name = name[0].contents[0]
    a1_list = []
    for f in soups[0].findAll('td', 'tdA1List'):
        if 'thA1Amount' in f['headers'][0]:
            amt.append(f.findAll('span')[0].contents[0])  
            date.append(f.findAll('span')[0].contents[2])       
    a1_list = [cmte_name,amt]
    return a1_list
        

# Scraper "backends" for specific report types
def _process_b1_page(soups, url, report_id, report_date):
    """
    Does the heavy lifting of actually looking at the report HTML, extracting
    the data we care about and returning
    """
    b1_list = []
    amt = []
    purp = []
    date = []
    supp = []
    cand = []
    off = []
    name = soups[0].findAll('span', id='ctl00_ContentPlaceHolder1_lblName')  
    if name:
        cmte_name = name[0].contents[0]
    for f in soups[0].findAll('td', 'tdB1List'):
        if 'thAmount' in f['headers'][0]:
            amt.append(f.findAll('span')[0].contents[0])  
            date.append(f.findAll('span')[0].contents[2])
        if 'thPurpose' in f['headers'][0]:
            if f.findAll('span')[0].contents == []:
                purp.append('unstated purpose')
            else:
                purp.append(f.findAll('span')[0].contents[0])
        if 'thSuppOpp' in f[('headers')][0]:
            supp.append(f.findAll('span')[0].contents[0])
        if 'thCandidateName' in f[('headers')][0]:
            cand.append(f.findAll('span')[0].contents[0])
        if 'thOffice' in f[('headers')][0]:
            off.append(f.findAll('span')[0].contents[0])
    for i in range(len(soups[0].findAll('td','tdB1ListContributor'))):
        b1_list.append(\
            [cmte_name,amt[i],date[i],purp[i]\
            ,supp[i],cand[i],off[i],url]\
        )
    return b1_list
    

f_loc = os.getcwd()+'/log.txt'
with open(f_loc,'w') as logfile:
    logfile.write('log written at %s\n' % (time.ctime()))
    
    f_loc = os.getcwd()+'/twt_keys.txt'
    with open(f_loc,'r') as keys:
        cons_key = keys.readline().strip()
        cons_secret = keys.readline().strip()
        access_token = keys.readline().strip()
        access_token_secret = keys.readline().strip()
    
    t = Twitter(
    auth=OAuth(access_token, access_token_secret, cons_key, cons_secret))
    
    f_loc = os.getcwd()+'/last_seen_time.txt'
    with open(f_loc,'r') as time_file:
        str_time = time_file.readline().strip()
        try:
            last_time = time.strptime(str_time,'%Y-%m-%d %H:%M:%S')
        except:
            logfile.write('missing last_seen_time; setting new last_seen_time to current time\n')
            last_time = time.gmtime()
    llt = list(last_time)
    llt = llt[:-1]
    llt.append(0)
    last_time = time.struct_time(tuple(llt))
    logfile.write('time from file: ')
    logfile.write(str(last_time))
    first_time = True
    i = 0
    logfile.write('\n\nLooking for recent reports, and printing out details\n\n')
    for report in scrape_reports_filed():
        i+=1
        logfile.write('interation count: %d\n'%(i))
        if i>100:
            break
        if first_time:
            with open(f_loc,'w') as time_file:
                try:
                    str_time = time.strftime('%Y-%m-%d %H:%M:%S', report['post_date'])
                    logfile.write('%s updated to %s\n' % (f_loc,str_time))
                except:
                    logfile.write('report missing timestamp "%s"; using current\n' % (str(report['post_date'])))
                    for r in report:
                        logfile.write(str(r))
                    report['post_date'] = time.gmtime()
                time_file.write(str_time)
            first_time = False
        if report['post_date'] <= last_time:
            logfile.write('time passed with %s\n' % \
                (time.strftime('%Y-%m-%d %H:%M:%S', report['post_date'])) )       
            break
        logfile.write('%s <= %s is %s\n' % \
            (str(report['post_date']),str(last_time) \
            ,str(report['post_date']<=last_time)))
        if report['report_type'] == 'A1':
            _out =  scrape_a1(\
                report['report_id'],
                report['report_url'],
                report['report_date'])
            if _out[0]=='empty':
                continue
            moni = 0
            for con in _out[1]:
                moni = moni+float(con[1:].replace(',',''))
            moni_str = str(moni)
            m = moni_str.split('.')
            moni_str = m[0]
            if len(moni_str) > 6:
                moni_str = moni_str[:-6]+','+moni_str[-6:-3]+','+moni_str[-3:]
            elif len(moni_str) > 3:
                moni_str = moni_str[:-3]+','+moni_str[-3:]
            tweet_str = '$%s A1: to %s' %\
                (moni_str,_out[0])
            if len(tweet_str)>112:
                tweet_str = tweet_str[:105]+'...\n'+report['report_url']
            else:
                tweet_str = tweet_str+'\n'+report['report_url']
            tweet_str = tweet_str.encode('utf-8')
            logfile.write(tweet_str+'\n')
            try:
                t.statuses.update(status=tweet_str)
            except:
                with open('bad_tweet.txt','w') as bt:
                    bt.write(tweet_str+'\n')
                    for r in report:
                        print(str(r))
        elif report['report_type'] == 'B1':
            _out = scrape_b1(
                report['report_id'],
                report['report_url'],
                report['report_date'])
            moni = 0
            for j in range(len(_out)):
                moni = moni + float(_out[j][1][:-3].strip('$').replace(',',''))
            moni_str = '%s' % (moni)
            moni_str = moni_str.split('.')[0]
            if len(moni_str) > 6:
                moni_str = moni_str[:-6]+','+moni_str[-6:-3]+','+moni_str[-3:]
            elif len(moni_str) > 3:
                moni_str = moni_str[:-3]+','+moni_str[-3:]
            so = _out[j][4].lower()[0:4]
            if so[0] == 'o':
                so = so[0:3]
            so = so+'.'
            tweet_str = '$%s B1: %s %s for %s from %s.\n'\
                        % (moni_str,so,_out[0][5],\
                        _out[0][6],_out[0][0])
            if len(tweet_str)>112:
                tweet_str = tweet_str[:105]+'...\n'+_out[j][7]
            else:
                tweet_str = tweet_str+_out[j][7]
            tweet_str = tweet_str.encode('utf-8')
            logfile.write(tweet_str+'\n')
            try:
                t.statuses.update(status=tweet_str)
            except:
                with open('bad_tweet.txt','w') as bt:
                    bt.write(tweet_str+'\n')
                    for r in report:
                        print(str(r))
        elif report['report_type'] == 'D2':
            tweet_str = 'D2 filing from %s:\n%s' % (report['report_id'],report['report_url'])
            t.statuses.update(status=tweet_str)            
        elif report['report_type'] == 'PDF':
            tweet_str = 'Paper filing for %s:\n%s' % (report['report_id'],report['report_url'])
            t.statuses.update(status=tweet_str)
    logfile.write('\n\nexiting program')
