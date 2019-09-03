import re
from requests_html import HTMLSession, HTML
from datetime import datetime
from urllib.parse import quote
from lxml.etree import ParserError
import mechanicalsoup

session = HTMLSession()

browser = mechanicalsoup.StatefulBrowser()
browser.addheaders = [('User-agent', 'Firefox')]

def get_tweets(query, pages=25):
    """Gets tweets for a given user, via the Twitter frontend API."""

    after_part = f'include_available_features=1&include_entities=1&include_new_items_bar=true'
    if query.startswith('#'):
        query = quote(query)
        url = f'https://twitter.com/i/search/timeline?f=tweets&vertical=default&q={query}&src=tyah&reset_error_state=false&'
    else:
        url = f'https://twitter.com/i/profiles/show/{query}/timeline/tweets?'
    url += after_part
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': f'https://twitter.com/{query}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8',
        'X-Twitter-Active-User': 'yes',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept-Language': 'en-US'
    }

    def gen_tweets(pages):
        r = session.get(url, headers=headers)

        while pages > 0:
            try:
                html = HTML(html=r.json()['items_html'],
                            url='bunk', default_encoding='utf-8')
            except KeyError:
                raise ValueError(
                    f'Oops! Either "{query}" does not exist or is private.')
            except ParserError:
                break

            comma = ","
            dot = "."
            tweets = []
            for tweet in html.find('.stream-item'):
                # 10~11 html elements have `.stream-item` class and also their `data-item-type` is `tweet`
                # but their content doesn't look like a tweet's content
                try:
                    text = tweet.find('.tweet-text')[0].full_text
                except IndexError:  # issue #50
                    continue

                tweet_id = tweet.attrs['data-item-id']

                time = datetime.fromtimestamp(int(tweet.find('._timestamp')[0].attrs['data-time-ms']) / 1000.0)

                interactions = [
                    x.text
                    for x in tweet.find('.ProfileTweet-actionCount')
                ]

                replies = int(
                    re.sub('\D', '', interactions[0].split(" ")[0]
                          )
                )
                
                retweets = int(
                    re.sub('\D', '', interactions[1].split(" ")[0]
                          )
                )
                likes = int(
                    re.sub('\D', '', interactions[2].split(" ")[0]
                          )
                )

                hashtags = [
                    hashtag_node.full_text
                    for hashtag_node in tweet.find('.twitter-hashtag')
                ]
                urls = [
                    url_node.attrs['data-expanded-url']
                    for url_node in tweet.find('a.twitter-timeline-link:not(.u-hidden)')
                ]
                photos = [
                    photo_node.attrs['data-image-url']
                    for photo_node in tweet.find('.AdaptiveMedia-photoContainer')
                ]

                is_retweet = True if tweet.find('.js-stream-tweet')[0].attrs.get('data-retweet-id', None) \
                    else False

                videos = []
                video_nodes = tweet.find(".PlayableMedia-player")
                for node in video_nodes:
                    styles = node.attrs['style'].split()
                    for style in styles:
                        if style.startswith('background'):
                            tmp = style.split('/')[-1]
                            video_id = tmp[:tmp.index('.jpg')]
                            videos.append({'id': video_id})

                tweets.append({
                    'tweetId': tweet_id,
                    'isRetweet': is_retweet,
                    'time': time,
                    'text': text,
                    'replies': replies,
                    'retweets': retweets,
                    'likes': likes,
                    'entries': {
                        'hashtags': hashtags, 'urls': urls,
                        'photos': photos, 'videos': videos
                    }
                })

            last_tweet = html.find('.stream-item')[-1].attrs['data-item-id']

            for tweet in tweets:
                if tweet:
                    tweet['text'] = re.sub(r'\Shttp', ' http', tweet['text'], 1)
                    tweet['text'] = re.sub(r'\Spic\.twitter', ' pic.twitter', tweet['text'], 1)
                    yield tweet

            r = session.get(url, params={'max_position': last_tweet}, headers=headers)
            pages += -1

    yield from gen_tweets(pages)

def search_tweet(query):
    def FindUsername(doit):
        tmp = doit.find('username u-dir')
        return doit[tmp+66:tmp+66+doit[tmp+66:].find('<')]

    def FindScreenname(doit):
        keyword = 'data-name='
        tmp2 = doit.find('data-name=')
        return doit[tmp2+len(keyword)+1:tmp2+len(keyword)+1+doit[tmp2+len(keyword)+1:].find('"')]    

    def FindContent(doit):
        keyword = 'TweetTextSize'
        tmp2 = doit.find(keyword)
        withAhref = doit[tmp2+len(keyword)+63:tmp2+len(keyword)+63+doit[tmp2+len(keyword)+63:].find('<\\/p>')].replace("<strong>","").replace("<\\/strong>","")
        result = re.sub(r'<a href=.+dir="ltr" >',"",withAhref).replace('<s>',"").replace('<\\/s>',"").replace('<b>',"").replace('<\\/b>',"").replace('<\\/a>'," ")
        result = re.sub(r'<img class=.+>',"",result)
        return result
    url = 'https://twitter.com/i/search/timeline?vertical=default&q='+'&src=typd&composed_count=0&include_available_features=1&include_entities=1&include_new_items_bar=true&interval=30000&latent_count=0'
    got = session.get(query)

    decoded = str(got.text).encode().decode('unicode-escape')

    main_part = decoded[decoded.find('<li class="js-stream-item stream-item stream-item\n"'):]

    singles = []

    while main_part.find('js-stream-item stream-item stream-item') != -1:
        use = main_part.find('<\\/div>\n\n  <\\/div>\n\n\n\n<\\/li>\n')+29
        singles.append(main_part[:use])
        main_part = main_part[use:]
    result = []
    for each in singles:
        single_result = {}
        single_result["screen_name"] = FindScreenname(each)
        single_result["username"] = FindUsername(each)
        single_result["content"] = FindContent(each)
    return result