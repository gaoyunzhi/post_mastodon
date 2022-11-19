#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import plain_db
import cached_url
from telegram_util import isCN, isUrl, removeOldFiles
from reddit_2_album import reddit
from telepost import getPendingPosts, getPost, getImages, getRawText, exitTelethon
from praw.models import InlineImage, InlineVideo
from telegram_util import matchKey
import copy
import time
import yaml
import random
import itertools
import export_to_telegraph
from bs4 import BeautifulSoup

reddit.validate_on_submit = True
existing = plain_db.load('existing')
with open('db/setting') as f:
    setting = yaml.load(f, Loader=yaml.FullLoader)

Day = 24 * 60 * 60

def shouldRemoveLine(channel, line):
    if not line.strip():
        return True
    if channel == 'translate_img':
        for pivot in ['翻译：', '原文：']:
            if line.startswith(pivot):
                return True
    return False

def getTitle(url):
    if not url.startswith('http'):
        url = 'https://' + url
    return '【%s】' % export_to_telegraph.getTitle(url)

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

def getCore(channel, post_text):
    lines = post_text.split('\n')
    if len(lines) == 1:
        return post_text
    if isUrl(lines[-1]) and len(lines[-1].split()) == 1:
        lines = lines[:-1]
    lines = [line.strip() for line in lines if not shouldRemoveLine(channel, line)]
    if len(lines) >= 4 and len(''.join(lines)) > 100:
        return 
    result = '　'.join(lines)
    for char in '。！？，；':
        result = result.replace(char + '　', char)
    if isUrl(result) and len(result.split()) == 1:
        return getTitle(result)
    return result

def postAsGallery(subreddit, core, fns, key): 
    if len(fns) == 1:
        return subreddit.submit_image(core, fns[0])
    images = [{"image_path": fn, "outbound_url": key} for fn in fns]
    return subreddit.submit_gallery(core, images)

def splitText(text):
    lines = text.split('\n')
    title = lines[0]
    rest = lines[1:]
    if len(title) > 300:
        for splitter in ['。', '.']:
            try:
                title, suffix = text.split(splitter, 1)
            except:
                continue
            if suffix:
                title += splitter
                rest = [suffix]
                break
    return title, '\n'.join(rest).strip()

def postAsText(subreddit, post_text):
    title, content = splitText(post_text)
    if isUrl(title) and len(title.split()) == 1:
        title = getTitle(title)
        content = post_text
    return subreddit.submit(title, selftext=content)

def postInline(subreddit, post_text, fns):
    media = {}
    count = 0
    text = ''
    for fn in fns:
        count += 1
        image_key = 'image' + str(count)
        media[image_key] = InlineImage(path=fn)
        text += '{%s}' % image_key
    title, content = splitText(post_text)
    content += text
    return subreddit.submit(title, selftext=content, inline_media=media)

def postVideo(subreddit, post_text, video):
    cached_url.get(video, mode='b', force_cache=True)
    title, content = splitText(post_text)
    content += '{video}'
    return subreddit.submit(title, selftext=content, inline_media={
        "video": InlineVideo(path=cached_url.getFilePath(video))})
    
async def getText(channel, post, key):
    text, post = await getRawText(channel, post.post_id)
    for entity in post.entities or []:
        origin_text = ''.join(text[entity.offset:entity.offset + entity.length])
        to_replace = entity.url if hasattr(entity, 'url') else origin_text
        to_replace = replaceTelegraphUrl(to_replace)
        text[entity.offset] = to_replace
        if entity.offset + entity.length == len(text) and origin_text == 'source':
            text[entity.offset] = '\n\n' + to_replace
        for index in range(entity.offset + 1, entity.offset + entity.length):
            if text[index] != '\n':
                text[index] = ''
    text = ''.join(text)
    text = '\n'.join([line.strip() for line in text.split('\n')]).strip()
    return text or key

async def postImp(subreddit, channel, post, key):
    post_text = await getText(channel, post, key)
    img_number = post.getImgNumber()
    if post.getVideo():
        return postVideo(subreddit, post_text, post.getVideo())
    if not img_number:
        # see if I need to deal with the link case separately
        return postAsText(subreddit, post_text)
    fns = await getImages(channel, post.post_id, img_number)
    core = getCore(channel, post_text)
    if core and len(core) < 180:
        return postAsGallery(subreddit, core, fns, post_text.split()[-1])
    return postInline(subreddit, post_text, fns)

def getPostFromPending(posts):
    posts = list(itertools.islice(posts, 100))
    posts = [(post.time + random.random(), post) for post in posts]
    posts.sort()
    if not posts:
        return
    if posts[0][0] < time.time() - Day * 2:
        return posts[0][1]
    for post in posts:
        if post[1].post_id != 128801: # testing
            continue
        if random.random() > 0.02:
            continue
        return post[1]

async def runImp():
    removeOldFiles('tmp', day=0.1)
    items = list(setting['channel_map'].items())
    random.shuffle(items)
    for channel, sub_name in items:
        sub_setting = setting['setting_map'].get(channel, {})
        subreddit = reddit.subreddit(sub_name)
        posts = getPendingPosts(channel, existing, 
            max_time=time.time() + Day * sub_setting.get('max_time', -0.05),
            min_time=time.time() + Day * sub_setting.get('min_time', -10))
        post = getPostFromPending(posts)
        if not post:
            continue
        key = 'https://t.me/' + post.getKey()
        try:
            result = await postImp(subreddit, channel, post, key)
            existing.update(key, 1)
        except Exception as e:
            print('post_reddit', key, e)
            if str(e).startswith('TOO_LONG:') or str(e).startswith('a bytes-like object is required'):
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