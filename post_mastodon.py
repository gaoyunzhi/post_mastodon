#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import plain_db
import cached_url
from telegram_util import isCN, isUrl, removeOldFiles
from telepost import getPendingPosts, getPost, getImages, getRawText, exitTelethon
from telegram_util import matchKey
import copy
import time
import yaml
import random
import itertools
import export_to_telegraph
from bs4 import BeautifulSoup
from mastodon import Mastodon

existing = plain_db.load('existing')
with open('db/setting') as f:
    setting = yaml.load(f, Loader=yaml.FullLoader)

with open('credential') as f:
    credential = yaml.load(f, Loader=yaml.FullLoader)

Day = 24 * 60 * 60

def replaceTelegraphUrl(url):
    if 'telegra.ph' not in url:
        return url
    if not url.startswith('http'):
        url = 'https://' + url
    soup = BeautifulSoup(cached_url.get(url, force_cache=True), 'html.parser')
    try:
        return soup.find('address').find('a')['href']
    except:
        return url

async def getText(channel, post, key):
    text, post = await getRawText(channel, post.post_id)
    for entity in post.entities or []:
        origin_text = ''.join(text[entity.offset:entity.offset + entity.length])
        to_replace = entity.url if hasattr(entity, 'url') else origin_text
        # to_replace = replaceTelegraphUrl(to_replace) # see if needed
        text[entity.offset] = to_replace
        if entity.offset + entity.length == len(text) and origin_text == 'source':
            text[entity.offset] = '\n\n' + to_replace
        for index in range(entity.offset + 1, entity.offset + entity.length):
            if text[index] != '\n':
                text[index] = ''
    text = ''.join(text)
    text = '\n'.join([line.strip() for line in text.split('\n')]).strip()
    return text or key

async def getMediaIds(mastodon, channel, post):
    video = post.getVideo()
    media_ids = []
    if video:
        cached_url.get(video, mode='b', force_cache=True)
        media_ids.append(mastodon.media_post(cached_url.getFilePath(video))['id'])
    img_number = post.getImgNumber()
    if img_number:
        fns = await getImages(channel, post.post_id, img_number)
        for fn in fns:
            media_ids.append(mastodon.media_post(fn)['id'])
    return media_ids[:4]

async def postImp(mastodon, channel, post, key):
    post_text = await getText(channel, post, key)
    media_ids = await getMediaIds(mastodon, channel, post)
    if not media_ids:
        mastodon.status_post(post_text, media_ids=media_ids)
        return
    for sleep_time in range(3, 18, 5):
        time.sleep(sleep_time)
        try:
            mastodon.status_post(post_text, media_ids=media_ids)
            return
        except Exception as e:
            if not matchKey(str(e), ['不能附加还在处理中的文件']):
                raise e

def getPostFromPending(posts):
    posts = list(itertools.islice(posts, 100))
    posts = [(post.time + random.random(), post) for post in posts]
    posts.sort()
    if not posts:
        return
    if posts[0][0] < time.time() - Day * 2:
        return posts[0][1]
    for post in posts:
        # if post[1].post_id != 128801: # testing
        #     continue
        if random.random() > 0.02:
            continue
        return post[1]

async def runImp():
    removeOldFiles('tmp', day=0.1)
    items = list(setting['channel_map'].items())
    random.shuffle(items)
    for channel, mastodon_name in items:
        sub_setting = setting['setting_map'].get(channel, {})
        mastodon = Mastodon(
            access_token = 'db/%s_mastodon_secret' % mastodon_name,
            api_base_url = credential['mastodon_domain']
        )
        posts = getPendingPosts(channel, existing, 
            max_time=time.time() + Day * sub_setting.get('max_time', -0.05),
            min_time=time.time() + Day * sub_setting.get('min_time', -10))
        post = getPostFromPending(posts)
        if not post:
            continue
        key = 'https://t.me/' + post.getKey()
        try:
            result = await postImp(mastodon, channel, post, key)
            existing.update(key, 1)
        except Exception as e:
            print('post_mastodon', key, e)
            if matchKey(str(e), ['Text超过了 1000 字的限制']): 
                existing.update(key, -1)
                continue
            raise e
        return

async def run():
    await runImp()
    await exitTelethon()
        
if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    r = loop.run_until_complete(run())
    loop.close()