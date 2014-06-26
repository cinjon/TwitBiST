What this solves:

You want to search for tweets from certain hashtags on Twitter in a certain time range. Twitter doesn't admit that using its API. So, in order to not hit the query limit, we run a binary search on the full day to get only the range that we want.

How to use it:

1. Get a nice handy twitter client api: ```pip install https://github.com/pabluk/twitter-application-only-auth/archive/master.zip```
2. Retrieve your client with ```client = main.auth(key, secret)```
3. results = main.binary_search_tweet_times(client, start_time=datetime.datetime(...), end_time=datetime.datetime(...), hashtags=['myhashtag'])

How this works:

First, it retrieves the last and first batch of tweets of the day. Then, it uses the max_id of the first and the min_id of the last as start and end ids for running a binary search to find some id which is in the time range. Once it finds that id, it goes to town yielding the tweets.