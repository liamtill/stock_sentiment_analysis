from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import requests
from newsapi import NewsApiClient
import datetime as dt
import praw
from psaw import PushshiftAPI
import pandas as pd
import os
import numpy as np
import yfinance as yf
from dash.dependencies import Input, Output, State
import yaml

def get_twtr_sentiment(ticker, apikey):
    """
    Fetch stock sentiment from socialsentiment.io. Twitter sentiment scores

    200 - Success
    400 - Invalid request - Response body will include a description of the details
    404 - Not found
    429 - Exceeded rate limit
    500 - Server error

    :param ticker: stock ticker
    :return: score and avg data for 7, 14 and 30 days
    """
    

    response = requests.get("https://socialsentiment.io/api/v1/stocks/"+ticker+"/sentiment/daily/",
                headers={"Authorization": apikey, "Accept": "application/json"})

    data = response.json()

    dates = []
    avg_7_days = []
    avg_14_days = []
    avg_30_days = []
    scores = []

    for i, d in enumerate(data):
        avg_7_days.append(d['avg_7_days'])
        avg_14_days.append(d['avg_14_days'])
        avg_30_days.append(d['avg_30_days'])
        scores.append(d['score'])
        dates.append(d['date'])

    return response.status_code, dates, scores, avg_7_days, avg_14_days, avg_30_days


def sentiment_analyzer_scores(sentence):
    """
    Analyse sentiment of a sentence
    :param sentence:
    :return: compound sentiment
    """
    analyser = SentimentIntensityAnalyzer()

    customwords = {
        'call': 4.0,
        'put': -4.0,
        'buy': 4.0,
        'sell': -4.0,
        'calls': 4.0,
        'puts': -4.0,
        'tendies': 4.0,
    }

    analyser.lexicon.update(customwords)

    try:
        score = analyser.polarity_scores(sentence)
        return score['compound']
    except:
        return np.nan


def get_ticker_name(symbol):
    """
    Get company name for ticker
    :param symbol:
    :return: company name
    """
    url = "http://d.yimg.com/autoc.finance.yahoo.com/autoc?query={}&region=1&lang=en".format(symbol)

    result = requests.get(url).json()

    for x in result['ResultSet']['Result']:
        if x['symbol'] == symbol:
            return x['name']


def daterange(date1, date2):
    for n in range(int ((date2 - date1).days)+2):
        yield date1 + dt.timedelta(n)


def get_news(q, from_date, apikey):
    """
    Get news for a query
    :param q: query
    :param from_date: from when date
    :return:
    """
    newsapi = NewsApiClient(api_key=apikey)

    # /v2/everything
    all_articles = newsapi.get_everything(q=q,
                                          from_param=from_date,
                                          language='en',
                                          sort_by='relevancy')

    return all_articles


def reddit_scrape(q, sub, start_time, end_time, config, limit=1):
    """
    Scrape reddit for post and comments for a search query between dates
    :param q: query term
    :param sub: sub to search
    :param start_time: start date
    :param end_time: end date
    :param limit: limit number of comments
    :return: dict of post title, body and comments
    """

    id = config['id']
    secret = config['secret']
    appname = config['appname']
    username = config['username']
    pwd = config['passwd']

    reddit = praw.Reddit(client_id=id, client_secret=secret, user_agent=appname, username=username,
                         password=pwd)

    subreddit = reddit.subreddit(sub)

    psawapi = PushshiftAPI()

    start_time_epoch = int(start_time.timestamp())
    end_time_epoch = int(end_time.timestamp())

    submissions = list(psawapi.search_submissions(q=q, after=start_time_epoch, before=end_time_epoch, subreddit=sub,
                                                  filter=['id', 'url', 'author', 'title', 'selftext', 'subreddit']))

    post_dict = {}
    comments_dict = {}
    for date in daterange(start_time, end_time):
        datestamp = date.strftime("%Y-%m-%d")
        post_dict[datestamp] = {
                        "title": [],  # title of the post
                        "score": [],  # score of the post
                        "id": [],  # unique id of the post
                        "url": [],  # url of the post
                        "comms_num": [],  # the number of comments on the post
                        "created": [],  # timestamp of the post
                        "body": []  # the content of post
                    }
        comments_dict[datestamp] = {
                        "comment_id": [],  # unique comm id
                        "comment_parent_id": [],  # comment parent id
                        "comment_body": [],  # text in comment
                        "comment_link_id": []  # link to the comment
                    }

    for sm in submissions:
        id = sm[-1]['id']
        submission = reddit.submission(id=id)
        timestamp = submission.created_utc
        datestamp = dt.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

        if submission.selftext == '[removed]':
            continue
        if submission.selftext == '[deleted]':
            continue

        post_dict[datestamp]['title'].append(submission.title)
        post_dict[datestamp]['body'].append(submission.selftext)

        submission.comments.replace_more(limit=limit)
        submission.comment_sort = "top"
        for comment in submission.comments.list():
            comments_dict[datestamp]["comment_body"].append(comment.body)

    return post_dict, comments_dict


