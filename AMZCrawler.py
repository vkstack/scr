#!/usr/bin/python

from datetime import datetime
import time
import inspect
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException,StaleElementReferenceException,ElementNotVisibleException,TimeoutException, ElementNotSelectableException
import multiprocessing
import sys,os
import re
from pprint import pprint
from bs4 import BeautifulSoup
import json
from pymongo import MongoClient
from dbConnection import config
bestsellers_url = "https://www.amazon.in/gp/bestsellers"
# bestsellers_url = 'https://www.amazon.in/gp/bestsellers/boost/10894225031/ref=zg_bs_nav_2_10894224031'
category_root_id = "zg_browseRoot"
current_category = "zg_selected"
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("disable-infobars")
chrome_options.add_argument("start-maximized")
chrome_options.add_argument("--disable-dev-shm-usage")

chromedriver_path='/usr/bin/chromedriver'
excluded_cats = ['Kindle Store','Movies & TV Shows','Music','Books','Gift Cards']
product_page = "https://www.amazon.in/dp/%s"
DEBUG = False

def PrintFrame():
  callerframerecord = inspect.stack()[1]    # 0 represents this line
                                            # 1 represents line at caller
  frame = callerframerecord[0]
  info = inspect.getframeinfo(frame)
  print(info.lineno) 

def ChildsCategories(rootElement):
    try:
         return rootElement.find_elements_by_xpath("//span[@class='%s']/ancestor::li/following-sibling::ul/li/a"%current_category)
    except Exception as e:
        return False

def exploreLeaf(driver,item,Q):
    center_content = driver.find_element_by_id('zg-center-div')
    try:
        try:
            next_page = center_content.find_element_by_xpath("//ul[@class='a-pagination']/li[@class='a-last']")
            xx = next_page.find_element_by_partial_link_text('Next page')
            Q.put((xx.get_attribute("href"),item[1],0,item[3]))
        except Exception as e:
            pass
        pids =  map(lambda x: re.search('/dp/([^/]*)/',x.get_attribute('href')).groups()[0] , center_content.find_elements_by_xpath("//ol[@id='zg-ordered-list']/li/span/div/span/a"))
        pids = list(set(pids))
        for x in pids:
            Q.put((product_page%x,item[1],0,'product'))
    except Exception as e:
        Q.put(item)

def traverseIter(Q,PQ):
    try:
        driver = webdriver.Chrome(chrome_options=chrome_options,executable_path=chromedriver_path)
        format = '%Y-%m-%d %H:%M:%S'
        while True:
            timestamp = datetime.now().strftime(format)
            try:
                item = Q.get(True,100)
            except Exception as e:
                return
            driver.get(item[0])
            # print page
            # pass
            if item[3] == 'category':
                try:
                    root = driver.find_element_by_id(category_root_id)
                    selected = root.find_element_by_xpath("//span[@class='%s']"%current_category)
                except Exception as e:
                    if item[2]  < 3:
                        Q.put((item[0],item[1],item[2]+1,item[3]))
                    continue
                child_cats = ChildsCategories(root)
                # Restricted categories.
                if selected.text in excluded_cats:
                    continue
                path = item[1] +"//%s"%selected.text
                if child_cats is False or not child_cats: #leaf category
                    print "%s %s Leaf Category : "%(os.getpid(),timestamp),path
                    exploreLeaf(driver,item,Q)
                    # for x in pids:
                    #     Q.put((product_page%x,path,0,'product'))
                        # if not pids:
                        #    print "No PIDs in category"
                       # return
                else:
                    print "%s %s Meta Category : "%(os.getpid(),timestamp),path
                    for x in child_cats:
                        Q.put((x.get_attribute("href"),path,0,'category'))
            else:
                try:
                    # print item
                    product = scrapeAmazonPDP(driver,item)
                    # print product
                    PQ.put(product)
                    # print "Success->",item
                except Exception as e:
                    # print "Failure->",item,
                    if DEBUG:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        print exc_type, fname, exc_tb.tb_lineno
                    if item[2]  < 3:
                        Q.put((item[0],item[1],item[2]+1,item[3]))
                    else:
                        print item
                    continue
    except Exception as e:
        if DEBUG:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print exc_type, fname, exc_tb.tb_lineno,
            print e,item
        traverseIter(Q,PQ)

