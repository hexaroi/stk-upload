import io
import re
import sys
import time
from collections import Counter, defaultdict
from contextlib import redirect_stdout

import transformer
from flask_babelex import _
import traceback

name = _("GEDCOM Analyzer")

def initialize(options):
    return Analyzer()

def add_args(parser):
    pass

class Info: pass 

import gedcom_grammar_data2

def read_allowed_paths():
    allowed = set()
    from gedcom_grammar_data import paths
    for line in paths.splitlines():
        if line.strip() != "":
            allowed.add(line.strip())
    return allowed

def valid_date(datestring):
    # date checker, not perfect
    parts = datestring.split(maxsplit=1)
    if len(parts) < 1: return False

    if len(parts) > 1 and parts[0] in {"ABT","EST","CAL"}:
        return valid_date(parts[1])

    m = re.match("BET (.+?) AND (.+)",datestring)
    if m:
        return valid_date(m.group(1)) and valid_date(m.group(2))

    m = re.match("FROM (.+) TO (.+)",datestring)
    if m:
        return valid_date(m.group(1)) and valid_date(m.group(2))

    if len(parts) > 1 and parts[0] in {"FROM","TO","BEF","AFT"}:
        return valid_date(parts[1])
    
    try:
        if time.strptime(datestring, "%Y"): return True
    except:
        pass

    try:
        if time.strptime(datestring, "%b %Y"): return True
    except:
        pass

    try:
        if time.strptime(datestring, "%d %b %Y"): return True
    except:
        pass
        
    return False

class Out:
    def emit(self,s):
        print(s)
out = Out()

class LineCounter:
    def __init__(self,title=None):
        self.title = title
        self.values = defaultdict(list)
    def add(self,key,item):
        self.values[key].append(item)
    def display(self):
        if len(self.values) == 0: return
        print()
        print(self.title) 
        for key,itemlist in sorted(self.values.items()):
            linenums = [str(item.linenum) for item in itemlist]
            if len(linenums) > 10:
                linenums = linenums[0:10] 
                linenums.append("...")
            print("- {:25} (count={:5}, lines {})".format(key,len(itemlist),",".join(linenums)))   
            #print("- {:25} (count={:5})".format(key,len(itemlist)))
            #try:
            #    for item in itemlist: item.print_items(out)
            #except:
            #    traceback.print_exc()   
       
                
