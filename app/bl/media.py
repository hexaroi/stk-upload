'''
Created on 24.3.2020

@author: jm
'''
from .base import NodeObject

class MediaBl_todo(NodeObject):
    '''
    NOT IN USE, yet
    '''
    def __init__(self, params):
        '''
        Constructor
        '''
        

class MediaRefResult():
    ''' Gramps media reference result object.
    
        Includes Note and Citation references and crop data
    '''
    def __init__(self):
        self.media_handle = None
        self.media_order = 0        # Media reference order nr
        self.crop = []              # Four coordinates
        self.note_handles = []      # list of note handles
        self.citation_handles = []  # list of citation handles

    def __str__(self):
        s = f'{self.media_handle} [{self.media_order}]'
        if self.crop: s += f' crop({self.crop})'
        if self.note_handles: s += f' notes({self.note_handles})'
        if self.citation_handles: s += f' citations({self.citation_handles})'
        return s

