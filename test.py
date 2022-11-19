from post_mastodon import *

def create_account_secrets():
    for user, user_setting in credential['mastodon_users'].items():
        secret_file = 'db/%s_mastodon_secret' % user
        Mastodon.create_app(
            't',
            api_base_url = credential['mastodon_domain'],
            to_file = secret_file
        )
        mastodon = Mastodon(
            client_id = secret_file,
            api_base_url = credential['mastodon_domain'],
        )    
        mastodon.log_in(
            user_setting['email'],
            user_setting['password'],
            to_file = secret_file,
        )

def test():
    ...

if __name__ == '__main__':
    # create_account_secrets()
    test()