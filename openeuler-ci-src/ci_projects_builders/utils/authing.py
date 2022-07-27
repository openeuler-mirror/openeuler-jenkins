import logging
import json
import requests


logger = logging.getLogger('log')


def get_token(userId, secret):
    url = 'https://core.authing.cn/api/v2/userpools/access-token'
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        'userPoolId': userId,
        'secret': secret
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload))
    if r.status_code != 201:
        logger.info('Fail to get authing access token, please check userId and secret.')
        return None
    logger.info('Success to get authing access token.')
    return r.json()['accessToken']


def search_member(token, userId, email_address):
    url = 'https://core.authing.cn/api/v2/users/search'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(token),
        'x-authing-userpool-id': userId
    }
    params = {
        'query': email_address
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200 and r.json()['data']['totalCount'] > 0:
        for item in r.json()['data']['list']:
            if item['email'] == email_address:
                logger.info('Success to search member {} whose member_id is {}.'.format(email_address, item['id']))
                return item['id']
    else:
        logger.error('ERROR! Cannot search member {}.'.format(email_address))
        return


def create_authing_user(token, userId, email_address):
    url = 'https://core.authing.cn/api/v2/users'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(token),
        'x-authing-userpool-id': userId
    }
    payload = {
        'userInfo': {
            'email': email_address
        }
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload))
    if r.json()['code'] == 200:
        member_id = r.json()['data']['id']
        logger.info('Success to create authing user for {} whose member_id is {}.'.format(email_address, member_id))
        return member_id
    elif r.json()['code'] == 2026:
        member_id = search_member(token, userId, email_address)
        logger.info('The user {} still exists and its member_id is {}.'.format(email_address, member_id))
        return member_id
    else:
        logger.error('ERROR! Fail to create member, the status code is {}.'.format(r.json()['code']))
        return


def add_member(token, userId, group, member_id):
    url = 'https://core.authing.cn/api/v2/groups/{}/add-users'.format(group)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(token),
        'x-authing-userpool-id': userId
    }
    payload = {
        'userIds': [str(member_id)]
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload))
    if r.status_code != 201:
        logger.error('ERROR! Fail to add member to group {} whose member_id is {}.'.format(group, member_id))
    else:
        logger.info('Success to add member to group {} whose member_id is {}.'.format(group, member_id))
