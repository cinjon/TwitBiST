import requests
import json
import time
import math
from application_only_auth import Client

base_twitter_url = 'https://api.twitter.com/1.1/search/tweets.json'

def get_status(client):
    return client.rate_limit_status()

def auth():
    CONSUMER_KEY = 'z60k8bsColkrv8Ruca0aERHvY'
    CONSUMER_SECRET = 'LMITBL5ITgnJRZeyrsrFOVgWfoKBjeuMcln6cT31unClCKpPQg'
    return Client(CONSUMER_KEY, CONSUMER_SECRET)

def get_client_request(client, query):
    # query is the query to the api, e.g. ?max_id=12345&q=%23startupschool
    return client.request(base_twitter_url + query)

def get_hashtag_results(client, hashtags, count=100, **kwargs):
    # example kwargs: since_id=None, max_id=None, since=None, until=None):
    # since_id is an optional number representing a tweet id to start from.
    # until is an optional string rep of the date, e.g. "2012-09-01" that will be an open lower bound
    modifiers = {'result_type':'recent', 'count':str(count),
                 'q':'+'.join(['%23' + hashtag for hashtag in hashtags])}
    for key in kwargs:
        modifiers[key] = kwargs[key]
    query = '?' + '&'.join(['%s=%s' % (modifier, modifiers[modifier]) for modifier in modifiers])
    return get_client_request(client, query)

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
    results.extend([tweet for tweet in tweets if get_datetime_from_tweet(tweet) <= end_time])
    return results

def get_all_tweets_to_start(client, hashtags, max_id, start_time):
    # Free reign to just go at it, getting tweets going down until we reach start_time
    # We assume that the max_id is in the right range ... until the beginning of the request is not
    request = get_hashtag_results(client, hashtags, max_id=max_id)
    tweets = request['statuses']
    results = []

    # Keep adding to results until we fill up on max count groups
    while(len(tweets) > 0 and get_datetime_from_tweet(tweets[0]) >= start_time):
        results.extend(tweets)
        request = get_hashtag_results(client, hashtags, max_id=tweets[0]['id_str'])
        tweets = request['statuses']

    # Now put any remainder left over into results before returning it
    results.extend([tweet for tweet in tweets if get_datetime_from_tweet(tweet) >= start_time])
    return results

def get_batch_valid_tweets(tweets, start_time, end_time, start_index=0):
    # Find the first index where the tweet time is >= start_time
    while(start_index < len(tweets)):
        if get_datetime_from_tweet(tweets[start_index]) >= start_time:
            break
        start_index += 1
    end_index = start_index + 1
    # Find the last index when tweet time is <= end_time
    while(end_index < len(tweets)):
        if get_datetime_from_tweet(tweets[end_index]) > end_time:
            break
        end_index += 1
    return tweets[start_index, end_index]

def binary_search_tweet_times(client, start_time, end_time, hashtags):
    # {start, end}_time are datetime objects, assumed to be on same day (a conference day)
    # We start by getting the day in question where {start, end} lie.
    # Use that to get 100 at beginning of day (since:) and 100 at end (until:)
    # Run a binary search on those with since_id=beg[0][id] and max_id=end[-1][id]
    if not start_time or not end_time or not hashtags:
        raise
    today = make_day(end_time, 0)
    tomorrow = make_day(end_time, 1)
    start_request = get_hashtag_results(client, hashtags, since=today)
    end_request = get_hashtag_results(client, hashtags, until=tomorrow)
    return binary_search_tweet_times_helper(
        client, start_time, end_time, hashtags,
        start_request['statuses'][0]['id'], end_request['statuses'][-1]['id'])

def binary_search_tweet_times_helper(client, start_time, end_time, hashtags, since_id, max_id):
    print "Since_id: %s, Max_id: %s" % (since_id, max_id)
    if since_id >= max_id:
        print "bailing, since_id >= max_id"
        return []
    avg_id = int((since_id + max_id)/2)
    request = get_hashtag_results(client, hashtags, max_id=avg_id) # BST
    tweets = request['statuses']
    last_tweet_time = get_datetime_from_tweet(tweets[-1])
    first_tweet_time = get_datetime_from_tweet(tweets[0])

    if last_tweet_time < start_time:
        # this set is too early
        print "BST down"
        return binary_search_tweet_time_helper(client, start_time, end_time, avg_id, max_id, hashtags)
    elif first_tweet_time > end_time:
        # this set is too late
        print "BST up"
        return binary_search_tweet_time_helper(client, start_time, end_time, start_id, avg_id, hashtags)
    elif last_tweet_time <= end_time and first_tweet_time >= start_time:
        # this set is contained in the range
        # add all in set to the tweets. Then go to town on the min_id and the max_id
        print "Set contained in the range"
        ret = tweets
        ret.extend(get_all_tweets_to_start(client, hashtags, tweets[0]['id_str'], start_time))
        ret.extend(get_all_tweets_until_end(client, hashtags, tweets[-1]['id_str'], end_time))
        return ret
    elif last_tweet_time <= end_time:
        # somewhere in (first_tweet, last_tweet] is the start.
        # get everything in that range and then do get_all_tweets_until_end
        print "Set half in range, getting all until end"
        ret = get_batch_valid_tweets(tweets, start_time, end_time)
        ret.extend(get_all_tweets_until_end(client, hashtags, tweets[-1]['id_str'], end_time))
        return ret
    elif last_tweet_time > end_time:
        # somewhere in [first_tweet, last_tweet) is the end.
        # get everything in that range and then do get_all_tweets_to_start
        print "Set half in range, getting all to start"
        ret = get_batch_valid_tweets(tweets, start_time, end_time)
        ret.extend(get_all_tweets_to_start(client, hashtags, tweets[0]['id_str'], start_time))
        return ret
    else:
        print "How did I get to else?"
        print "Start Time: %s, End Time: %s, Since ID: %s, Max ID: %s" % (start_time, end_time, since_id, max_id)
        return []

def pretty_print_request(request):
    return json.dumps(request, sort_keys=True, indent=4, separators=(',', ':'))
