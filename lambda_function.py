
# 並列処理
import threading
import os
import json
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime as dt
import datetime
import requests
from decimal import Decimal

from requests_oauthlib import OAuth1Session  # OAuthのライブラリの読み込み

# ネガポジ閾値
# negpos_threshold = int(os.environ["negpos_threshold"])
# Slack通知先
# slack_room = os.environ["slack_chanel"]

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

# 基準日からのツイートデータを取得する
def get_tweet_data(ref_day):
    try:
        dynamoDB = boto3.resource("dynamodb")
        table = dynamoDB.Table("twitter_negpos")  # DynamoDBのテーブル名

        dynamo_data = table.query(
            IndexName='search_query-tweet_time-index',
            KeyConditionExpression=Key("search_query").eq('ランサーズ') & Key("tweet_time").gt(ref_day)
        )

        return dynamo_data
    except Exception as e:
        print(e)

# 1日二回決まった時間にslackにpostする
def post_slack(neg_tweets, pos_tweets):
    if pos_tweets == "":
        pos_tweets = "今回通知分はないよ\n"
    if neg_tweets == "":
        neg_tweets = "今回通知分はないよ\n"

    post_text = "テスト\n" + "■ポジティブ\n" + pos_tweets + "\n\n■ネガティブ\n" + neg_tweets

    SLACK_WEBHOOK = "https://hooks.slack.com/services/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"
    # ツイートデータをslackに投げる
    payload_dic = {
        "text": post_text,
        "username": "twitterネガポジ分析",
        "unfurl_links": False,
        "channel": "#gr_cc_twitter対応",
    }

    r = requests.post(SLACK_WEBHOOK, data=json.dumps(payload_dic))


# Slackに投稿したデータに対してフラグを立てる。
# def set_post_flag(tweet_id):

# Slackに投稿するデータのみを抽出する
# def setup_post_data():
#     try:
#         dynamoDB = boto3.resource("dynamodb")
#         table = dynamoDB.Table("twitter_negpos")  # DynamoDBのテーブル名

#         dynamo_data = table.query(
#             IndexName='search_query-tweet_time-index',
#             KeyConditionExpression=Key("search_query").eq(
#                 'ランサーズ') & Key("tweet_time").gt(ref_day)
#         )

#         return dynamo_data
#     except Exception as e:
#         print(e)

# twitterからとってきたデータの日付を整える
def date_translate(date):
    pre_date = date.split(' ')
    y = pre_date[-1]
    m = MONTH_LUT[pre_date[1]]
    d = pre_date[2]
    time = pre_date[3]
    res_date = '{}-{}-{} {}'.format(y, m, d, time)
    return res_date

def main_func(event, content):
    twitter = OAuth1Session(CK, CS, AT, ATS)  #認証処理
    query = os.environ["query"]
    # twitter検索結果取得エンドポイント
    url = 'https://api.twitter.com/1.1/search/tweets.json'

    # ランサーズが含まれる今日のツイートを取得する
    since = dt.now()
    query += " since:" + since.strftime("%Y-%m-%d")
    res = twitter.get(url, params={'q': query})

    if res.status_code == 200:
        res_text = json.loads(res.text)
        print(res_text)

        #NLPAPI
        nlp_url = 'https://language.googleapis.com/v1/documents:analyzeSentiment?key=' + NLP_Key

        header = {'Content-Type': 'application/json'}
        body = {
            "document": {
                "type": "PLAIN_TEXT",
                "language": "ja",
                "content" : ""
            },
            "encodingType": "UTF8"
        }
        # response = requests.post(nlp_url, headers=header, json=body).json()

        # 基準となる日からのツイートデータをとってくる
        ref_day = Decimal(since.timestamp())
        dynamo_data = get_tweet_data(ref_day)

        pos_tweet = ""
        neg_tweet = ""

        # すでにデータが保存されているツイート
        tweet_ids = []
        for d_tweet in dynamo_data['Items']:
            tweet_ids.append(d_tweet['tweet_id'])

        # # 検知済みのツイートを弾く
        for tweet in res_text['statuses']:
            if tweet['id_str'] in tweet_ids:
                continue

            # この下でgoogle NLP叩く
            body['document']['content'] = tweet['text']
            response = requests.post(nlp_url, headers=header, json=body).json()

            score = response['documentSentiment']['score']
            abs_score = response['documentSentiment']['magnitude']
            tweet_link = "https://twitter.com/" + tweet['user']['screen_name'] + "/status/" + tweet['id_str']

            # pos 1, neg -1, default 0
            negpos_flag = 0

            if abs_score > 1:
                if score > 0:
                    negpos_flag = 1
                    pos_tweet += "**ツイートデータ**" + '\n'
                    pos_tweet += "ネガポジスコア :" + str(score) + '\n'
                    pos_tweet += "絶対スコア :" + str(abs_score) + '\n'
                    pos_tweet += "ツイートユーザ: https://twitter.com/" + tweet['user']['screen_name'] + '\n\n'
                    pos_tweet += "ツイート本文: \n```" + tweet['text'] + '```\n'
                    pos_tweet += tweet_link + "\n\n"

                if score <= 0:
                    negpos_flag = -1
                    neg_tweet += "**ツイートデータ**" + '\n'
                    neg_tweet += "ネガポジスコア :" + str(score) + '\n'
                    neg_tweet += "絶対スコア :" + str(abs_score) + '\n'
                    neg_tweet += "ツイートユーザ: https://twitter.com/" + tweet['user']['screen_name'] + '\n\n'
                    neg_tweet += "ツイート本文: \n```" + tweet['text'] + '```\n'
                    neg_tweet += tweet_link + "\n\n"

            # ツイートデータを保存する
            try:
                dynamoDB = boto3.resource("dynamodb")
                table = dynamoDB.Table("twitter_negpos")  # DynamoDBのテーブル名

                preform_date = dt.strptime(date_translate(tweet['created_at']), '%Y-%m-%d %H:%M:%S')
                tweet_time = Decimal(preform_date.timestamp())

                # 昨日からのツイートデータをとってくる
                res = table.put_item(
                    Item={
                        "tweet_id": str(tweet['id_str']),
                        "search_query": "ランサーズ",
                        'abs_score': Decimal(str(abs_score)),
                        "negpos": Decimal(str(score)),
                        "tweet_text": tweet['text'],
                        "tweet_user": tweet['user']['screen_name'],
                        "tweet_time": tweet_time,
                        "tweet_link": tweet_link,
                        "negpos_status": negpos_flag,
                        "post_status" : 0
                    }
                )
            except Exception as e:
                print(e)

    return 0
