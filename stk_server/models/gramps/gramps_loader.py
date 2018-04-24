# coding=UTF-8
#
# Methods to import all data from Gramps xml file
#
# @author: Jorma Haapasalo <jorma.haapasalo@pp.inet.fi>

import logging
import time
import xml.dom.minidom

from models.gen.event import Event
from models.gen.family import Family
from models.gen.note import Note
from models.gen.media import Media
from models.gen.person import Person, Name, Weburl
from models.gen.place import Place, Place_name, Point
from models.gen.dates import Gramps_DateRange
from models.gen.source_citation import Citation, Repository, Source
from models.dataupdater import set_confidence_value, set_person_refnames
import shareds


def xml_to_neo4j(pathname, userid='Taapeli'):
    """ Reads a xml backup file from Gramps, and saves the information to db """

    # Make a precheck for cleaning problematic delimiters
    a = pathname.split(".")
    pathname2 = a[0] + "_pre." + a[1]

    file1 = open(pathname, encoding='utf-8')
    file2 = open(pathname2, "w", encoding='utf-8')

    for line in file1:
        # Already \' in line
        if not line.find("\\\'") > 0:
            # Replace ' with \'
            line = line.replace("\'", "\\\'")
        file2.write(line)

    file1.close()
    file2.close()

    t0 = time.time()

    ''' Get XML DOM parser '''
    DOMTree = xml.dom.minidom.parse(open(pathname2, encoding='utf-8'))

    ''' Start DOM elements handler transaction '''
    handler = DOM_handler(DOMTree.documentElement, userid)
    
    use_transaction = True  # Voi testata Falsella
    if use_transaction:
        handler.begin_tx(shareds.driver.session())
    else:
        handler.tx = shareds.driver.session()
    
    handler.put_message("Storing XML file to Neo4j database")
    # Run report shows columns split by ':' 
    handler.put_message("Kohteita:kpl:aika / sek")

    handler.handle_notes()
    handler.handle_repositories()
    handler.handle_media()

    handler.handle_places()
    handler.handle_sources()
    handler.handle_citations()

    handler.handle_events()
    handler.handle_people()
    handler.handle_families()

    if use_transaction:
        handler.commit()

    # Set person confidence values (for all persons!)
    handler.begin_tx(shareds.driver.session())
    result_text = set_confidence_value(handler.tx)
    handler.put_message(result_text)
    # Set Refname links (for imported persons)
    result_text = handler.set_refnames()
    handler.put_message(result_text)
    handler.commit()

    msg = " - Total time:: {:.4f}".format(time.time()-t0)
    handler.put_message(msg)
    return(handler.get_messages())

# -----------------------------------------------------------------------------