def save_data(dict, filename, mode):
    """
    Store data to csv
    :param dict: dicf df
    :param filename: output filename
    :param mode: write or append
    :return:
    """

    sent_data_df = pd.DataFrame.from_dict(dict, orient='index')
    if mode == 'w':
        sent_data_df.to_csv(filename, mode=mode, index_label='date')
    else:
        sent_data_df.to_csv(filename, mode=mode, header=False)


def read_data(filename):
    """
    Read data from csv to df
    :param filename: filename
    :return: df from csv
    """
    data = pd.read_csv(filename)
    return data


def get_stock_data(ticker, start, end):
    return yf.download(ticker, start=start, end=end)


def process_news(start_time, end_time, all_articles):

    news_data = {}
    for date in daterange(start_time, end_time):
        datestamp = date.strftime("%Y-%m-%d")
        news_data[datestamp] = {'title': [], 'content': []}

    # loop all_articles['articles']
    print('processing news data')
    for article in all_articles['articles']:
        try:
            published = article['publishedAt']
            published_date = dt.datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
            published_date_str = published_date.strftime('%Y-%m-%d')
            # print(published, published_date, published_date.strftime('%Y-%m-%d'))
            news_data[published_date_str]['title'].append(article['title'])
            news_data[published_date_str]['content'].append(article['content'])
        except Exception as e:
            print('error processing news data for article')
            print(e)
            news_data[published_date_str] = {'title': [], 'content': []}
            continue

    print('processed news data')
    return news_data


def process_reddit(ticker, subs, start_time, end_time, config, limit):

    print('subs to get data from: ', subs)
    sub_data = {k: {} for k in subs}
    q = ticker
    for sub in subs:
        try:
            print('fetching reddit data from: ', sub)
            post_dict, comments_dict = reddit_scrape(q, sub, start_time, end_time, config, limit=limit)
            sub_data[sub]['posts'] = post_dict
            sub_data[sub]['comments'] = comments_dict
            print('fetched reddit data from: ', sub)
        except Exception as e:
            print('error fetching reddit data from: ', sub)
            print(e)
            sub_data[sub] = {}
            continue

    return sub_data


def get_news_sentiment(news_data, news_sentiment):

    print('calculating sentiment for news')
    for d in news_data.keys():
        for title, content in zip(news_data[d]['title'], news_data[d]['content']):
            try:
                title_sent = sentiment_analyzer_scores(title)
                content_sent = sentiment_analyzer_scores(content)
                news_sentiment[d].append(np.nanmean([title_sent, content_sent]))
            except Exception as e:
                print('error calculating sentiment for news for: ', d)
                print(e)
                continue

    print('calculated sentiment for news')

    return news_sentiment


