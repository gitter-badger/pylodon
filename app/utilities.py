from app import mongo
from config import ACCEPT_HEADERS, API_NAME, API_URI, SERVER_NAME
from .crypto import generate_keys
from .api.utilities import find_user_or_404, get_time, sign_object
from .users import User

from activipy import vocab
from flask import abort, request
from flask_login import current_user
from webfinger import finger
import requests


def get_logged_in_user():
    u = mongo.db.users.find_one({'id': current_user.get_id()})
    if not u:
        abort(404)
    return u


def find_post_or_404(handle, post_id):
    id = request.url_root+'api/'+handle+'/'+post_id+'/activity'
    p = mongo.db.posts.find_one({'id': id}, {'_id': False})
    if not p:
        abort(404)
    return p


def get_address(addr, box='inbox'):
    try:
        if addr.startswith('@'):
            addr = 'acct:'+addr[1:]
    except AttributeError:
        for a in addr:
            if a.startswith('@'):
                addr = 'acct:'+addr[1:]
    try:
        if addr.startswith('acct'):
            return get_address_from_webfinger(acct=addr, box=box)    
    except AttributeError:
        for a in addr:
            if addr.startswith('acct'):
                return get_address_from_webfinger(acct=a)

    try:
        if addr.startswith('http'):
            if addr is not 'https://www.w3.org/ns/activitystreams#Public':
                try:
                    inbox = requests.get(addr, headers=sign_headers(get_logged_in_user(), ACCEPT_HEADERS)).json()['inbox']
                    return inbox
                except AttributeError:
                    return addr
        else:
            return addr
    except AttributeError:
        for a in addr:
            if addr.startswith('http'):
                if addr is not 'https://www.w3.org/ns/activitystreams#Public':
                    try:
                        inbox = requests.get(addr, headers=sign_headers(get_logged_in_user(), ACCEPT_HEADERS)).json()['inbox']
                        return inbox
                    except AttributeError:
                        return addr
                else:
                    return addr
            else:
                print('not a valid uri')


def get_address_from_webfinger(acct, box):
    wf = finger(acct)
    user = wf.rel('self')
    u = requests.get(user, headers=ACCEPT_HEADERS).json()

    return u[box]


def create_user(user):
    public, private = generate_keys()

    user_api_uri = API_URI+'/'+user['handle']

    return vocab.Person(
                    user_api_uri,
                    username=user['handle'],
                    acct=user['handle']+SERVER_NAME,
                    url=SERVER_NAME+'/@'+user['handle'],
                    preferredUsername=user['displayName'],
                    email=user['email'],
                    following=user_api_uri+'/following',
                    followers=user_api_uri+'/followers',
                    liked=user_api_uri+'/likes',
                    inbox=user_api_uri+'/inbox',
                    outbox=user_api_uri+'/feed',
                    metrics=dict(post_count=0),
                    created_at=get_time(),
                    passwordHash=User.hash_password(user['password']),
                    publicKey=dict(
                        id=user_api_uri+'#main-key',
                        owner=user_api_uri,
                        publicKeyPem=public),
                    privateKey=private)


def create_post(content, handle, to, cc):
    u = find_user_or_404(handle)

    post_number = str(u['metrics']['post_count'])
    id = request.url_root+'api/'+u['username']+'/posts/'+post_number
    note_url = request.url_root+'@'+u['username']+'/'+post_number

    time = get_time()

    # create =  {
    #           'id': id+'/activity',
    #           'type': 'Create',
    #           '@context': 'DEFAULT_CONTEXT',
    #           'actor': u['@id'],
    #           'published': time,
    #           'to': to,
    #           'cc': cc,
    #           'object': {
    #                       'id': id,
    #                       'type': 'Note',
    #                       'summary': None,
    #                       'content': content,
    #                       'inReplyTo': None,
    #                       'published': time,
    #                       'url': note_url,
    #                       'attributedTo': u['@id'],
    #                       'to': to,
    #                       'cc': cc,
    #                       'sensitive': False
    #                     },
    #           'signature': {
    #             'created': time,
    #             'creator': u['@id']+'?get=main-key',
    #             'signatureValue': sign_object(u, content),
    #             'type': 'rsa-sha256'
    #           }
    #         }

    # return json.dumps(create)

    return vocab.Create(
                        id+'/activity',
                        actor=vocab.Person(
                            u['@id'],
                            displayName=u['displayName']),
                        to=to,
                        cc=cc,
                        object=vocab.Note(
                            id,
                            url=note_url,
                            content=content)
                        )


def create_like(actorAcct, post):
    to = post['attributedTo']
    if post.get('to'):
        for t in post['to']:
            to.append(t)

    return vocab.Like(
                    context='DEFAULT_CONTEXT',
                    actor=actorAcct,
                    to=to,
                    object=post['@id'])


def create_follow(actorAcct, otherUser):
    return vocab.Follow(
                      id=None,
                      context='DEFAULT_CONTEXT',
                      actor=actorAcct,
                      object=vocab.User(otherUser['@id']))


def create_accept(followObj, to):
    acceptObj = {
                "@context": 'DEFAULT_CONTEXT',
                'type': 'Accept',
                'to': to,
                'object': followObj
              }
    return acceptObj


def create_reject(followObj, to):
    rejectObj = {
                'type': 'Reject',
                'to': to,
                'object': followObj
              }
    return rejectObj