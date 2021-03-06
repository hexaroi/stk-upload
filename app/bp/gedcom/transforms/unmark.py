#!/usr/bin/env python3
"""
Restores marked tags: <tag>-X -> <tag>
"""

version = "2.0"
#doclink = "http://wiki.isotammi.net/wiki/Gedcom:Gedcom-Marriages-ohjelma"

from flask_babelex import _
name = _("Unmark")
docline = _("Restores marked tags: <tag>-X -> <tag>")
doclinks = {
    'fi': "http://wiki.isotammi.net/wiki/Poista_tag_X_merkinnät", 
}    

from .. import transformer

def add_args(parser):
    pass

def initialize(options):
    return Unmark()

class Unmark(transformer.Transformation):
    def transform(self,item,options,phase):
        # phase 1
        if item.tag.endswith("-X"):
            item.tag = item.tag[0:-2]
            return item
        return True