def get_reddit_sentiment(sub_data, reddit_sentiment):

    print('calculating sentiment for reddit data')
    for sub, v in sub_data.items():
        for d in sub_data[sub]['posts'].keys():
            #print(sub_data[sub]['posts'][d].keys())
            try:
                title_sent = sentiment_analyzer_scores(sub_data[sub]['posts'][d]['title'])
                body_sent = sentiment_analyzer_scores(sub_data[sub]['posts'][d]['body'])
                post_sent = np.mean([title_sent, body_sent])
                reddit_sentiment[d].append(post_sent)
            except Exception as e:
                print('error calculating sentiment for reddit post')
                continue
        for d in sub_data[sub]['comments'].keys():
            #print(sub_data[sub]['comments'][d].keys())
            try:
                comment_sent = sentiment_analyzer_scores(sub_data[sub]['comments'][d]['comment_body'])
                reddit_sentiment[d].append(comment_sent)
            except Exception as e:
                print('error calculating sentiment for reddit comment')
                continue

    print('calculated sentiment for reddit data')

    return reddit_sentiment


def get_final_sentiment(stock_data, sent_data, reddit_sentiment, news_sentiment, twtr_data):

    print('doing final sentiment calculations')
    for i, d in enumerate(news_sentiment.keys()):
        # calculate mean sentiment and add to dict for each source
        try:
            sent_data[d]['reddit'] = np.mean(reddit_sentiment[d])
        except Exception as e:
            print('error calculating reddit sentiment for: ', d)
            #continue
        try:
            sent_data[d]['news'] = np.mean(news_sentiment[d])
        except Exception as e:
            print('error calculating news sentiment for: ', d)
            #continue
        try:
            sent_data[d]['mean'] = np.mean([news_sentiment[d]+reddit_sentiment[d]])
        except Exception as e:
            print('error calculating mean sentiment for: ', d)
            #continue
        try:
            sent_data[d]['twitter'] = twtr_data[d]/100. # normalise to -1, 1
        except Exception as e:
            print('error calculating socialsentiment.io values')
            sent_data[d]['twitter'] = np.nan
        # add stock price data to dict
        try:
            # no data for weekends or non trading days. nan out
            #'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'
            sent_data[d]['open'] = stock_data['Open'][d]
            sent_data[d]['high'] = stock_data['High'][d]
            sent_data[d]['low'] = stock_data['Low'][d]
            sent_data[d]['close'] = stock_data['Close'][d]
            sent_data[d]['vol'] = stock_data['Volume'][d]
            lastopen = stock_data['Open'][d]
            lasthigh = stock_data['High'][d]
            lastlow = stock_data['Low'][d]
            lastclose = stock_data['Close'][d]
            lastvol = stock_data['Volume'][d]
        except Exception as ed:
            sent_data[d]['open'] = lastopen
            sent_data[d]['high'] = lasthigh
            sent_data[d]['low'] = lastlow
            sent_data[d]['close'] = lastclose
            sent_data[d]['vol'] = lastvol

    print('final sentiment data calculated')
    return sent_data