class DOM_handler():
    """ XML DOM elements handler

        Creates transaction and collects status messages
    """
    def __init__(self, DOM_collection, current_user):
        """ Set DOM collection and username """
        self.collection = DOM_collection    # XML documentElement
        self.username = current_user        # current username

        self.uniq_ids = []                  # List of processed Person node
                                            # unique id's
        self.msg = []                       # List of result messages


    def begin_tx(self, session):
        self.tx = session.begin_transaction()

    def commit(self):
        """ Commit transaction """
        try:
            self.tx.commit()
        except Exception as e:
            self.put_message("Talletus tietokantaan ei onnistunut: {}", "ERROR", e)

    def put_message(self, msg, level="INFO", oid=""):
        ''' Add info message to messages list '''
        if oid:
            msg = "{} '{}'".format(msg, oid)
        if level == "INFO":
            logging.info(msg)
        elif level == "WARINING":
            logging.warning(msg)
        else:
            logging.error(msg)
        print("{}: {}".format(level, msg))
        self.msg.append(str(msg))

    def get_messages(self):
        ''' Return all info messages '''
        return self.msg


    # XML subtree handlers

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
                c.change = citation.getAttribute("change")
            if citation.hasAttribute("id"):
                c.id = citation.getAttribute("id")

            if len(citation.getElementsByTagName('dateval') ) == 1:
                citation_dateval = citation.getElementsByTagName('dateval')[0]
                if citation_dateval.hasAttribute("val"):
                    c.dateval = citation_dateval.getAttribute("val")
            elif len(citation.getElementsByTagName('dateval') ) > 1:
                self.put_message("More than one dateval tag in a citation", "WARNING", c.id)

            if len(citation.getElementsByTagName('page') ) == 1:
                citation_page = citation.getElementsByTagName('page')[0]
                c.page = citation_page.childNodes[0].data
            elif len(citation.getElementsByTagName('page') ) > 1:
                self.put_message("More than one page tag in a citation", "WARNING", c.id)

            if len(citation.getElementsByTagName('confidence') ) == 1:
                citation_confidence = citation.getElementsByTagName('confidence')[0]
                c.confidence = citation_confidence.childNodes[0].data
            elif len(citation.getElementsByTagName('confidence') ) > 1:
                self.put_message("More than one confidence tag in a citation", "WARNING", c.id)

            if len(citation.getElementsByTagName('noteref') ) >= 1:
                for i in range(len(citation.getElementsByTagName('noteref') )):
                    citation_noteref = citation.getElementsByTagName('noteref')[i]
                    if citation_noteref.hasAttribute("hlink"):
                        c.noteref_hlink.append(citation_noteref.getAttribute("hlink"))

            if len(citation.getElementsByTagName('sourceref') ) == 1:
                citation_sourceref = citation.getElementsByTagName('sourceref')[0]
                if citation_sourceref.hasAttribute("hlink"):
                    c.sourceref_hlink = citation_sourceref.getAttribute("hlink")
            elif len(citation.getElementsByTagName('sourceref') ) > 1:
                self.put_message("More than one sourceref tag in a citation", "WARNING", c.id)

            c.save(self.tx)
            counter += 1

        msg = "Citations: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


    def handle_events(self):
        # Get all the events in the collection
        events = self.collection.getElementsByTagName("event")

        print ("***** {} Events *****".format(len(events)))
        t0 = time.time()
        counter = 0

        # Print detail of each event
        for event in events:

            e = Event()

            if event.hasAttribute("handle"):
                e.handle = event.getAttribute("handle")
            if event.hasAttribute("change"):
                e.change = event.getAttribute("change")
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
                self.put_message("More than one type tag in an event", "WARNING", e.id)

            if len(event.getElementsByTagName('description') ) == 1:
                event_description = event.getElementsByTagName('description')[0]
                # If there are description tags, but no description data
                if (len(event_description.childNodes) > 0):
                    e.description = event_description.childNodes[0].data
                else:
                    e.description = ''
            elif len(event.getElementsByTagName('description') ) > 1:
                self.put_message("More than one description tag in an event", "WARNING", e.id)

            """ Dates:
                <daterange start="1820" stop="1825" quality="estimated"/>
                <datespan start="1840-01-01" stop="1850-06-30" quality="calculated"/>
                <dateval val="1870" type="about"/>
                <datestr val="1700-luvulla" />    # Not processed!
            """
            e.dates = self._extract_daterange(event)
            # e.date = e.dates.estimate() # TODO: remove this, not needed!

            if len(event.getElementsByTagName('place') ) == 1:
                event_place = event.getElementsByTagName('place')[0]
                if event_place.hasAttribute("hlink"):
                    e.place_hlink = event_place.getAttribute("hlink")
            elif len(event.getElementsByTagName('place') ) > 1:
                self.put_message("More than one place tag in an event", "WARNING", e.id)

            if len(event.getElementsByTagName('attribute') ) == 1:
                event_attr = event.getElementsByTagName('attribute')[0]
                if event_attr.hasAttribute("type"):
                    e.attr_type = event_attr.getAttribute("type")
                if event_attr.hasAttribute("value"):
                    e.attr_value = event_attr.getAttribute("value")
            elif len(event.getElementsByTagName('attribute') ) > 1:
                self.put_message("More than one attribute tag in an event", "WARNING", e.id)

            if len(event.getElementsByTagName('noteref') ) == 1:
                event_noteref = event.getElementsByTagName('noteref')[0]
                if event_noteref.hasAttribute("hlink"):
                    e.noteref_hlink = event_noteref.getAttribute("hlink")
            elif len(event.getElementsByTagName('noteref') ) > 1:
                self.put_message("More than one noteref tag in an event", "WARNING", e.id)

            if len(event.getElementsByTagName('citationref') ) == 1:
                event_citationref = event.getElementsByTagName('citationref')[0]
                if event_citationref.hasAttribute("hlink"):
                    e.citationref_hlink = event_citationref.getAttribute("hlink")
            elif len(event.getElementsByTagName('citationref') ) > 1:
                self.put_message("More than one citationref tag in an event", "WARNING", e.id)

            if len(event.getElementsByTagName('objref') ) == 1:
                event_objref = event.getElementsByTagName('objref')[0]
                if event_objref.hasAttribute("hlink"):
                    e.objref_hlink = event_objref.getAttribute("hlink")
            elif len(event.getElementsByTagName('objref') ) > 1:
                self.put_message("More than one objref tag in an event", "WARNING", e.id)

            e.save(self.username, self.tx)
            counter += 1

        msg = "Events: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


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
                f.change = family.getAttribute("change")
            if family.hasAttribute("id"):
                f.id = family.getAttribute("id")

            if len(family.getElementsByTagName('rel') ) == 1:
                family_rel = family.getElementsByTagName('rel')[0]
                if family_rel.hasAttribute("type"):
                    f.rel_type = family_rel.getAttribute("type")
            elif len(family.getElementsByTagName('rel') ) > 1:
                self.put_message("More than one rel tag in a family", "WARNING", f.id)

            if len(family.getElementsByTagName('father') ) == 1:
                family_father = family.getElementsByTagName('father')[0]
                if family_father.hasAttribute("hlink"):
                    f.father = family_father.getAttribute("hlink")
            elif len(family.getElementsByTagName('father') ) > 1:
                self.put_message("More than one father tag in a family", "WARNING", f.id)

            if len(family.getElementsByTagName('mother') ) == 1:
                family_mother = family.getElementsByTagName('mother')[0]
                if family_mother.hasAttribute("hlink"):
                    f.mother = family_mother.getAttribute("hlink")
            elif len(family.getElementsByTagName('mother') ) > 1:
                self.put_message("More than one mother tag in a family", "WARNING", f.id)

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

            f.save(self.tx)
            counter += 1

        msg = "Families: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


    def handle_notes(self):
        # Get all the notes in the collection
        notes = self.collection.getElementsByTagName("note")

        print ("***** {} Notes *****".format(len(notes)))
        t0 = time.time()
        counter = 0

        # Print detail of each note
        for note in notes:

            n = Note()

            if note.hasAttribute("handle"):
                n.handle = note.getAttribute("handle")
            if note.hasAttribute("change"):
                n.change = note.getAttribute("change")
            if note.hasAttribute("id"):
                n.id = note.getAttribute("id")
            if note.hasAttribute("priv"):
                n.priv = note.getAttribute("priv")
            if note.hasAttribute("type"):
                n.type = note.getAttribute("type")

            if len(note.getElementsByTagName('text') ) == 1:
                note_text = note.getElementsByTagName('text')[0]
                n.text = note_text.childNodes[0].data

            n.save(self.tx)
            counter += 1

        msg = "Notes: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


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
                o.change = obj.getAttribute("change")
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

        msg = "Media objects: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


    def handle_people(self):
        # Get all the people in the collection
        people = self.collection.getElementsByTagName("person")

        print ("***** {} Persons *****".format(len(people)))
        t0 = time.time()
        counter = 0

        # Print detail of each person
        for person in people:

            p = Person()

            if person.hasAttribute("handle"):
                p.handle = person.getAttribute("handle")
            if person.hasAttribute("change"):
                p.change = person.getAttribute("change")
            if person.hasAttribute("id"):
                p.id = person.getAttribute("id")
            if person.hasAttribute("priv"):
                p.priv = person.getAttribute("priv")

            if len(person.getElementsByTagName('gender') ) == 1:
                person_gender = person.getElementsByTagName('gender')[0]
                p.gender = person_gender.childNodes[0].data
            elif len(person.getElementsByTagName('gender') ) > 1:
                self.put_message("More than one gender tag in a person", "WARNING", p.id)

            if len(person.getElementsByTagName('name') ) >= 1:
                for i in range(len(person.getElementsByTagName('name') )):
                    person_name = person.getElementsByTagName('name')[i]
                    pname = Name()
                    if person_name.hasAttribute("alt"):
                        pname.alt = person_name.getAttribute("alt")
                    if person_name.hasAttribute("type"):
                        pname.type = person_name.getAttribute("type")

                    if len(person_name.getElementsByTagName('first') ) == 1:
                        person_first = person_name.getElementsByTagName('first')[0]
                        if len(person_first.childNodes) == 1:
                            pname.firstname = person_first.childNodes[0].data
                        elif len(person_first.childNodes) > 1:
                            self.put_message("More than one child node in a first name of a person", 
                                             "WARNING", p.id)
                    elif len(person_name.getElementsByTagName('first') ) > 1:
                        self.put_message("More than one first name in a person", "WARNING", p.id)

                    if len(person_name.getElementsByTagName('surname') ) == 1:
                        person_surname = person_name.getElementsByTagName('surname')[0]
                        if len(person_surname.childNodes ) == 1:
                            pname.surname = person_surname.childNodes[0].data
                        elif len(person_surname.childNodes) > 1:
                            self.put_message("More than one child node in a surname of a person", 
                                             "WARNING", p.id)
                    elif len(person_name.getElementsByTagName('surname') ) > 1:
                        self.put_message("More than one surname in a person")

                    if len(person_name.getElementsByTagName('suffix') ) == 1:
                        person_suffix = person_name.getElementsByTagName('suffix')[0]
                        pname.suffix = person_suffix.childNodes[0].data
                    elif len(person_name.getElementsByTagName('suffix') ) > 1:
                        self.put_message("More than one suffix in a person", "WARNING", p.id)

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

            if len(person.getElementsByTagName('url') ) >= 1:
                for i in range(len(person.getElementsByTagName('url') )):
                    weburl = Weburl()
                    person_url = person.getElementsByTagName('url')[i]
                    if person_url.hasAttribute("priv"):
                        weburl.priv = person_url.getAttribute("priv")
                    if person_url.hasAttribute("href"):
                        weburl.href = person_url.getAttribute("href")
                    if person_url.hasAttribute("type"):
                        weburl.type = person_url.getAttribute("type")
                    if person_url.hasAttribute("description"):
                        weburl.description = person_url.getAttribute("description")
                    p.urls.append(weburl)

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

            p.save(self.username, self.tx)
            counter += 1
            # The refnames will be set for these persons 
            self.uniq_ids.append(p.uniq_id)

        msg = "Persons: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


    def handle_places(self):
        # Get all the places in the collection
        places = self.collection.getElementsByTagName("placeobj")

        print ("***** {} Places *****".format(len(places)))
        t0 = time.time()
        counter = 0

        # Print detail of each placeobj
        for placeobj in places:

            place = Place()
            # List of upper places in hierarchy as {hlink, dates} dictionaries
            #TODO move in Place and remove Place.placeref_hlink string
            place.surround_ref = []

            place.handle = placeobj.getAttribute("handle")
            if placeobj.hasAttribute("change"):
                place.change = int(placeobj.getAttribute("change"))
            place.id = placeobj.getAttribute("id")
            place.type = placeobj.getAttribute("type")

            if len(placeobj.getElementsByTagName('ptitle') ) == 1:
                placeobj_ptitle = placeobj.getElementsByTagName('ptitle')[0]
                place.ptitle = placeobj_ptitle.childNodes[0].data
            elif len(placeobj.getElementsByTagName('ptitle') ) > 1:
                self.put_message("More than one ptitle in a place")

            for placeobj_pname in placeobj.getElementsByTagName('pname'):
                placename = Place_name()
                if placeobj_pname.hasAttribute("value"):
                    placename.name = placeobj_pname.getAttribute("value")
                    if place.pname == '':
                        # First name is default name for Place node
                        place.pname = placename.name
                if placeobj_pname.hasAttribute("lang"):
                    placename.lang = placeobj_pname.getAttribute("lang")
                place.names.append(placename)

            for placeobj_coord in placeobj.getElementsByTagName('coord'):
                if placeobj_coord.hasAttribute("lat") \
                   and placeobj_coord.hasAttribute("long"):
                    coord_lat = placeobj_coord.getAttribute("lat")
                    coord_long = placeobj_coord.getAttribute("long")
                    place.coord = Point(coord_lat, coord_long)

            for placeobj_url in placeobj.getElementsByTagName('url'):
                weburl = Weburl()
                if placeobj_url.hasAttribute("priv"):
                    weburl.priv = placeobj_url.getAttribute("priv")
                if placeobj_url.hasAttribute("href"):
                    weburl.href = placeobj_url.getAttribute("href")
                if placeobj_url.hasAttribute("type"):
                    weburl.type = placeobj_url.getAttribute("type")
                if placeobj_url.hasAttribute("description"):
                    weburl.description = placeobj_url.getAttribute("description")
                place.urls.append(weburl)

            for placeobj_placeref in placeobj.getElementsByTagName('placeref'):
                # Traverse links to surrounding places
                hlink = placeobj_placeref.getAttribute("hlink")
                dates = self._extract_daterange(placeobj_placeref)
                place.surround_ref.append({'hlink':hlink, 'dates':dates})
