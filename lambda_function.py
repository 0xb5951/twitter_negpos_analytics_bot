# 並列処理
import threading
import os
import json
import boto3
import datetime.datetime as dt

from requests_oauthlib import OAuth1Session  # OAuthのライブラリの読み込み

# 検索クエリ
query = os.environ["query"]
# ネガポジ閾値
negpos_threshold = int(os.environ["negpos_threshold"])
# Slack通知先
slack_room = os.environ["slack_chanel"]

# twitterAPIアクセストークン
CK = os.environ["twitter_CK"]
CS = os.environ["twitter_CS"]
AT = os.environ["twitter_AT"]
ATS = os.environ["twitter_ATS"]


def lambda_function(event, content):
    thread_1 = threading.Thread(target=return_200)
    thread_2 = threading.Thread(target=main_func(event, content))
    return 0

# slackにとりあえず200を返す
def return_200():
    print("prodess kill")
    return 0

def main_func(event, content):
    twitter = OAuth1Session(CK, CS, AT, ATS)  #認証処理

    # twitter検索結果取得エンドポイント
    url = 'https://api.twitter.com/1.1/search/tweets.json'
    query += " since:" + dt.today().strftome("%Y-%m-%d")
    print(query)

    # ランサーズが含まれる昨日からのツイートを取得する
    res = twitter.get(url, params={'q': query})

    if res.status_code == 200:
        print(res.text)

    return 0
