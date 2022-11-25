from post_mastodon import *

def create_account_secrets():
    for user, user_setting in credential['mastodon_users'].items():
        print('creating credential:', user)
        secret_file = 'db/%s_mastodon_secret' % user
        Mastodon.create_app(
            't1',
            api_base_url = credential['mastodon_domain'],
            to_file = secret_file
        )
        print(1)
        mastodon = Mastodon(
            client_id = secret_file,
            api_base_url = credential['mastodon_domain'],
        )    
        print(2)
        mastodon.log_in(
            user_setting['email'],
            user_setting['password'],
            to_file = secret_file,
        )
        print(3)

def test():
    ...

if __name__ == '__main__':
    create_account_secrets()
    test()