def run_sentiment(ticker):

    # load config
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    lookback = config['GLOBAL']['lookback']
    sublimit = config['GLOBAL']['sublimit']
    socialsentiment_apikey = config['APIKEYS']['socialsentiment']
    newsapikey = config['APIKEYS']['newsapi']


    print('Running for ticker: ', ticker)
    subs = config['REDDIT']['subs']
    #TODO: yahoo finance scrape for ticker name needs updating
    name = ticker #get_ticker_name(ticker)

    if name is None:
        print('cannot retrieve company name, stopping...')
        return pd.DataFrame({})

    filename = ticker + "_sentiment.csv"
    exists = False

    try:
        q = ticker + ' OR ' + name # search query
        print('query for: ', q)
    except Exception as e:
        print('ticker query incorrect, cannot get company name', e)
        q = ticker

    end_time = dt.datetime.now() - dt.timedelta(days=1)
    print('end time: ', end_time)

    if os.path.exists(filename):
        print(filename, 'exists')
        sent_file = read_data(filename)
        #print(sent_file)
        #print(list(sent_file['date']))
        start_time = dt.datetime.strptime(list(sent_file['date'])[-1], '%Y-%m-%d')# +  dt.timedelta(days=1)
        print('start time: ', start_time)
        exists = True
        if start_time >= end_time:
            print('loading data for plot')
            data = read_data(filename)
            return data
    else:
        print(filename, 'does not exist')
        start_time = dt.datetime.now() - dt.timedelta(days=lookback)

        print('start time: ', start_time)

    ## GET PRICE DATA ##
    print('downloading stock data')
    stock_data = get_stock_data(ticker, start=start_time.strftime('%Y-%m-%d'), end=end_time.strftime('%Y-%m-%d'))
    print('downloaded stock data')
    ## END PRICE DATA ##

    ## GET TWITTER SENTIMENT FROM SOCAILSENTIMENT.IO ##
    #  7 DAYS DATA ONLY #
    failed = []
    twtr_data = {}
    # get sentiment for each ticker
    try:
        print('getting twitter sentiment from socialsentiment.io')
        status, twtr_dates, twtr_scores, avg_7_days, avg_14_days, avg_30_days = get_twtr_sentiment(ticker, socialsentiment_apikey)
    except Exception as e:
        print(e)
        status = 999
        twtr_scores = []

    # successful so get sentiment
    if status == 200:
        # calc weighted sentiment, weighting latest more than past
        # these are abtirary weights
        twtrsent = 0.6 * np.nanmean(avg_7_days) + 0.3 * np.nanmean(avg_14_days) + 0.1 * np.nanmean(avg_30_days)
        twtrsent = np.round(twtrsent)

        # check not nan
        if np.isnan(twtrsent):
            twtrsent = ''

        for date, score in zip(twtr_dates, twtr_scores):
            twtr_data[date] = score
        print('got twitter sentiment from socialsentiment.io')

    # failed rate, try again after rest, sleep for a minute to refresh rate
    elif status == 429:
        failed.append(ticker)
        print('failed to get twitter sentiment from socialsentiment.io')
        pass

    # some other error we don't care. NA value
    else:
        print('failed to get twitter sentiment from socialsentiment.io')
        twtrsent = ''

    ## END TWITTER SENTIMENT ##

    ## GET NEWS ARTICLES FOR TICKER AND COMPANY NAME ##
    # UP TO 30 DAYS DATA #

    try:
        print('getting news from newsapi')
        all_articles = get_news(q, start_time, newsapikey) # title, content
        print('fetched news articles using newsapi')
    except Exception as e:
        print('error getting news from newsapi')
        print(e)

    news_data = process_news(start_time, end_time, all_articles)

    ## END NEWS SCRAPE ##

    # REDDIT SCRAPE ##
    # ANY TIME DATA #

    sub_data = process_reddit(ticker, subs, start_time, end_time, config['REDDIT'], limit=sublimit)

    ## END REDDIT SCRAPE ##

    ## ANALYSE SENTIMENT ON ALL DATA ##

    news_sentiment = {}
    reddit_sentiment = {}
    sent_data = {}
    for date in daterange(start_time, end_time):
        datestamp = date.strftime("%Y-%m-%d")
        news_sentiment[datestamp] = []
        reddit_sentiment[datestamp] = []
        sent_data[datestamp] = {}#{'twitter': [], 'news': [], 'reddit': []}

    news_sentiment = get_news_sentiment(news_data, news_sentiment)

    reddit_sentiment = get_reddit_sentiment(sub_data, reddit_sentiment)

    sent_data = get_final_sentiment(stock_data, sent_data, reddit_sentiment, news_sentiment, twtr_data)

    ## END SENTIMENT ANALYSIS ##

    ## WRITE TO CSV ##
    print('saving csv data')
    if exists:
        save_data(sent_data, filename, mode='a')
    else:
        save_data(sent_data, filename, mode='w')
    print('csv data saved')
    ## END WRITE TO CSV ##

    ## NOW LOAD THAT SHIT IN TO PLOT IT ##
    print('loading data for plot')
    data = read_data(filename)
    return data
    ## END LOADING DATA ##

