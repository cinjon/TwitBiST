import requests
import json
import time
from application_only_auth import Client

base_twitter_url = 'https://api.twitter.com/1.1/search/tweets.json'

def get_status(client):
    return client.rate_limit_status()

def auth():
    CONSUMER_KEY = 'z60k8bsColkrv8Ruca0aERHvY'
    CONSUMER_SECRET = 'LMITBL5ITgnJRZeyrsrFOVgWfoKBjeuMcln6cT31unClCKpPQg'
    return Client(CONSUMER_KEY, CONSUMER_SECRET)

def get_client_request(client, query):
    # query is the query to the api, e.g. ?max_id=479405243290386431&q=%23startupschool
    return client.request(base_twitter_url + query)

def get_hashtag_results(client, hashtags, count=100, since_id=None, max_id=None, since=None, until=None):
    # since_id is an optional number representing a tweet id to start from.
    # until is an optional string rep of the date, e.g. "2012-09-01" that will be an open lower bound
    modifiers = {'result_type':'recent', 'count':str(count),
                 'q':'+'.join(['%23' + hashtag for hashtag in hashtags])}

    #Change this to be more pythonic
    if since_id:
        modifiers['since_id'] = since_id
    if max_id:
        modifiers['max_id'] = max_id
    if since:
        modifiers['since'] = since
    if until:
        modifiers['until'] = until

    query = '?' + '&'.join(['%s=%s' % (modifier, modifiers[modifier]) for modifier in modifiers])
    return client.request(query)

def make_num_into_two_char(num):
    str_num = str(num)
    if len(str_num) == 1:
        return '0' + str_num
    return str_num
def make_day(dayt, day_delta):
    return '-'.join([str(dayt.year), make_num_into_two_char(dayt.month),
                     make_num_into_two_char(dayt.day + day_delta)])
def get_datetime_from_tweet(t):
    return datetime.datetime.strptime(t['created_at'], '%a %b %d %H:%M:%S +0000 %Y')

def get_all_tweets_until_end(client, hashtags, since_id, end_time):
    # Free reign to just go at it, getting tweets until we hit the end_time
    # We assume that the since_id is in the right range ... until the end of the request is not
    request = get_hashtag_results(client, hashtags, since_id=since_id)
    tweets = request['statuses']
    results = []

    # Keep adding to results until we fill up on max count groups
    while(len(tweets) > 0 and get_datetime_from_tweet(tweets[-1]) <= end_time):
        results.extend(tweets)
        request = get_hashtag_results(client, hashtags, since_id=tweets[-1]['id_str'])
        tweets = request['statuses']

    # Now put any remainder into results before returning it
    for index in range(len(tweets)):
        tweet = tweets[index]
        if get_datetime_from_tweet(tweet) > end_time:
            break
        results.append(tweet)
    return results

def get_end_results(client, until, start_time, end_time, hashtags):
    # Finds the end results.
    # If end_time in these results, then it goes back in time and gets all of the results.
    # Else it returns the max_id for use with binary search
    end_request = get_hashtag_results(client, hashtags, until=until)
    tweets = end_request['statuses']
    first_end = get_datetime_from_tweet(tweets[0])
    if end_time < first_end:
        # Given end_time is earlier than these tweets.
        return tweets[0]['id_str'], None
    elif first_end >= start_time:
        # The given end_time is later than the earliest of these tweets, so somewhere in this batch is the last one.
        ret = batch_has_valid_tweets(tweets, start_time, end_time)
        ret.extend(get_all_tweets_to_start(client, hashtags, first_end['id_str'], start_time))
        return ret
    else:
        # Somewhere in this batch is the first tweet *and* the last tweet
        return _, batch_has_valid_tweets(tweets, start_time, end_time)

def batch_has_valid_tweets(tweets, start_time, end_time, start_index=0):
    while(start_index < len(tweets)):
        if get_datetime_from_tweet(tweets[start_index]) >= start_time:
            break
        start_index += 1
    end_index = start_index + 1
    while(end_index < len(tweets)):
        if get_datetime_from_tweet(tweets[end_index]) > end_time:
            break
        end_index += 1
    return tweets[start_index, end_index]

def binary_search_tweet_times(client, start_time, end_time, hashtags):
    # {start, end}_time are datetime objects, assumed to be on same day (a conference day)
    # We start by getting the day in question where {start, end} lie.
    # Use that to get 100 at beginning of day (since:) and 100 at end (until:)
    # If in the time horizon, boom, got our max or min, else:
    # we know that the value is between our given ids, so binary search there on both max and min.
    if not until:
        raise

    today = make_day(end_time, 0)
    tomorrow = make_day(end_time, 1)

    start_request = get_hashtag_results(client, hashtags, since=today)
    tweets = start_request['statuses']
    last_start = get_datetime_from_tweet(tweets[-1])
    if start_time > last_start:
        # The given start_time is later these tweets, so we use the max_id of this set as the since_id to binary search
        since_id = tweets[-1]['id_str']
        max_id, end_results = get_end_results(client, tomorrow, start_time, end_time, hashtags)
        if end_results:
            # It turns out the last set had end_time in it, so we just got the results from get_max_id
            return end_results
        return binary_search_tweet_times_helper(client, start_time, end_time, since_id, max_id, hashtags)
    elif last_start <= end_time
        # The given start_time is earlier than the latest of these tweets, so somewhere in this batch is the first one.
        # Put it and all later ones into search_results, then set the last as the since_id and go to town until we hit end_time
        ret = batch_has_valid_tweets(tweets, start_time, end_time)
        ret.extend(get_all_tweets_until_end(client, hashtags, last_start['id_str'], end_time))
        return ret
    else:
        # somewhere in this batch is the first tweet *and* the last tweet.
        return batch_has_all_tweets(tweets, start_time, end_time)

def pretty_print_request(request):
    return json.dumps(request, sort_keys=True, indent=4, separators=(',', ':'))