# Scraping Amazon's PDP
'''
datas to be scraped 
Category path, ASIN , URL
MRP | SP / DP , Title , Image URL,
'''
def scrapeAmazonPDP(driver,ASIN):
    try:
        ex = driver.find_element_by_xpath("//div[@id='altImages']/ul/li[contains(@class,'imageThumbnail')]")
        ex.click()
        # print ASIN
        soup = BeautifulSoup(driver.page_source,'lxml')
        product ={
            'asin':os.path.basename(ASIN[0]),
            'url':ASIN[0]
        }
        # Capturing All the images.
        x = soup.find('script',text=re.compile("'colorImages': { 'initial':"))
        # product['images'] = json.dumps(re.findall('hiRes":"([^"]*)"',x.string))
        product['images'] = re.findall('hiRes":"([^"]*)"',x.string)
    except Exception as e:
        if DEBUG:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print exc_type, fname, exc_tb.tb_lineno,e,
        raise e
    try:
        '''
        <tr>
            <td class="a-color-secondary a-size-base a-text-right a-nowrap">M.R.P.:</td>
            <td class="a-span12 a-color-secondary a-size-base">
                <span class="a-text-strike"> <span class="currencyINR">&nbsp;&nbsp;</span> 300.00</span>
        <span id="listPriceLegalMessage">
        </span>
        <style>
            #listPriceLegalMessageText {
                margin-left: 5px !important;
            }
            
            #listPriceLegalMessage .a-popover-trigger:hover {
                text-decoration: underline !important;
            }
            
            #listPriceLegalMessage .a-icon-popover {
                display: inline-block !important;
                margin-left: 0px !important;
                margin-top: 6px !important;
            }
        </style>
                
            </td>
        </tr>
        '''
        product_data_element = soup.find(id='centerCol')
        price_pattern = re.compile("\d+\.\d+",re.MULTILINE)

        price_rank = 1
        # Deal PRICE
        tmp = product_data_element.find(id='priceblock_dealprice')
        if tmp is not None:
            tmp = price_pattern.search(tmp.text)
            product['deal_price'] = tmp.group()
            price_rank += 1

        # PRICE
        tmp = product_data_element.find(id='priceblock_ourprice')
        if tmp is not None:
            tmp = price_pattern.search(tmp.text)
            product['price'] = tmp.group()
            price_rank += 1

        # MRP
        tmp = product_data_element.find(id='listPriceLegalMessage')
        if tmp is not None:
            tmp = tmp.findPreviousSibling()
            tmp = price_pattern.search(tmp.text)
            product['mrp'] = tmp.group()
            price_rank += 1

        # productTitle
        tmp = product_data_element.find(id='productTitle')
        product['title'] = tmp.text.strip()
        return product
    except Exception as e:
        if DEBUG:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print exc_type, fname, exc_tb.tb_lineno,e,
        raise e



if __name__ == '__main__':
    # DEBUG = True
    Q,PQ= multiprocessing.Queue(),multiprocessing.Queue()
    Q.put(('https://www.amazon.in/gp/bestsellers/boost/10894225031/ref=zg_bs_nav_2_10894224031','',0,'category'),);
    # Q.put((u'https://www.amazon.in/dp/B01CYGHLFY', '', 0, 'product'))
    # Q.put(('https://www.amazon.in/dp/B01M9EB7ZK','',0,'product'),);
    # multiprocessing.cpu_count()-1
    # pool = multiprocessing.Pool(1,traverseIter,(Q,PQ,))
    pool = multiprocessing.Pool(max(1,multiprocessing.cpu_count()-2),traverseIter,(Q,PQ,))
    # client = MongoClient(host=config['host'],port=config['port'])
    # db = client.get_database('shopclue_prod')
    # col = db.get_collection('scraped_competitor_products')
    count=0
    while True:
        try:
            product = PQ.get(True,100)
            count +=1
            print product.get('title')
        except Exception as e:
            break
    print count
    pool.close()
    pool.join()


# the_queue = multiprocessing.Queue()
# def worker_main(queue):
#     print os.getpid(),"working"
#     while True:
#         item = queue.get(True)
#         print os.getpid(), "got", item
#         time.sleep(1) # simulate a "long" operation

# the_pool = multiprocessing.Pool(3, worker_main,(the_queue,))
# for i in range(5):
#     the_queue.put("hello")
#     the_queue.put("world")
# time.sleep(10)

'''
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException,StaleElementReferenceException,ElementNotVisibleException,TimeoutException, ElementNotSelectableException
import multiprocessing
import os
import re
from bs4 import BeautifulSoup
from pprint import pprint

bestsellers_url = "https://www.amazon.in/gp/bestsellers"

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("disable-infobars")
chrome_options.add_argument("start-maximized")
chrome_options.add_argument("--disable-dev-shm-usage")

chromedriver_path='/usr/bin/chromedriver'
excluded_cats = ['Kindle Store','Movies & TV Shows','Music','Books','Gift Cards']
product_page = "https://www.amazon.in/dp/%s"
driver = webdriver.Chrome(chrome_options=chrome_options,executable_path=chromedriver_path)
driver.get('https://www.amazon.in/gp/bestsellers/boost/10894225031/ref=zg_bs_nav_2_10894224031')
'''
