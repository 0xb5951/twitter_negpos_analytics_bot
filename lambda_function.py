
# 並列処理
import threading
import os
import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime as dt
import datetime
import requests
from decimal import Decimal

from requests_oauthlib import OAuth1Session  # OAuthのライブラリの読み込み

# twitterAPIアクセストークン
CK = os.environ["twitter_CK"]
CS = os.environ["twitter_CS"]
AT = os.environ["twitter_AT"]
ATS = os.environ["twitter_ATS"]

NLP_Key = os.environ["NLP_Key"]

Dynamo_table = os.environ["Dynamo_table"]

Slack_channel = os.environ["Slack_channel"]
Slack_post_user = os.environ["Slack_post_user"]

MONTH_LUT = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

# 基準日からのツイートデータを取得する


def get_tweet_data(ref_day):
    try:
        dynamoDB = boto3.resource("dynamodb")
        table = dynamoDB.Table(Dynamo_table)  # DynamoDBのテーブル名

        dynamo_data = table.query(
            IndexName='search_query-tweet_time-index',
            KeyConditionExpression=Key("search_query").eq(
                'ランサーズ') & Key("tweet_time").gt(ref_day)
        )

        return dynamo_data
    except Exception as e:
        print(e)

# ツイートデータをDynamoDBに保存する


def save_tweet_data(tweet, score, abs_score):
    preform_date = dt.strptime(date_translate(
        tweet['created_at']), '%Y-%m-%d %H:%M:%S')
    tweet_time = Decimal(preform_date.timestamp())
    tweet_link = "https://twitter.com/{0}/status/{1}".format(
        tweet['user']['screen_name'], tweet['id_str'])

    # pos 1, neg -1, default 0
    negpos_flag = 0

    if abs_score > 1:
        if score >= 0:
            negpos_flag = 1
        else:
            negpos_flag = -1

    # ツイートデータを保存する
    try:
        dynamoDB = boto3.resource("dynamodb")
        table = dynamoDB.Table(Dynamo_table)  # DynamoDBのテーブル名

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
                "post_status": 0
            }
        )
    except Exception as e:
        print(e)
        # forで回すことを前提としているので、エラーを返す
        raise Exception('Error!')

    return 0


# 1日二回決まった時間にslackにpostする
def post_slack(neg_tweets, pos_tweets):
    if pos_tweets == "":
        pos_tweets = "今回通知分はないよ\n"
    if neg_tweets == "":
        neg_tweets = "今回通知分はないよ\n"

    post_text = "<@{0}>\n■ポジティブ\n {1} \n\n■ネガティブ\n{2}".format(
        Slack_post_user, pos_tweets, neg_tweets)

    SLACK_WEBHOOK = os.environ["Slack_webhook"]
    # ツイートデータをslackに投げる
    payload_dic = {
        "text": post_text,
        "username": "twitterネガポジ分析",
        "unfurl_links": False,
        "channel": "#gr_cc_twitter対応",
    }

    r = requests.post(SLACK_WEBHOOK, data=json.dumps(payload_dic))
    return r


# Slackに投稿したデータに対してフラグを立てる。
def set_post_flag(tweet_data):
    dynamoDB = boto3.resource("dynamodb")
    table = dynamoDB.Table(Dynamo_table)  # DynamoDBのテーブル名

    for tweet in tweet_data['Items']:
        try:
            res = table.update_item(
                Key={
                    'tweet_id': str(tweet['tweet_id'])
                },
                UpdateExpression='SET post_status = :f',
                ExpressionAttributeValues={
                    ':f': Decimal(1)
                }
            )
        except Exception as e:
            print(e)

    return 0

# Slackに投稿するデータのみを抽出する


def setup_post_data():
    try:
        dynamoDB = boto3.resource("dynamodb")
        table = dynamoDB.Table(Dynamo_table)  # DynamoDBのテーブル名

        pos_date = table.query(
            IndexName='post_status-negpos_status-index',
            KeyConditionExpression=Key("post_status").eq(
                0) & Key("negpos_status").eq(1)
        )

        neg_date = table.query(
            IndexName='post_status-negpos_status-index',
            KeyConditionExpression=Key("post_status").eq(
                0) & Key("negpos_status").eq(-1)
        )

        return pos_date, neg_date
    except Exception as e:
        print(e)

# twitterからとってきたデータの日付を整える


def date_translate(date):
    pre_date = date.split(' ')
    y = pre_date[-1]
    m = MONTH_LUT[pre_date[1]]
    d = pre_date[2]
    time = pre_date[3]
    res_date = '{}-{}-{} {}'.format(y, m, d, time)
    return res_date


def lambda_function(event, content):
    twitter = OAuth1Session(CK, CS, AT, ATS)  # 認証処理
    query = os.environ["query"]
    # twitter検索結果取得エンドポイント
    url = 'https://api.twitter.com/1.1/search/tweets.json'

    # ランサーズが含まれる今日のツイートを取得する
    since = dt.now()
    query += " since:" + since.strftime("%Y-%m-%d")
    res = twitter.get(url, params={
        'q': query,
        'result_type': 'recent',
        'count': 100
    }
    )

    if res.status_code == 200:
        now = dt.now()
        # 時刻データ 測定時 12:00 出力値 03:00:19.908117
        check_time = str(now.strftime("%H")) + str(now.strftime("%M"))
        # print(check_time)

        res_text = json.loads(res.text)

        #NLPAPI
        nlp_url = 'https://language.googleapis.com/v1/documents:analyzeSentiment?key=' + NLP_Key

        header = {'Content-Type': 'application/json'}
        body = {
            "document": {
                "type": "PLAIN_TEXT",
                "language": "ja",
                "content": ""
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
            try:
                body['document']['content'] = tweet['text']
                response = requests.post(
                    nlp_url, headers=header, json=body).json()
            except Exception as e:
                print(e)
                continue

            score = response['documentSentiment']['score']
            abs_score = response['documentSentiment']['magnitude']

            try:
                save_tweet_data(tweet, score, abs_score)
            except Exception as e:
                print(e)
                continue

        # 9時と18時にslackに投稿する. UTCなので、0時0分と9時0分。
        if check_time == '0000' or check_time == '0900':
            pos_data, neg_data = setup_post_data()

            pos_tweets = ""
            neg_tweets = ""

            for pos_tweet in pos_data['Items']:
                pos_tweets += "*ツイートデータ*\n" \
                              "ネガポジスコア : {0} \n" \
                              "絶対スコア : {1} \n" \
                              "ツイートユーザ: https://twitter.com/{2}\n\n" \
                              "ツイート本文: \n```{3}```\n {4}\n\n".format(
                                  str(pos_tweet['negpos']),
                                  str(pos_tweet['abs_score']),
                                  pos_tweet['tweet_user'],
                                  pos_tweet['tweet_text'],
                                  pos_tweet['tweet_link']
                              )

            for neg_tweet in neg_data['Items']:
                neg_tweets += "*ツイートデータ*\n" \
                              "ネガポジスコア : {0} \n" \
                              "絶対スコア : {1} \n" \
                              "ツイートユーザ: https://twitter.com/{2} \n\n" \
                              "ツイート本文: \n```{3}```\n {4}\n\n".format(
                                  str(neg_tweet['negpos']),
                                  str(neg_tweet['abs_score']),
                                  neg_tweet['tweet_user'],
                                  neg_tweet['tweet_text'],
                                  neg_tweet['tweet_link']
                              )

            post_slack(neg_tweets, pos_tweets)

            # 投稿したtweetデータのSlack通知フラグを立てる
            set_post_flag(neg_data)
            set_post_flag(pos_data)

    return 0
