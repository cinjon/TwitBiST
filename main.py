import requests
import json
import math
import datetime
import pytz
from application_only_auth import Client

base_twitter_url = 'https://api.twitter.com/1.1/search/tweets.json'

#############################
### Twitter API Functions ###
#############################

def auth(key, secret):
    return Client(key, secret)

def get_client_request(client, query):
    # query is the query to the api, e.g. ?max_id=12345&q=%23startupschool
    return client.request(base_twitter_url + query)

def get_hashtag_results(client, hashtags, count=100, **kwargs):
    # example kwargs: since_id=None, max_id=None, since=None, until=None
    # since_id is an optional number representing a tweet id to start from.
    # until is an optional string rep of the date, e.g. "2012-09-01" that will be an open lower bound
    modifiers = {'result_type':'recent', 'count':str(count),
                 'q':'+'.join(['%23' + hashtag for hashtag in hashtags])}
    for key in kwargs:
        modifiers[key] = str(kwargs[key])
    query = '?' + '&'.join(['%s=%s' % (modifier, modifiers[modifier]) for modifier in modifiers])
    return get_client_request(client, query)

def get_next_tweets_from_metadata(client, search_metadata):
    request = None
    if 'next_results' in search_metadata:
        request = get_client_request(client, search_metadata['next_results'])
        if request:
            return request, request.get('statuses', None)
    return request, None

def get_status(client):
    return client.rate_limit_status()

#############################
###   Utility Functions   ###
#############################

def get_datetime_from_tweet(t):
    return datetime.datetime.strptime(t['created_at'], '%a %b %d %H:%M:%S +0000 %Y')

def is_in_range(tweet, since_id, max_id, start_time, end_time):
    return tweet['id'] >= since_id and tweet['id'] <= max_id and get_datetime_from_tweet(tweet) >= start_time and get_datetime_from_tweet(tweet) <= end_time

def make_day(dayt, day_delta):
    return '-'.join([str(dayt.year), make_num_into_two_char(dayt.month),
                     make_num_into_two_char(dayt.day + day_delta)])

def make_num_into_two_char(num):
    str_num = str(num)
    if len(str_num) == 1:
        return '0' + str_num
    return str_num

def pretty_print_request(request):
    return json.dumps(request, sort_keys=True, indent=4, separators=(',', ':'))

#############################
###  Search and Retrieve  ###
#############################

def binary_search_tweet_times(client, start_time, end_time, hashtags):
    # {start, end}_time are datetime objects, assumed to be on same day (a conference day)
    # We start by getting the day in question where {start, end} lie.
    # Use that to get 100 at beginning of day (since:) and 100 at end (until:)
    # Run a binary search on those with since_id=beg[0][id] and max_id=end[-1][id]
    if not start_time or not end_time or not hashtags:
        raise
    start_day = make_day(start_time, 0)
    end_day = make_day(end_time, 1)

    # Get the last from yesterday and the last from today as our start and end requests
    # TODO: It may be that the last from yesterday doesn't exist.
    start_request = get_hashtag_results(client, hashtags, until=start_day)
    end_request = get_hashtag_results(client, hashtags, until=end_day)
    return binary_search_tweet_times_helper(
        client, start_time, end_time, hashtags,
        start_request['statuses'][0]['id'], end_request['statuses'][0]['id'])

def binary_search_tweet_times_helper(client, start_time, end_time, hashtags, since_id, max_id):
    if since_id >= max_id:
        print "Bailing: since_id >= max_id"
        return []
    avg_id = int((since_id + max_id)/2)
    request = get_hashtag_results(client, hashtags, max_id=avg_id) # BST
    tweets = request['statuses']
    last_tweet_time = get_datetime_from_tweet(tweets[0]) # Most recent is first
    first_tweet_time = get_datetime_from_tweet(tweets[-1])

    if last_tweet_time < start_time:
        # this set is too early
        print "BST up"
        return binary_search_tweet_times_helper(client, start_time, end_time, hashtags, avg_id, max_id)
    elif first_tweet_time > end_time:
        # this set is too late
        print "BST down"
        return binary_search_tweet_times_helper(client, start_time, end_time, hashtags, start_id, avg_id)
    elif last_tweet_time <= end_time and first_tweet_time >= start_time:
        # this set is contained in the range
        # add all in set to the tweets. Then go to town on the min_id and the max_id
        print "Set contained in the range"
        ret = tweets
        # Going down works no problem because at this point we have a max id (the tweet here) and can just progress using next_results
        ret.extend(get_all_tweets(
            client, hashtags, since_id, tweets[-1]['id'], start_time, end_time))
        # Going up doesn't work as well because our max_id is potentially outside of the time range. BS again.
        ret.extend(binary_search_tweet_times_helper(
            client, start_time, end_time, hashtags, tweets[0]['id'], max_id))
        return ret
    elif last_tweet_time <= end_time:
        # The start is in (first_tweet, last_tweet].
        # get everything in that range and then get all tweets going up
        print "Set half in range, getting all until end"
        ret = get_batch_valid_tweets(tweets, start_time, end_time)
        ret.extend(binary_search_tweet_times_helper(
            client, start_time, end_time, hashtags, tweets[0]['id'], max_id))
        return ret
    elif last_tweet_time > end_time:
        # The end is in [first_tweet, last_tweet).
        # get everything in that range and then get all tweets going down
        print "Set half in range, getting all to start"
        ret = get_batch_valid_tweets(tweets, start_time, end_time)
        ret.extend(get_all_tweets(
            client, hashtags, since_id, tweets[-1]['id'], start_time, end_time))
        return ret
    else:
        print "How did I get to here? This is an error"
        print "Start Time: %s, End Time: %s, Since ID: %s, Max ID: %s" % (start_time, end_time, since_id, max_id)
        return []

def get_all_tweets(client, hashtags, since_id, max_id, start_time, end_time):
    request = get_hashtag_results(client, hashtags, since_id=since_id, max_id=max_id)
    tweets = request['statuses']
    results = []

    # Keep adding to results until we fill up on max count groups
    while(len(tweets) > 0 and is_in_range(tweets[0], since_id, max_id, start_time, end_time) and is_in_range(tweets[-1], since_id, max_id, start_time, end_time)):
        print 'Adding from time %s to time %s' % (get_datetime_from_tweet(tweets[-1]),
                                                  get_datetime_from_tweet(tweets[0]))
        results.extend(tweets)
        request, tweets = get_next_tweets_from_metadata(client, request['search_metadata'])
        if not tweets:
            break

    # Now put any remainder into results before returning it
    if not tweets:
        return results
    extra_tweets = [tweet for tweet in tweets if is_in_range(tweet, since_id, max_id, start_time, end_time)]
    if extra_tweets:
        print 'Extending %d many with %d many more from time %s to %s' % (len(results), len(extra_tweets),
                                                                          get_datetime_from_tweet(extra_tweets[-1]),
                                                                          get_datetime_from_tweet(extra_tweets[0]))
        results.extend(extra_tweets)

    return results

def get_batch_valid_tweets(tweets, start_time, end_time):
    datetimes = [get_datetime_from_tweet(tweet) for tweet in tweets]
    return [tweet for index, tweet in enumerate(tweets) if datetimes[index] >= start_time and datetimes[index] <= end_time]
