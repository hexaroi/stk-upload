'''
Extracted from gramps_loader.py on 2.12.2018

    Methods to import all data from Gramps xml file

@author: Jorma Haapasalo <jorma.haapasalo@pp.inet.fi>
'''

import logging
import time
import xml.dom.minidom
import re

from .models.person_gramps import Person_gramps
from .models.event_gramps import Event_gramps
from .batchlogger import Log    # Batch

from models.gen.family import Family
from models.gen.note import Note
from models.gen.media import Media
from models.gen.person_name import Name
from models.gen.person_combo import Person_combo

from models.gen.place import Place, Place_name, Point
from models.gen.dates import Gramps_DateRange
from models.gen.citation import Citation
from models.gen.source import Source
from models.gen.repository import Repository

from models.dataupdater import set_person_name_properties


def pick_url(src):
    ''' Extract an url from the text src, if any
    
        Returns (text, url), where the url is removed from text
    '''
    #TODO: Jos url päättyy merkkeihin '").,' ne tulee poistaa ja siirrää end-tekstiin
    #TODO: Pitäsikö varautua siihen että tekstikenttä sisältää monta url:ia?

    match = re.search("(?P<url>https?://[^\s'\"]+)", src)
    url = None
    text = src
    if match is not None:
        url = match.group("url")
        start = match.start()
        end = match.end()
#         start = ''   if start == 0
#         end = ''     if end == len(src) - 1:
#         print("[{}:{}] url='{}'".format(start, end, url))
        text = ''
        if start:
            text = src[:start]
        if end < len(src):
            text = "{}{}".format(text, src[end:])
#         if text:
#             print("    '{}'".format(text.rstrip()))
#     elif len(src) > 0 and not src.isspace():
#         print("{} ...".format(src[:72].rstrip()))

    return (text.rstrip(), url)

def get_priv(dom_obj):
    ''' Gives priv property value as int, if it is not '0'
    '''
    if dom_obj.hasAttribute("priv"):
        priv = int(dom_obj.getAttribute("priv"))
        if priv:
            return priv
    return None


