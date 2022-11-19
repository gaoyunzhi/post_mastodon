from post_mastodon import *

def test():
    Mastodon.create_app(
        't',
        api_base_url = credential['mastodon_domain'],
        to_file = 'db/pytooter_clientcred.secret'
    )

if __name__ == '__main__':
    test()