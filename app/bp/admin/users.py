'''
Created on 6.5.2019

@author: jm
'''
from datetime import datetime
 
import shareds
from .models.cypher_adm import Cypher_stats

class Batches(object):
    '''
    Methods for collectiong user batch statistics.
    
    Target example:
    user    batch                   "Family"    "Note"    "Person"
    ----    -----                   --------    ------    --------
    "usr1"  "usr1 2019-05-03.001"        94       224         153
    "usr1"  "usr1 2019-05-03.002"       736      3990        1949
    '''

    def __init__(self, user=None):
        '''
        Decide, which user is included in reports (if limited)
        '''
        self.user = user

    def get_user_batch_stats(self):
        ''' Get statistics of user Batch contents.
        
            u["usr1"].append({batch:"usr1 2019-05-03.001", "Family":94, "Note":224, "Person":153})
        '''
        labels = []
        users = {}
        result = shareds.driver.session().run(Cypher_stats.get_batches, user=self.user)
        for record in result:
            # <Record batch=<Node id=319388 labels={'Batch'} 
            #    properties={ // 'mediapath': '/home/jm/my_own.media', 
            #        'file': 'uploads/jpek/Julius_vanhemmat_clean.gramps', 
            #        'id': '2019-08-21.002', 'user': 'jpek', 'timestamp': 1566398894787, 
            #        'status': 'completed'}> 
            #  label='Note'
            #  cnt=2>
            batch = record['batch']
            label = record['label']
            cnt = record['cnt']
            batch_id = batch.get('id')
            ts = batch.get('timestamp')
            if ts:
                t = float(ts)/1000.
                tstring = datetime.fromtimestamp(t).strftime("%-d.%-m.%Y %H:%M")
#                 tstring = datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")
#                 d, t = tstring.split()
#                 if batch[:10] == d:
#                     tstring = t
            else:
                tstring = ""
            label = record['label']
            if not label: label = ""
            if label and not label in labels:
                labels.append(label)
            cnt = record['cnt']

            key = f'{self.user}/{batch_id}/{tstring}'
            if not key in users:
                users[key] = {}
            users[key][label] = cnt

            #print(f'users[{key}] {users[key]}')

        return sorted(labels), users


    def get_batch_stats(self, batch_id):
        ''' Get statistics of user Batch contents.
        '''
        labels = []
        batch = None
        result = shareds.driver.session().run(Cypher_stats.get_single_batch, batch=batch_id)
        for record in result:
            # <Record batch=<Node id=319388 labels={'Batch'} 
            #    properties={ // 'mediapath': '/home/jm/my_own.media', 
            #        'file': 'uploads/jpek/Julius_vanhemmat_clean.gramps', 
            #        'id': '2019-08-21.002', 'user': 'jpek', 'timestamp': 1566398894787, 
            #        'status': 'completed'}> 
            #  label='Note'
            #  cnt=2>

            if not batch:
                batch = record['batch']
                user = batch.get('user')
                #batch_id = batch.get('id')
                ts = batch.get('timestamp')
                if ts:
                    t = float(ts)/1000.
                    tstring = datetime.fromtimestamp(t).strftime("%-d.%-m.%Y %H:%M")
                else:
                    tstring = ""
            label = record.get('label', '')
            cnt = record['cnt']
            labels.append((label,cnt))

#             key = f'{user}/{batch_id}/{tstring}'
#             if not key in users:
#                 users[key] = {}
#             users[key][label] = cnt

            #print(f'users[{key}] {users[key]}')

        return user, batch_id, tstring, sorted(labels)
    
    def TODO_move_batch_owner(self, batch_id):
        ''' Move Batch to Isotammi database.
        
            Before: 
            (up:UserProfile) -[:HAS_LOADED]-> (b:Batch {id:$batch}) -[:OWNS]-> (x)
            
            After:
            (ip:UserProfile{username:'*suomi*'}) -[:HAS_LOADED]-> (b:Batch {id:$batch}) -[:OWNS]-> (x)
        '''
        result = shareds.driver.session().run(Cypher_stats.get_single_batch, batch=batch_id)
        for record in result:
            # <Record batch=<Node id=319388 labels={'Batch'} 
            #    properties={ // 'mediapath': '/home/jm/my_own.media', 
            #        'file': 'uploads/jpek/Julius_vanhemmat_clean.gramps', 
            #        'id': '2019-08-21.002', 'user': 'jpek', 'timestamp': 1566398894787, 
            #        'status': 'completed'}> 
            #  label='Note'
            #  cnt=2>

            pass