class Analyzer(transformer.Transformation):
    def __init__(self):
        self.info = Info()
        self.allowed_paths = read_allowed_paths()
        self.illegal_paths = LineCounter(_("Invalid tag hierarchy:"))
        self.novalues = LineCounter(_("No value:"))
        self.invalid_dates = LineCounter(_("Invalid dates:"))
        #self.too_few = []
        #self.too_many = []
        self.too_few = LineCounter(_("Too few child tags:"))
        self.too_many = LineCounter(_("Too many child tags:"))
        self.submitter_refs = LineCounter(_("Records for submitters"))
        self.submitters = dict()
        self.submitter_emails = dict()
        self.records = set()
        self.xrefs = set()
        self.types = defaultdict(LineCounter)
        self.genders = defaultdict(int)
        self.mandatory_paths = {
            "HEAD",
            "HEAD.SOUR",
            "HEAD.GEDC",
            "HEAD.GEDC.VERS",
            "HEAD.GEDC.FORM",
            "HEAD.CHAR",
            "HEAD.SUBM",
            "TRLR",
        }
        self.grammar_data = [
            # parent tag/suffix, child tag, mincount, maxcount
            # ->
            # child tag must occur mincount to maxcount times under parent tag
            (".MAP",    "LATI", 1,1),
            (".MAP",    "LONG", 1,1),
            (".HUSB",   "AGE", 1,1),
        ]       

    def transform(self,item,options,phase):
        if 0:
            print("line:",item.line)
            print("tag:",item.tag)
            print("path:",item.path)
            print("value:",item.value)
        path = item.path
        if path[0] == '@': path = path.split(".",maxsplit=1)[1]
        if item.tag != "CONC" and path not in self.allowed_paths:
            self.illegal_paths.add(path,item)
        
        if item.value == "" and len(item.children) == 0 and item.tag not in {"TRLR","CONT"}:
            self.novalues.add(item.line,item)         
            
        if item.tag == "SEX":
            self.genders[item.value] += 1
            
        if item.tag == "DATE":
            if not valid_date(item.value.strip()):
                self.invalid_dates.add(item.value,item)

        if path in self.mandatory_paths: self.mandatory_paths.remove(path)     
        
        """
        for (suffix, tag, mincount,maxcount) in self.grammar_data:
            if path.endswith(suffix):
                count = 0
                for c in item.children:
                    if c.tag == tag: count += 1
                if count < mincount:
                    #self.too_few.append( (item,suffix,tag,mincount,count) )     
                    self.too_few.add( "Only {} {} tags under {} - should be at least {}".format(count,tag,suffix,mincount), item )     
                if count > maxcount:
                    #self.too_many.append( (item, suffix,tag,maxcount,count) )     
                    self.too_few.add( "{} {} tags under {} - should be at most {}".format(count,tag,suffix,maxcount), item )     
        """
        taglist = gedcom_grammar_data2.data.get(path)
        if taglist:
            for (tag,(mincount,maxcount)) in taglist:
                count = 0
                for c in item.children:
                    if c.tag == tag: count += 1
                if count < mincount:
                    self.too_few.add( "Only {} {} tags under {} - should be at least {}".format(count,tag,path,mincount), item )     
                if maxcount and count > maxcount:
                    self.too_many.add( "{} {} tags under {} - should be at most {}".format(count,tag,path,maxcount), item )     
        
        if item.path.endswith("SUBM.NAME"):
            xref = item.path.split(".")[0]
            self.submitters[xref] = item.value 
        if item.path.endswith("SUBM.EMAIL"):
            xref = item.path.split(".")[0]
            self.submitter_emails[xref] = item.value 
        if item.level == 1 and item.tag == "SUBM":
            self.submitter_refs.add(item.value,item) 
        if item.level == 0 and item.xref:
            self.records.add(item.xref)
        if item.level > 0 and item.value.startswith("@") and not item.value.startswith("@#"):
            self.xrefs.add(item.value)
            
        if item.tag == "TYPE": # classify types
            parts = item.path.split(".")
            if parts[0][0] == "@":
                parent_path = ".".join(parts[1:-1])
            else: 
                parent_path = ".".join(parts[0:-1])
            self.types[parent_path].add(item.value,item)
        return True

    def finish(self,options):
        with io.StringIO() as buf, redirect_stdout(buf):
            self.display_results(options)
            self.info = buf.getvalue()

            
    def display_results(self,options):
        print()
        print(_("Genders:"))
        for sex,count in sorted(self.genders.items()):
            print("- {}: {:5}".format(sex,count))            
        self.illegal_paths.display()
        self.invalid_dates.display()
        self.novalues.display()
        self.too_few.display()
        self.too_many.display()
        
        self.submitter_refs2 = LineCounter(_("Submitters"))
        for xref,itemlist in self.submitter_refs.values.items():
            name = self.submitters.get(xref,xref)
            if name == xref: name = self.submitter_emails.get(xref,xref)
            self.submitter_refs2.values[name] = itemlist
        self.submitter_refs2.display()
             
        if len(self.mandatory_paths) > 0:
            print()
            print(_("Missing paths:"))
            for path in sorted(self.mandatory_paths):
                print("-",path)

        for parent_path,typeinfo in self.types.items():
            typeinfo.title = _("TYPEs for %(parent_path)s",parent_path=parent_path)
            typeinfo.display()

        print()
        for xref in self.xrefs:
            if xref not in self.records:
                print("Missing record:", xref)            

        print()
        for xref in self.records:
            if xref not in self.xrefs:
                print("Unused record:", xref)            

            

            
            
            