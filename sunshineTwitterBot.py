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
        if report_url.startswith(
                'http://www.elections.il.gov/CampaignDisclosure/A1'):
            report_type = 'A1'
            report_id = parsed_url['FiledDocID'][0]
        elif report_url.startswith(
                'http://www.elections.il.gov/CampaignDisclosure/B1'):
            report_type = 'B1'
            report_id = parsed_url['FiledDocID'][0]
        else:
            report_type = 'UNK'  # Unknown/unhandled report type
            report_id = -1
        reports_list.append({
            'report_id': report_id,
            'report_type': report_type,
            'report_url': report_url,
            'report_date': report_date
        })
    return reports_list


# Scraper interfaces for specific report types
def scrape_a1(report_id, report_url, report_date):
    """
    Given a report_id, attempts to download it and scrape it.
    Unlike with D2s, we need the URL and date up front, because they're tougher
    to extract from the body of the A1 report itself.
    """
    req = requests.get(report_url)
    soups = [BeautifulSoup(req.text)]
    a1_list = _process_a1_page(soups,report_url,report_id,report_date)
    return a1_list
    
        
# Scraper interfaces for specific report types
def scrape_b1(report_id, report_url, report_date):
    """
    Given a report_id, attempts to download it and scrape it.
    Unlike with D2s, we need the URL and date up front, because they're tougher
    to extract from the body of the A1 report itself.
    """
    req = requests.get(report_url)
    soups = [BeautifulSoup(req.text)]
    b1_list = _process_b1_page(soups, report_url, report_id, report_date)  
    return b1_list
        

# Scraper "backends" for specific report types
def _process_a1_page(soups, url, report_id, report_date):
    """
    Does the heavy lifting of actually looking at the report HTML, extracting
    the data we care about and saving it to the db.
    """
    amt = []
    date = []
    name = soups[0].findAll('span', id='ctl00_ContentPlaceHolder1_lblName')
    if name:
        cmte_name = name[0].contents[0]
    a1_list = []
    for f in soups[0].findAll('td', 'tdA1List'):
        if 'thA1Amount' in f['headers'][0]:
            amt.append(f.findAll('span')[0].contents[0])  
            date.append(f.findAll('span')[0].contents[2]) 
#    if report['report_id']=='625680': sys.exit()        
    a1_list = [cmte_name,amt,date]
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


keys = open('twt_keys.txt')
cons_key = keys.readline().strip('\n').strip("'")
cons_secret = keys.readline().strip('\n').strip("'")
access_token = keys.readline().strip('\n').strip("'")
access_token_secret = keys.readline().strip('\n').strip("'")
keys.close()


t = Twitter(
auth=OAuth(access_token, access_token_secret, cons_key, cons_secret))


id_file = open('last_seen_id.txt','r')
last_id = id_file.readline()
id_file.close()
id_file = open('last_seen_id.txt','w')
first_id = True
print 'Looking for recent reports, and printing out details'
for report in scrape_reports_filed():
    if first_id:
        id_file.write(report['report_id'])
        id_file.close()
        first_id = False
    if report['report_id'] == str(last_id):
        break
    if report['report_type'] == 'A1':
        _out =  scrape_a1(\
            report['report_id'],
            report['report_url'],
            report['report_date'])
        moni = 0
        for con in _out[1]:
            moni = moni+float(con[1:].replace(',',''))
        moni_str = str(moni)
        if len(moni_str) > 9:
            moni_str = moni_str[:-9]+','+moni_str[-9:-6]+','+moni_str[-6:-3]
        elif len(moni_str) > 6:
            moni_str = moni_str[:-6]+','+moni_str[-6:-3]
        tweet_str = '$%s A1: to %s\n%s' %\
            (moni_str,_out[0],report['report_url'])
        t.statuses.update(status=tweet_str)
    elif report['report_type'] == 'B1':
        _out = scrape_b1(
            report['report_id'],
            report['report_url'],
            report['report_date'])
        for j in range(len(_out)):
            so = _out[j][4].lower()[0:4]
            if so[0] == 'o':
                so = so[0:3]
            so = so+'.'
            tweet_str = '%s B1: %s %s for %s from %s.\n'\
                        % (_out[j][1][:-3],so,_out[j][5],\
                        _out[j][6],_out[j][0])
            if len(tweet_str)>112:
                tweet_str = tweet_str[:105]+'...\n'+_out[j][7]
            else:
                tweet_str = tweet_str+_out[j][7]
        t.statuses.update(status=tweet_str)