class DOM_handler():
    """ XML DOM elements handler
        - creates transaction
        - processes different data groups from given xml file to database
        - collects status log
    """

    def __init__(self, infile, current_user):
        """ Set DOM collection and username """
        DOMTree = xml.dom.minidom.parse(open(infile, encoding='utf-8'))
        self.collection = DOMTree.documentElement    # XML documentElement
        self.username = current_user        # current username

        self.uniq_ids = []                  # List of processed Person node unique id's
        self.tx = None                      # Transaction not opened

    def begin_tx(self, session):
        self.tx = session.begin_transaction()
        print("Transaction started")

    def commit(self):
        """ Commit transaction """
        if self.tx.closed():
            print("Transaction already closed!")
        else:
            try:
                self.tx.commit()
                print("Transaction committed")
            except Exception as e:
                print("Transaction failed")
                self.blog.log_event({'title':"Talletus tietokantaan ei onnistunut {} {}".\
                                     format(e.__class__.__name__, e), 'level':"ERROR"})


    # ---------------------   XML subtree handlers   --------------------------

    def handle_citations(self):
        # Get all the citations in the collection
        citations = self.collection.getElementsByTagName("citation")

        print ("***** {} Citations *****".format(len(citations)))
        t0 = time.time()
        counter = 0

        # Print detail of each citation
        for citation in citations:

            c = Citation()

            if citation.hasAttribute("handle"):
                c.handle = citation.getAttribute("handle")
            if citation.hasAttribute("change"):
                c.change = int(citation.getAttribute("change"))
            if citation.hasAttribute("id"):
                c.id = citation.getAttribute("id")

            if len(citation.getElementsByTagName('dateval') ) == 1:
                citation_dateval = citation.getElementsByTagName('dateval')[0]
                if citation_dateval.hasAttribute("val"):
                    c.dateval = citation_dateval.getAttribute("val")
            elif len(citation.getElementsByTagName('dateval') ) > 1:
                self.blog.log_event({'title':"More than one dateval tag in a citation",
                                     'level':"WARNING", 'count':c.id})

            if len(citation.getElementsByTagName('page') ) == 1:
                citation_page = citation.getElementsByTagName('page')[0]
                c.page = citation_page.childNodes[0].data
            elif len(citation.getElementsByTagName('page') ) > 1:
                self.blog.log_event({'title':"More than one page tag in a citation",
                                     'level':"WARNING", 'count':c.id})

            if len(citation.getElementsByTagName('confidence') ) == 1:
                citation_confidence = citation.getElementsByTagName('confidence')[0]
                c.confidence = citation_confidence.childNodes[0].data
            elif len(citation.getElementsByTagName('confidence') ) > 1:
                self.blog.log_event({'title':"More than one confidence tag in a citation",
                                     'level':"WARNING", 'count':c.id})

            if len(citation.getElementsByTagName('noteref') ) >= 1:
                for i in range(len(citation.getElementsByTagName('noteref') )):
                    citation_noteref = citation.getElementsByTagName('noteref')[i]
                    if citation_noteref.hasAttribute("hlink"):
                        c.noteref_hlink.append(citation_noteref.getAttribute("hlink"))

            if len(citation.getElementsByTagName('sourceref') ) == 1:
                citation_sourceref = citation.getElementsByTagName('sourceref')[0]
                if citation_sourceref.hasAttribute("hlink"):
                    c.source_handle = citation_sourceref.getAttribute("hlink")
            elif len(citation.getElementsByTagName('sourceref') ) > 1:
                self.blog.log_event({'title':"More than one sourceref tag in a citation",
                                     'level':"WARNING",'count':c.id})

            c.save(self.tx)
            counter += 1

        self.blog.log_event({'title':"Citations", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_events(self):
        # Get all the events in the collection
        events = self.collection.getElementsByTagName("event")

        print ("***** {} Events *****".format(len(events)))
        t0 = time.time()
        counter = 0

        # Print detail of each event
        for event in events:
            # Create an event with Gramps attributes
            e = Event_gramps()

            if event.hasAttribute("handle"):
                e.handle = event.getAttribute("handle")
            if event.hasAttribute("change"):
                e.change = int(event.getAttribute("change"))
            if event.hasAttribute("id"):
                e.id = event.getAttribute("id")

            if len(event.getElementsByTagName('type') ) == 1:
                event_type = event.getElementsByTagName('type')[0]
                # If there are type tags, but no type data
                if (len(event_type.childNodes) > 0):
                    e.type = event_type.childNodes[0].data
                else:
                    e.type = ''
            elif len(event.getElementsByTagName('type') ) > 1:
                self.blog.log_event({'title':"More than one type tag in an event",
                                     'level':"WARNING", 'count':e.id})

            if len(event.getElementsByTagName('description') ) == 1:
                event_description = event.getElementsByTagName('description')[0]
                # If there are description tags, but no description data
                if (len(event_description.childNodes) > 0):
                    e.description = event_description.childNodes[0].data
            elif len(event.getElementsByTagName('description') ) > 1:
                self.blog.log_event({'title':"More than one description tag in an event",
                                     'level':"WARNING", 'count':e.id})

            """ Dates:
                <daterange start="1820" stop="1825" quality="estimated"/>
                <datespan start="1840-01-01" stop="1850-06-30" quality="calculated"/>
                <dateval val="1870" type="about"/>
                <datestr val="1700-luvulla" />    # Not processed!
            """
            try:
                # type Gramps_DateRange
                e.dates = self._extract_daterange(event)
            except:
                e.dates = None

            if len(event.getElementsByTagName('place') ) == 1:
                event_place = event.getElementsByTagName('place')[0]
                if event_place.hasAttribute("hlink"):
                    e.place_hlink = event_place.getAttribute("hlink")
            elif len(event.getElementsByTagName('place') ) > 1:
                self.blog.log_event({'title':"More than one place tag in an event",
                                     'level':"WARNING", 'count':e.id})

            e.attr = dict()
            for attr in event.getElementsByTagName('attribute'):
                if attr.hasAttribute("type"):
                    e.attr[attr.getAttribute("type")] = attr.getAttribute("value")

            for ref in event.getElementsByTagName('noteref'):
                if ref.hasAttribute("hlink"):
                    e.note_handles.append(ref.getAttribute("hlink"))

            for ref in event.getElementsByTagName('citationref'):
                if ref.hasAttribute("hlink"):
                    e.citation_handles.append(ref.getAttribute("hlink"))

            if len(event.getElementsByTagName('objref') ) == 1:
                event_objref = event.getElementsByTagName('objref')[0]
                if event_objref.hasAttribute("hlink"):
                    e.objref_hlink = event_objref.getAttribute("hlink")
            elif len(event.getElementsByTagName('objref') ) > 1:
                self.blog.log_event({'title':"More than one objref tag in an event",
                                     'level':"WARNING", 'count':e.id})

            e.save(self.tx)
            if e.type == "Death" or e.type == "Cause Of Death":
                print ("- {} event {} / {}".format(e.type, e.uniq_id, e.id))
                #TODO: Don't know how to link them!
            counter += 1

        self.blog.log_event({'title':"Events", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_families(self):
        # Get all the families in the collection
        families = self.collection.getElementsByTagName("family")

        print ("***** {} Families *****".format(len(families)))
        t0 = time.time()
        counter = 0

        # Print detail of each family
        for family in families:

            f = Family()

            if family.hasAttribute("handle"):
                f.handle = family.getAttribute("handle")
            if family.hasAttribute("change"):
                f.change = int(family.getAttribute("change"))
            if family.hasAttribute("id"):
                f.id = family.getAttribute("id")

            if len(family.getElementsByTagName('rel') ) == 1:
                family_rel = family.getElementsByTagName('rel')[0]
                if family_rel.hasAttribute("type"):
                    f.rel_type = family_rel.getAttribute("type")
            elif len(family.getElementsByTagName('rel') ) > 1:
                self.blog.log_event({'title':"More than one rel tag in a family",
                                     'level':"WARNING", 'count':f.id})

            if len(family.getElementsByTagName('father') ) == 1:
                family_father = family.getElementsByTagName('father')[0]
                if family_father.hasAttribute("hlink"):
                    f.father = family_father.getAttribute("hlink")
            elif len(family.getElementsByTagName('father') ) > 1:
                self.blog.log_event({'title':"More than one father tag in a family",
                                     'level':"WARNING", 'count':f.id})

            if len(family.getElementsByTagName('mother') ) == 1:
                family_mother = family.getElementsByTagName('mother')[0]
                if family_mother.hasAttribute("hlink"):
                    f.mother = family_mother.getAttribute("hlink")
            elif len(family.getElementsByTagName('mother') ) > 1:
                self.blog.log_event({'title':"More than one mother tag in a family",
                                     'level':"WARNING", 'count':f.id})

            if len(family.getElementsByTagName('eventref') ) >= 1:
                for i in range(len(family.getElementsByTagName('eventref') )):
                    family_eventref = family.getElementsByTagName('eventref')[i]
                    if family_eventref.hasAttribute("hlink"):
                        f.eventref_hlink.append(family_eventref.getAttribute("hlink"))
                    if family_eventref.hasAttribute("role"):
                        f.eventref_role.append(family_eventref.getAttribute("role"))

            if len(family.getElementsByTagName('childref') ) >= 1:
                for i in range(len(family.getElementsByTagName('childref') )):
                    family_childref = family.getElementsByTagName('childref')[i]
                    if family_childref.hasAttribute("hlink"):
                        f.childref_hlink.append(family_childref.getAttribute("hlink"))

            if len(family.getElementsByTagName('noteref') ) >= 1:
                for i in range(len(family.getElementsByTagName('noteref') )):
                    family_noteref = family.getElementsByTagName('noteref')[i]
                    if family_noteref.hasAttribute("hlink"):
                        f.noteref_hlink.append(family_noteref.getAttribute("hlink"))

            f.save(self.tx, self.batch_id)
            counter += 1

        self.blog.log_event({'title':"Families", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_notes(self):
        # Get all the notes in the collection
        notes = self.collection.getElementsByTagName("note")

        print ("***** {} Notes *****".format(len(notes)))
        t0 = time.time()
        counter = 0

        for note in notes:
            n = Note()

            if note.hasAttribute("handle"):
                n.handle = note.getAttribute("handle")
            if note.hasAttribute("change"):
                n.change = int(note.getAttribute("change"))
            if note.hasAttribute("id"):
                n.id = note.getAttribute("id")
            self.priv = get_priv(note)
            if note.hasAttribute("type"):
                n.type = note.getAttribute("type")

            if len(note.getElementsByTagName('text') ) == 1:
                note_text = note.getElementsByTagName('text')[0]
                n.text = note_text.childNodes[0].data
                # Pick possible url
                n.text, n.url = pick_url(n.text)

            #TODO: 17.10.2018 Viime palaverissa mm. suunniteltiin, että kuolinsyyt 
            # konvertoitaisiin heti Note-nodeiksi sopivalla node-tyypillä
            print(n)

            n.save(self.tx)
            counter += 1

        self.blog.log_event({'title':"Notes", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_media(self):
        # Get all the media in the collection (in Gramps 'object')
        media = self.collection.getElementsByTagName("object")

        print ("***** {} Media *****".format(len(media)))
        t0 = time.time()
        counter = 0

        # Print detail of each media object
        for obj in media:

            o = Media()

            if obj.hasAttribute("handle"):
                o.handle = obj.getAttribute("handle")
            if obj.hasAttribute("change"):
                o.change = int(obj.getAttribute("change"))
            if obj.hasAttribute("id"):
                o.id = obj.getAttribute("id")

            if len(obj.getElementsByTagName('file') ) == 1:
                obj_file = obj.getElementsByTagName('file')[0]

                if obj_file.hasAttribute("src"):
                    o.src = obj_file.getAttribute("src")
                if obj_file.hasAttribute("mime"):
                    o.mime = obj_file.getAttribute("mime")
                if obj_file.hasAttribute("description"):
                    o.description = obj_file.getAttribute("description")

            o.save(self.tx)
            counter += 1

        self.blog.log_event({'title':"Media objects", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_people(self):
        # Get all the people in the collection
        people = self.collection.getElementsByTagName("person")

        person_count = len(people)
        print ("***** {} Persons *****".format(person_count))
        t0 = time.time()
        counter = 0

        # Get details of each person
        for person in people:

            p = Person_gramps()
            name_order = 0

            if person.hasAttribute("handle"):
                p.handle = person.getAttribute("handle")
            if person.hasAttribute("change"):
                p.change = int(person.getAttribute("change"))
            if person.hasAttribute("id"):
                p.id = person.getAttribute("id")
            self.priv = get_priv(person)

            if len(person.getElementsByTagName('gender') ) == 1:
                person_gender = person.getElementsByTagName('gender')[0]
                p.gender = person_gender.childNodes[0].data
            elif len(person.getElementsByTagName('gender') ) > 1:
                self.blog.log_event({'title':"More than one gender in a person",
                                     'level':"WARNING", 'count':p.id})

            if len(person.getElementsByTagName('name') ) >= 1:
                for i in range(len(person.getElementsByTagName('name') )):
                    person_name = person.getElementsByTagName('name')[i]
                    pname = Name()
                    pname.order = name_order
                    name_order += 1

                    if person_name.hasAttribute("alt"):
                        pname.alt = person_name.getAttribute("alt")
                    if person_name.hasAttribute("type"):
                        pname.type = person_name.getAttribute("type")

                    if len(person_name.getElementsByTagName('first') ) == 1:
                        person_first = person_name.getElementsByTagName('first')[0]
                        if len(person_first.childNodes) == 1:
                            pname.firstname = person_first.childNodes[0].data
                        elif len(person_first.childNodes) > 1:
                            self.blog.log_event({'title':"More than one child node in a first name of a person",
                                                'level':"WARNING", 'count':p.id})
                    elif len(person_name.getElementsByTagName('first') ) > 1:
                        self.blog.log_event({'title':"More than one first name in a person",
                                             'level':"WARNING", 'count':p.id})

                    if len(person_name.getElementsByTagName('surname') ) == 1:
                        person_surname = person_name.getElementsByTagName('surname')[0]
                        if len(person_surname.childNodes ) == 1:
                            pname.surname = person_surname.childNodes[0].data
                        elif len(person_surname.childNodes) > 1:
                            self.blog.log_event({'title':"More than one child node in a surname of a person",
                                                 'level':"WARNING", 'count':p.id})
                    elif len(person_name.getElementsByTagName('surname') ) > 1:
                        self.blog.log_event({'title':"More than one surname in a person",
                                             'level':"WARNING", 'count':p.id})

                    if len(person_name.getElementsByTagName('suffix') ) == 1:
                        person_suffix = person_name.getElementsByTagName('suffix')[0]
                        pname.suffix = person_suffix.childNodes[0].data
                    elif len(person_name.getElementsByTagName('suffix') ) > 1:
                        self.blog.log_event({'title':"More than one suffix in a person",
                                             'level':"WARNING", 'count':p.id})

                    p.names.append(pname)

            if len(person.getElementsByTagName('eventref') ) >= 1:
                for i in range(len(person.getElementsByTagName('eventref') )):
                    person_eventref = person.getElementsByTagName('eventref')[i]
                    if person_eventref.hasAttribute("hlink"):
                        p.eventref_hlink.append(person_eventref.getAttribute("hlink"))
                    if person_eventref.hasAttribute("role"):
                        p.eventref_role.append(person_eventref.getAttribute("role"))

            if len(person.getElementsByTagName('objref') ) >= 1:
                for i in range(len(person.getElementsByTagName('objref') )):
                    person_objref = person.getElementsByTagName('objref')[i]
                    if person_objref.hasAttribute("hlink"):
                        p.objref_hlink.append(person_objref.getAttribute("hlink"))

            for person_url in person.getElementsByTagName('url'):
                n = Note()
                n.priv = get_priv(person_url)
                if person_url.hasAttribute("href"):
                    n.url = person_url.getAttribute("href")
                if person_url.hasAttribute("type"):
                    n.type = person_url.getAttribute("type")
                if person_url.hasAttribute("description"):
                    n.text = person_url.getAttribute("description")
                if n.url:
                    p.notes.append(n)

            if len(person.getElementsByTagName('parentin') ) >= 1:
                for i in range(len(person.getElementsByTagName('parentin') )):
                    person_parentin = person.getElementsByTagName('parentin')[i]
                    if person_parentin.hasAttribute("hlink"):
                        p.parentin_hlink.append(person_parentin.getAttribute("hlink"))
                        
            if len(person.getElementsByTagName('noteref') ) >= 1:
                for i in range(len(person.getElementsByTagName('noteref') )):
                    person_noteref = person.getElementsByTagName('noteref')[i]
                    if person_noteref.hasAttribute("hlink"):
                        p.noteref_hlink.append(person_noteref.getAttribute("hlink"))

            if len(person.getElementsByTagName('citationref') ) >= 1:
                for i in range(len(person.getElementsByTagName('citationref') )):
                    person_citationref = person.getElementsByTagName('citationref')[i]
                    if person_citationref.hasAttribute("hlink"):
                        p.citationref_hlink.append(person_citationref.getAttribute("hlink"))

            p.save(self.tx, self.batch_id)
            counter += 1
            # The refnames will be set for these persons 
            self.uniq_ids.append(p.uniq_id)

        self.blog.log_event({'title':"Persons", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_places(self):
        # Get all the places in the collection
        places = self.collection.getElementsByTagName("placeobj")

        print ("***** {} Places *****".format(len(places)))
        t0 = time.time()
        counter = 0

        # Print detail of each placeobj
        for placeobj in places:

            pl = Place()
            # List of upper places in hierarchy as {hlink, dates} dictionaries
            #TODO move in Place and remove Place.placeref_hlink string
            pl.surround_ref = []

            pl.handle = placeobj.getAttribute("handle")
            if placeobj.hasAttribute("change"):
                pl.change = int(placeobj.getAttribute("change"))
            pl.id = placeobj.getAttribute("id")
            pl.type = placeobj.getAttribute("type")

            if len(placeobj.getElementsByTagName('ptitle') ) == 1:
                placeobj_ptitle = placeobj.getElementsByTagName('ptitle')[0]
                pl.ptitle = placeobj_ptitle.childNodes[0].data
            elif len(placeobj.getElementsByTagName('ptitle') ) > 1:
                self.blog.log_event({'title':"More than one ptitle in a place",
                                     'level':"WARNING", 'count':pl.id})

            for placeobj_pname in placeobj.getElementsByTagName('pname'):
                placename = Place_name()
                if placeobj_pname.hasAttribute("value"):
                    placename.name = placeobj_pname.getAttribute("value")
                    if pl.pname == '':
                        # First name is default name for Place node
                        pl.pname = placename.name
                if placeobj_pname.hasAttribute("lang"):
                    placename.lang = placeobj_pname.getAttribute("lang")
                pl.names.append(placename)

            for placeobj_coord in placeobj.getElementsByTagName('coord'):
                if placeobj_coord.hasAttribute("lat") \
                   and placeobj_coord.hasAttribute("long"):
                    coord_lat = placeobj_coord.getAttribute("lat")
                    coord_long = placeobj_coord.getAttribute("long")
                    try:
                        pl.coord = Point(coord_lat, coord_long)
                    except Exception as e:
                        self.blog.log_event({
                            'title':"Invalid coordinates - {}".format(e),
                            'level':"WARNING", 'count':pl.id})

            for placeobj_url in placeobj.getElementsByTagName('url'):
                n = Note()
                n.priv = get_priv(placeobj_url)
                if placeobj_url.hasAttribute("href"):
                    n.url = placeobj_url.getAttribute("href")
                if placeobj_url.hasAttribute("type"):
                    n.type = placeobj_url.getAttribute("type")
                if placeobj_url.hasAttribute("description"):
                    n.text = placeobj_url.getAttribute("description")
                if n.url:
                    pl.notes.append(n)

            for placeobj_placeref in placeobj.getElementsByTagName('placeref'):
                # Traverse links to surrounding places
                hlink = placeobj_placeref.getAttribute("hlink")
                dates = self._extract_daterange(placeobj_placeref)
                pl.surround_ref.append({'hlink':hlink, 'dates':dates})
#             # Piti sallia useita ylempia paikkoja eri päivämäärillä
#             # Tässä vain 1 sallitaan elikä päivämäärää ole
#             if len(placeobj.getElementsByTagName('placeref') ) == 1:
#                 placeobj_placeref = placeobj.getElementsByTagName('placeref')[0]
#                 if placeobj_placeref.hasAttribute("hlink"):
#                     pl.placeref_hlink = placeobj_placeref.getAttribute("hlink")
#                     pl.dates = self._extract_daterange(placeobj_placeref)
#             elif len(placeobj.getElementsByTagName('placeref') ) > 1:
#                 print("Warning: Ignored 2nd placeref in a pl - useita hierarkian yläpuolisia paikkoja")

            for placeobj_noteref in placeobj.getElementsByTagName('noteref'):
                if placeobj_noteref.hasAttribute("hlink"):
                    pl.noteref_hlink.append(placeobj_noteref.getAttribute("hlink"))

            pl.save(self.tx)
            counter += 1

        self.blog.log_event({'title':"Places", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_repositories(self):
        # Get all the repositories in the collection
        repositories = self.collection.getElementsByTagName("repository")

        print ("***** {} Repositories *****".format(len(repositories)))
        t0 = time.time()
        counter = 0

        # Print detail of each repository
        for repository in repositories:

            r = Repository()

            if repository.hasAttribute("handle"):
                r.handle = repository.getAttribute("handle")
            if repository.hasAttribute("change"):
                r.change = repository.getAttribute("change")
            if repository.hasAttribute("id"):
                r.id = repository.getAttribute("id")

            if len(repository.getElementsByTagName('rname') ) == 1:
                repository_rname = repository.getElementsByTagName('rname')[0]
                r.rname = repository_rname.childNodes[0].data
            elif len(repository.getElementsByTagName('rname') ) > 1:
                self.blog.log_event({'title':"More than one rname in a repocitory",
                                     'level':"WARNING", 'count':r.id})

            if len(repository.getElementsByTagName('type') ) == 1:
                repository_type = repository.getElementsByTagName('type')[0]
                r.type =  repository_type.childNodes[0].data
            elif len(repository.getElementsByTagName('type') ) > 1:
                self.blog.log_event({'title':"More than one type in a repocitory",
                                     'level':"WARNING", 'count':r.id})

            for repository_url in repository.getElementsByTagName('url'):
                n = Note()
                n.url = repository_url.getAttribute("href")
                n.type = repository_url.getAttribute("type")
                n.text = repository_url.getAttribute("description")
                if n.url:
                    r.notes.append(n)

            r.save(self.tx)
            counter += 1

        self.blog.log_event({'title':"Repositories", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def handle_sources(self):
        # Get all the sources in the collection
        sources = self.collection.getElementsByTagName("source")

        print ("***** {} Sources *****".format(len(sources)))
        t0 = time.time()
        counter = 0

        # Print detail of each source
        for source in sources:

            s = Source()

            if source.hasAttribute("handle"):
                s.handle = source.getAttribute("handle")
            if source.hasAttribute("change"):
                s.change = source.getAttribute("change")
            if source.hasAttribute("id"):
                s.id = source.getAttribute("id")

            if len(source.getElementsByTagName('stitle') ) == 1:
                source_stitle = source.getElementsByTagName('stitle')[0]
                s.stitle = source_stitle.childNodes[0].data
            elif len(source.getElementsByTagName('stitle') ) > 1:
                self.blog.log_event({'title':"More than one stitle in a source",
                                     'level':"WARNING", 'count':s.id})

#TODO More than one noteref in a source     S0041, S0002
            if len(source.getElementsByTagName('noteref') ) == 1:
                source_noteref = source.getElementsByTagName('noteref')[0]
                if source_noteref.hasAttribute("hlink"):
                    s.noteref_hlink = source_noteref.getAttribute("hlink")
            elif len(source.getElementsByTagName('noteref') ) > 1:
                self.blog.log_event({'title':"More than one noteref in a source",
                                     'level':"WARNING", 'count':s.id})

            if len(source.getElementsByTagName('reporef') ) == 1:
                source_reporef = source.getElementsByTagName('reporef')[0]
                if source_reporef.hasAttribute("hlink"):
                    s.reporef_hlink = source_reporef.getAttribute("hlink")
                if source_reporef.hasAttribute("medium"):
                    s.reporef_medium = source_reporef.getAttribute("medium")
            elif len(source.getElementsByTagName('reporef') ) > 1:
                self.blog.log_event({'title':"More than one reporef in a source",
                                     'level':"WARNING", 'count':s.id})

            s.save(self.tx)
            counter += 1

        self.blog.log_event({'title':"Sources", 'count':counter, 
                             'elapsed':time.time()-t0, 'percent':1})


    def set_sortname_refnames(self):
        ''' Add links from each Person to Refnames and set Person.sortname
        '''

        print ("***** {} Refnames & sortnames *****".format(len(self.uniq_ids)))
        t0 = time.time()
        refname_count = 0
        sortname_count = 0

        for p_id in self.uniq_ids:
            if p_id != None:
                rc, sc = set_person_name_properties(tx=self.tx, uniq_id=p_id)
                refname_count += rc
                sortname_count += sc

        self.blog.log_event({'title':"Refname references", 
                                'count':refname_count, 'elapsed':time.time()-t0})
        self.blog.log_event({'title':"Sorting names", 'count':sortname_count})


    def set_estimated_dates(self):
        ''' Sets estimated lifetime for each Person processed in handle_people
            in transaction
            
            Called from bp.gramps.gramps_loader.xml_to_neo4j
        '''
        print ("***** {} Estimated lifetimes *****".format(len(self.uniq_ids)))
        t0 = time.time()

        cnt = Person_combo.estimate_lifetimes(self.tx, self.uniq_ids)
                            
        self.blog.log_event({'title':"Estimated person lifetimes", 
                             'count':cnt, 'elapsed':time.time()-t0,
                             'percent':1})


    def _extract_daterange(self, obj):
        """ Extract a date information from these kind of date formats:
                <daterange start="1820" stop="1825" quality="estimated"/>
                <datespan start="1840-01-01" stop="1850-06-30" quality="calculated"/>
                <dateval val="1870" type="about"/>

            This is ignored:
                <datestr val="1700-luvulla" />

            Returns: DateRange object or None
        """
        # Note informal dateobj 'datestr' is not processed as all!
        for tag in ['dateval', 'daterange', 'datespan']:
            if len(obj.getElementsByTagName(tag) ) == 1:
                dateobj = obj.getElementsByTagName(tag)[0]
                if tag == 'dateval':
                    if dateobj.hasAttribute("val"):
                        date_start = dateobj.getAttribute("val")
                    date_stop = None
                    if dateobj.hasAttribute("type"):
                        date_type = dateobj.getAttribute("type")
                    else:
                        date_type = None
                else:
                    if dateobj.hasAttribute("start"):
                        date_start = dateobj.getAttribute("start")
                    if dateobj.hasAttribute("stop"):
                        date_stop = dateobj.getAttribute("stop")
                    date_type = None
                if dateobj.hasAttribute("quality"):
                    date_quality = dateobj.getAttribute("quality")
                else:
                    date_quality = None
                logging.debug("Creating {}, date_type={}, quality={}, {} - {}".\
                              format(tag, date_type, date_quality, date_start, date_stop))
                return Gramps_DateRange(tag, date_type, date_quality,
                                        date_start, date_stop)

            elif len(obj.getElementsByTagName(tag) ) > 1:
                self.log(Log("More than one {} tag in an event".format(tag),
                                    level="ERROR"))

        return None