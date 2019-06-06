# 並列処理
import threading
import os
import json
import boto3
import datetime
import requests

from requests_oauthlib import OAuth1Session  # OAuthのライブラリの読み込み

# ネガポジ閾値
negpos_threshold = int(os.environ["negpos_threshold"])
# Slack通知先
slack_room = os.environ["slack_chanel"]

# twitterAPIアクセストークン
CK = os.environ["twitter_CK"]
CS = os.environ["twitter_CS"]
AT = os.environ["twitter_AT"]
ATS = os.environ["twitter_ATS"]

NLP_Key = os.environ["NLP_Key"]

MONTH_LUT = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

def lambda_function(event, content):
    thread_1 = threading.Thread(target=return_200)
    thread_2 = threading.Thread(target=main_func(event, content))
    return 0

# slackにとりあえず200を返す
def return_200():
    print("prodess kill")
    return 0


def date_translate(date):
    pre_date = date.split(' ')
    y = pre_date[-1]
    m = MONTH_LUT[pre_date[1]]
    d = pre_date[2]
    time = pre_date[3]
    res_date = '{}-{}-{} {}'.format(y, m, d, time)
    print(res_date)
    return res_date

def main_func(event, content):
    twitter = OAuth1Session(CK, CS, AT, ATS)  #認証処理
    # 検索クエリ
    query = os.environ["query"]
    # twitter検索結果取得エンドポイント
    url = 'https://api.twitter.com/1.1/search/tweets.json'
    since = datetime.datetime.now()
    query += " since:" + since.strftime("%Y-%m-%d")

    # ランサーズが含まれる昨日からのツイートを取得する
    res = twitter.get(url, params={'q': query})

    if res.status_code == 200:
        res_text = json.loads(res.text)
        print(res_text)
        #NLPAPI
        nlp_url = 'https://language.googleapis.com/v1/documents:analyzeSentiment?key=' + NLP_Key

        # try:
        #     dynamoDB = boto3.resource("dynamodb")
        #     table = dynamoDB.Table("twitter_negpos")  # DynamoDBのテーブル名

        #     # 昨日からのツイートデータをとってくる
        #     dynamo_data = table.query(
        #         KeyConditionExpression = Key("tweet_time").gt(since.strftime("%Y-%m-%d"))
        #     )
        # except Exception as e:
        #     print(e)

        # ツイートデータを保存する
        try:
            dynamoDB = boto3.resource("dynamodb")
            table = dynamoDB.Table("twitter_negpos")  # DynamoDBのテーブル名

            for tweet in res_text['statuses']:
                # print(tweet)
                # 投稿データを加工
                tweet_time = date_translate(tweet['created_at'])

                # 昨日からのツイートデータをとってくる
                res = table.put_item(
                    Item={
                        "tweet_id": tweet['id_str'],
                        "negpos": 0,
                        "tweet_user": tweet['user']['screen_name'],
                        "tweet_time": tweet_time
                    }
                )
        except Exception as e:
            print(e)

        # すでに保存しているやつをまとめて弾く
        # for tweet in res.txt['statuses'][0]:


        # for tweet in res.txt['statuses']:


        # print(res.text)

    return 0
