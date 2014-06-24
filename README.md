How the relevant twitter api works:

Search for hashtag 'startupschool' with most recent results at the end and ending at day <until>
import main; client = main.auth(); results = main.get_hashtag_results(client, ['startupschool'], until='2014-06-19')
https://api.twitter.com/1.1/search/tweets.json?q=%23startupschool&count=100&result_type=recent&until=2014-06-19

that then yields the next set of results at results['search_metadata']['next_results']
