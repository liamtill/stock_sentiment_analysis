### Stock Sentiment Analyser

**NOTE: This repository is for archive purposes and will not be updated. However, you may still find some useful code here for your own projects**

Stock sentiment analyser. Scrapes news articles using [NewsAPI](https://newsapi.org/), Twitter sentiment for a stock using [SocialSentiment.io](https://socialsentiment.io/) and sub-reddits posts (and comments if wanted) from Reddit.
News articles, tweets and Reddit posts are then analysed for sentiment using [VADER Sentiment Analysis](https://pypi.org/project/vaderSentiment/). A composite sentiment score is calculated and plotted with stock price for the last month.

This was created a small personal project to learn how to scrape different sources and use sentiment analysis. Comparing social media sentiment against stock price was an interesting
project to learn these skills. 

### Setup

* [Get a free API key from NewsAPI](https://newsapi.org/register)
* [Get a free API key from SocialSentiment.io](https://socialsentiment.io/api/v1/getting-started/)
* [Follow this tutorial to set up an app in Reddit](https://www.geeksforgeeks.org/scraping-reddit-using-python/)
to get an app ID, app secret, app name. Use these details with your reddit username and password. This is needed to be able to scrape content from Reddit.

Copy `config.yaml.example` to `config.yaml` and enter your API keys for SocialSentiment, NewsAPI and the details for Reddit. Also define the sub-reddits you want to scrape.

Create a virual environment `python3 -m venv venv` and activate the environment `source venv/bin/activate`. Install the requirements `pip install -r requirements.txt`.

Run the dashboard `python3 stock_sentiment_analysis.py` and go to [localhost:8050](http://localhost:8050/) in your browser. Then enter the ticker and wait for the scraping and sentiment analysis to complete. Note that it can take a few minutes for the analysis to run. 