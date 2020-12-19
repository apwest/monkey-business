# from __future__ import print_function
import pickle
import os
import re
import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import base64
import email
from apiclient import errors

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify']

#===========================================================

def get_num_clips(path):
    return len([x for x in os.listdir(path) if re.match('[0-9]+\.html', x)])

def get_next_clip(path):
    total_clips = 0
    for f in os.listdir(path):
        clips_path = os.path.join(path, f)
        if os.path.isdir(clips_path):
            total_clips += len([x for x in os.listdir(clips_path) if re.match('[0-9]+\.html', x)])
    return total_clips

#===========================================================

def ModifyMessage(service, user_id, msg_id, remove_labels=[], add_labels=[]):
    """Modify the Labels on the given Message.

    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
        msg_id: The id of the message required.
        msg_labels: The change in labels.

    Returns:
        Modified message, containing updated labelIds, id and threadId.
    """
    try:
        print("user_id: {}\nmsg_id: {}".format(user_id, msg_id))
        msg_labels = { 'removeLabelIds': remove_labels,
                       'addLabelIds': add_labels }

        message = service.users().messages().modify(
                        userId=user_id, id=msg_id, body=msg_labels).execute()

        label_ids = message['labelIds']

        print("Message ID: %s - With Label IDs %s" % (msg_id, label_ids))
        return message
    except errors.HttpError as error:
        print("An error occurred: %s" % error)


def MarkAsRead(service, user_id, msg_id):
    return ModifyMessage(service, user_id, msg_id, remove_labels=[
            # 'INBOX',
            'UNREAD'
            ])


def GetMessage(service, user_id, msg_id):
    """Get a Message with given ID.

    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
        msg_id: The ID of the Message required.

    Returns:
        A Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id).execute()
        # print('Message snippet: %s' % message['snippet'])
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def GetMimeMessage(service, user_id, msg_id):
    """Get a Message and use it to create a MIME Message.

    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
        msg_id: The ID of the Message required.

    Returns:
        A MIME Message, consisting of data from Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id,
                                                format='raw').execute()

        # print('Message snippet: %s' % message['snippet'])

        msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))

        mime_msg = email.message_from_bytes(msg_str)

        return mime_msg
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def ListMessagesMatchingQuery(service, user_id, query=''):
    """List all Messages of the user's mailbox matching the query.

    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
        query: String used to filter messages returned.
        Eg.- 'from:user@some_domain.com' for Messages from a particular sender.

    Returns:
        List of Messages that match the criteria of the query. Note that the
        returned list contains Message IDs, you must use get with the
        appropriate ID to get the details of a Message.
    """
    try:
        response = service.users().messages().list(userId=user_id,
        q=query).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = service.users().messages().list(userId=user_id,
                                q=query, pageToken=page_token).execute()
                messages.extend(response['messages'])

        return messages

    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def ListMessagesWithLabels(service, user_id, label_ids=[]):
    """List all Messages of the user's mailbox with label_ids applied.

    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
        label_ids: Only return Messages with these labelIds applied.

    Returns:
        List of Messages that have all required Labels applied. Note that the
        returned list contains Message IDs, you must use get with the
        appropriate id to get the details of a Message.
    """
    try:
        response = service.users().messages().list(userId=user_id,
                                                   labelIds=label_ids).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = service.users().messages().list(userId=user_id,
                                labelIds=label_ids,
                                pageToken=page_token).execute()
                messages.extend(response['messages'])

        return messages

    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def ListLabels(service, user_id):
    # Call the Gmail API
    results = service.users().labels().list(userId=user_id).execute()
    labels = results.get('labels', [])

    if not labels:
        print('No labels found.')
    else:
        print('Labels:')
        for label in labels:
            print(label['name'])


clip_template = """
<div class="content">
<div class="details">
Original release date: <span>%s</span>
</div>
%s
</div>
"""

def ParseWootMessage(message, path, i):
    """Parses an email message from Woot looking for
    the Monte and Mortimer dialogue. Once finding the
    dialogue, it will save it to the templates folder.
    """
    # for part in message['payload']['parts']:
    #     print("  Part: {}, Size: {}".format(part['partId'], part['body']['size']))
    #     data = base64.b64decode(part['body']['data'].replace('-','+'))
    # with open('msg-{}.txt'.format('1'), 'w') as f:
    #     f.write(message.decode())
    for part in message.walk():
        if part.get_content_maintype() == 'multipart':
            continue

        try:
            txt = part.get_payload(decode=True).decode('utf-8')
        except:
            continue

        if 'Monte' in txt or 'Mortimer' in txt or 'monte' in txt or 'mortimer' in txt:
            print ("-- extracting dialog...")

            # Get Monte/Mortimer dialog
            content = ""
            p,q = 0,0
            while True:
                # APW: this used to be 'monkey_' prior to 2015-11-20
                p = txt.find('monkey-', q)
                if p == -1:
                    x = txt.find('mortimer-2.png', q)
                    y = txt.find('monte-2.png', q)
                    if x > -1 and y > -1:
                        p = min(x,y)
                    elif x > -1:
                        p = x
                    elif y > -1:
                        p = y
                    else:
                        break

                p = txt.rfind('<table', q, p)
                q = txt.find('</table', p)
                if p == -1 or q == -1:
                    break

                content += txt[p:q+8]

            #print (r)
            if content != "":
                date = message['Date'][:-15]
                html = clip_template % (date, content)
                print ("-- saving dialog to file...")
                clip_path = os.path.join(path, "%d" % ((i/1000) + 1))
                if not os.path.exists(clip_path):
                    os.mkdir(clip_path)
                file = os.path.join(clip_path, "%d.html" % (i%1000))
                if os.path.exists(file):
                    print ("ERROR: File already exists! (%s)" % file)
                    exit (1)
                print ("-- writing %d bytes to %s" % (len(html), file))
                f = open(file,"w")
                f.write(html)
                f.close()
                return True
    return False


def authenticate():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = authenticate()
    if not creds:
        return (False, "Invalid credentials")

    service = build('gmail', 'v1', credentials=creds)

    path = os.path.abspath("./templates")
    print("Saving clips to: {}".format(path))
    n = get_next_clip(path)

    messages = ListMessagesMatchingQuery(service, user_id='me', query='label:woot is:unread')

    # Reverse the list so it's sorted oldest to newest
    messages.reverse()

    print("{} new messages".format(len(messages)))
    for i,msg in enumerate(messages):
        print("Processing {} of {}...".format(i+1, len(messages)))
        min_msg = service.users().messages().get(userId='me', id=msg['id'],
                                                format='minimal').execute()
        print("-- {}".format(time.asctime(time.gmtime(int(min_msg['internalDate'])/1000))))

        MarkAsRead(service, 'me', msg['id'])
        msg = GetMimeMessage(service, 'me', msg['id'])
        if (ParseWootMessage(msg, path, n)):
            n += 1
        # break

    return (True, f"Processed {len(messages)} emails")

if __name__ == '__main__':
    main()