#             # Piti sallia useita ylempia paikkoja eri päivämäärillä
#             # Tässä vain 1 sallitaan elikä päivämäärää ole
#             if len(placeobj.getElementsByTagName('placeref') ) == 1:
#                 placeobj_placeref = placeobj.getElementsByTagName('placeref')[0]
#                 if placeobj_placeref.hasAttribute("hlink"):
#                     place.placeref_hlink = placeobj_placeref.getAttribute("hlink")
#                     place.dates = self._extract_daterange(placeobj_placeref)
#             elif len(placeobj.getElementsByTagName('placeref') ) > 1:
#                 print("Warning: Ignored 2nd placeref in a place - useita hierarkian yläpuolisia paikkoja")

            for placeobj_noteref in placeobj.getElementsByTagName('noteref'):
                if placeobj_noteref.hasAttribute("hlink"):
                    place.noteref_hlink.append(placeobj_noteref.getAttribute("hlink"))

            place.save(self.tx)
            counter += 1

        msg = "Places: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


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
                self.put_message("More than one rname in a repository", "WARNING", r.id)

            if len(repository.getElementsByTagName('type') ) == 1:
                repository_type = repository.getElementsByTagName('type')[0]
                r.type =  repository_type.childNodes[0].data
            elif len(repository.getElementsByTagName('type') ) > 1:
                self.put_message("More than one type in a repository", "WARNING", r.id)

            if len(repository.getElementsByTagName('url') ) >= 1:
                for i in range(len(repository.getElementsByTagName('url') )):
                    repository_url = repository.getElementsByTagName('url')[i]
                    if repository_url.hasAttribute("href"):
                        r.url_href.append(repository_url.getAttribute("href"))
                    if repository_url.hasAttribute("type"):
                        r.url_type.append(repository_url.getAttribute("type"))
                    if repository_url.hasAttribute("description"):
                        r.url_description.append(repository_url.getAttribute("description"))

            r.save(self.tx)
            counter += 1

        msg = "Repositories: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


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
                self.put_message("More than one stitle in a source", "WARNING", s.id)

            if len(source.getElementsByTagName('noteref') ) == 1:
                source_noteref = source.getElementsByTagName('noteref')[0]
                if source_noteref.hasAttribute("hlink"):
                    s.noteref_hlink = source_noteref.getAttribute("hlink")
            elif len(source.getElementsByTagName('noteref') ) > 1:
                self.put_message("More than one noteref in a source", "WARNING", s.id)

            if len(source.getElementsByTagName('reporef') ) == 1:
                source_reporef = source.getElementsByTagName('reporef')[0]
                if source_reporef.hasAttribute("hlink"):
                    s.reporef_hlink = source_reporef.getAttribute("hlink")
                if source_reporef.hasAttribute("medium"):
                    s.reporef_medium = source_reporef.getAttribute("medium")
            elif len(source.getElementsByTagName('reporef') ) > 1:
                self.put_message("More than one reporef in a source", "WARNING", s.id)

            s.save(self.tx)
            counter += 1

        msg = "Sources: {} : {:.4f}".format(counter, time.time()-t0)
        self.put_message(msg)


    def set_refnames(self):
        ''' Add links from each Person to Refnames '''

        print ("***** {} Refnames *****".format(len(self.uniq_ids)))
        t0 = time.time()
        self.namecount = 0

        for p_id in self.uniq_ids:
            set_person_refnames(self, p_id)

        msg = "Refname references: {} : {:.4f}".format(self.namecount, time.time()-t0)
        return msg


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
                self.put_message("More than one {} tag in an event".format(tag), "ERROR")

        return None