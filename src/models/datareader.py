# coding=UTF-8
# Taapeli harjoitustyö @ Sss 2016
# JMä 12.1.2016

import csv
import logging
import time
import xml.dom.minidom
from models.dbutil import Date
from models.gen.event import Event, Event_for_template
from models.gen.family import Family, Family_for_template
from models.gen.note import Note
from models.gen.person import Person, Name
from models.gen.place import Place
from models.gen.refname import Refname
from models.gen.source_citation import Citation, Repository, Source
from models.gen.user import User


def _poimi_(person_id, event_id, row, url):
    """ Poimitaan henkilötiedot riviltä ja palautetaan Person-objektina
    """

    suku=row['Sukunimi_vakioitu']
    etu=row['Etunimi_vakioitu']

    """ Käräjät-tieto on yhdessä sarakkeessa muodossa 'Tiurala 1666.02.20-22'
        Paikka erotetaan ja aika muunnetaan muotoon '1666-02-20 … 22'
        Päivämäärän korjaus tehdään jos kentässä on väli+numero.
        - TODO Pelkää vuosiluku käräjäpaikkana pitäisi siirtää alkuajaksi
     """
    if ' 1' in row['Käräjät']:
        kpaikka, aika = row['Käräjät'].split(' 1')
        aika = Date.range_str('1' + aika)
    else:
        kpaikka, aika = (row['Käräjät'], '')

    # Luodaan henkilö ja käräjätapahtuma

    p = Person(person_id)
    n = Name(etu, suku)
    p.name.append(n)
    p.name_orig = "{0} /{1}/".format(etu, suku)
    p.occupation = row['Ammatti_vakioitu']
    p.place=row['Paikka_vakioitu']

    e = Event(event_id, 'Käräjät')
    e.name = kpaikka
    e.date = aika
    e.name_orig = row['Käräjät']

    c = Citation()
    c.tyyppi = 'Signum'
    c.oid = row['Signum']
    c.url = url
    c.name_orig = row['Signum']
    c.source = Source()
    c.source.nimi = kpaikka + ' ' + aika
    e.citation = c

    p.events.append(e)
    return p


def henkilolista(pathname):
    """ Lukee csv-tiedostosta aineiston, ja luo kustakin 
        syöttörivistä Person-objektit
    """
    persons = []
    row_nro = 0
    url = ''

    with open(pathname, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, dialect='excel')

        for row in reader:
            if row_nro == 0:
                logging.debug("Tiedosto " + pathname + ", sarakkeet: " + str(reader.fieldnames))
                if not "Käräjät" in reader.fieldnames:
                    raise KeyError('Sarake "Käräjät" puuttuu: ' + str(reader.fieldnames))
            row_nro += 2
            person_id = row_nro
    
            # Onko otsikkorivi? Tästä url kaikille seuraaville riveille
            if row['Käräjät'][:4] == 'http':
                url = row['Käräjät']
                #logging.debug('%s: url=%s' % (person_id, url))
                continue

            # Onko henkilörivi?
            if row['Sukunimi_vakioitu'] == '' and row['Etunimi_vakioitu'] == '':
                logging.warning('%s: nimikentät tyhjiä!' % person_id)
                continue
                            
            p = _poimi_(row_nro, row_nro+1, row, url)
            persons.append(p)

    logging.info(u'%s: %d riviä' % (pathname, row_nro))
    return (persons)


def datastorer(pathname):
    """ Lukee csv-tiedostosta aineiston, ja tallettaa kustakin syöttörivistä
         Person-objektit sisältäen käräjä-Eventit, Citation-viittaukset ja
         Place-paikat
    """
    row_nro = 0
    url = ''

    with open(pathname, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, dialect='excel')

        for row in reader:
            if row_nro == 0:
                logging.debug("Tiedosto " + pathname + ", sarakkeet: " + str(reader.fieldnames))
                if not "Käräjät" in reader.fieldnames:
                    raise KeyError('Sarake "Käräjät" puuttuu: ' + str(reader.fieldnames))
            row_nro += 2
            person_id = row_nro
    
            # Onko otsikkorivi? Tästä url kaikille seuraaville riveille
            if row['Käräjät'][:4] == 'http':
                url = row['Käräjät']
                #logging.debug('%s: url=%s' % (person_id, url))
                continue

            # Onko henkilörivi?
            if row['Sukunimi_vakioitu'] == '' and row['Etunimi_vakioitu'] == '':
                logging.warning('%s: nimikentät tyhjiä!' % person_id)
                continue
                
            p = _poimi_(row_nro, row_nro+1, row, url)
    
            # Tallettaa Person-olion ja siihen sisältyvät Eventit
            # (Person)-[OSALLISTUU]->(Event)
            p.save("User100")

    message ='Talletettu %d riviä tiedostosta %s' % (row_nro, pathname)
    return message


def lue_henkilot(oid=None, names=None, nmax=1000):
    """ Lukee tietokannasta Person- ja Event- objektit näytettäväksi
        
        Palauttaa riveillä listan muuttujia: henkilön tiedot ja lista
        käräjätapahtuman muuttujalistoja
    """
    
    persons = []
    t0 = time.time()
    recs = Person.get_person_events(nmax=nmax, pid=oid, names=names)
    nro = 0
    for rec in recs:
        nro = nro + 1
        # Saatu Person ja collection(Event)
        #Palauttaa riveillä listan muuttujia:
        #n.oid, n.firstname, n.lastname, n.occu, n.place, type(r), events
        #  0      1            2           3       4      5        6
        # 146    Bengt       Bengtsson   soldat   null    OSALLISTUI [[...]]	

        pid = rec['n.id']
        p = Person(pid)
        etu = ""
        suku = ""
        if rec['k.firstname']:
            etu = rec['k.firstname']
        if rec['k.surname']:
            suku = rec['k.surname']
        p.name.append(Name(etu,suku))
#        if rec['n.name_orig']:
#            p.name_orig = rec['n.name_orig']
#         if rec['n.occu']:
#             p.occupation = rec['n.occu']
#         if rec['n.place']:
#             p.place= rec['n.place']

        for ev in rec['events']:
            # 'events' on lista käräjiä, jonka jäseninä on lista muuttujia:
            #[[e.oid, e.kind,  e.name,  e.date,          e.name_orig]...]
            #    0      1        2        3                4
            #[[ 147,  Käräjät, Sakkola, 1669-03-22 … 23, Sakkola 1669.03.22-23]]

            event_id = ev[0]
            if event_id:
                e = Event(event_id, ev[1])
    #             e.name = ev[2]
    #             e.date = ev[3]
    #             e.name_orig = ev[4]
                p.events.append(e)    
    #            logging.info("lue_henkilot: Tapahtuma {}".format(e))

#            c = Citation()
#            c.tyyppi = 'Signum'
#            c.oid = 'Testi3'
#            c.url = url
#            c.source = Source()
#            c.source.nimi = 'Testi3'
#            e.citation = c

        persons.append(p)

    if nro == 0:
        logging.warning("lue_henkilot: ei ketään oid={}, names={}".format(oid, names))
    else:
        logging.info("lue_henkilot: {} henkiloä".format(nro))
        #print ("Lue_henkilot:\n", retList[0])
    logging.debug("TIME lue_henkilot {} sek".format(time.time()-t0))

    return (persons)


def lue_refnames():
    """ Lukee tietokannasta Refname- objektit näytettäväksi
        (n:Refname)-[r]->(m)
    """
    namelist = []
    t0 = time.time()
    recs = Refname.getrefnames()
    for rec in recs:
        namelist.append(rec)

    logging.info("TIME get_refnames {} sek".format(time.time()-t0))

    return (namelist)


def lue_typed_refnames(reftype):
    """ Lukee tietokannasta Refname- objektit näytettäväksi
    """
    namelist = []
    t0 = time.time()
    if not (reftype and reftype != ""):
        raise AttributeError("Mitä referenssityyppiä halutaan?")
    
    recs = Refname.get_typed_refnames(reftype)
# Esimerkki:
# >>> for x in v_names: print(x)
# <Record a.oid=3 a.name='Aabi' a.gender=None a.source='harvinainen' 
#         base=[[2, 'Aapeli', None]] other=[[None, None, None]]>
# <Record a.oid=5 a.name='Aabraham' a.gender='M' a.source='Pojat 1990-luvulla' 
#         base=[[None, None, None]] other=[[None, None, None]]>
# <Record a.oid=6 a.name='Aabrahami' a.gender=None a.source='harvinainen' 
#         base=[[7, 'Aappo', None]] other=[[None, None, None]]>
# >>> for x in v_names: print(x[1])
# Aabrahami
# Aabrami
# Aaca

#a.oid  a.name  a.gender  a.source   base                 other
#                                     [oid, name, gender]  [oid, name, gender]
#-----  ------  --------  --------   ----                 -----
#3493   Aake	F	  Messu- ja  [[null, null, null], [[3495, Aakke, null],
#                         kalenteri   [null, null, null],  [3660, Acatius, null],
#                                     [null, null, null],  [3662, Achat, null],
#                                     [null, null, null],  [3664, Achatius, M],
#                                     [null, null, null],  [3973, Akatius, null],
#                                     [null, null, null],  [3975, Ake, null],
#                                     [null, null, null]]  [3990, Akke, null]]
#3495   Aakke   null     harvinainen [[3493, Aake, F]]    [[null, null, null]]

    for rec in recs:
#        logging.debug("oid={}, name={}, gender={}, source={}, base={}, other={}".\
#               format( rec[0], rec[1],  rec[2],    rec[3],    rec[4],  rec[5]))
        # Luodaan nimi
        r = Refname(rec['a.name'])
        r.oid = rec['a.id']
        if rec['a.gender']:
            r.gender = rec['a.gender']
        if rec['a.source']:
            r.source= rec['a.source']

        # Luodaan mahdollinen kantanimi, johon tämä viittaa (yksi?)
        baselist = []
        for fld in rec['base']:
            if fld[0]:
                b = Refname(fld[1])
                b.oid = fld[0]
                if fld[2]:
                    b.gender = fld[2]
                baselist.append(b)

        # Luodaan lista muista nimistä, joihin tämä viittaa
        otherlist = []
        for fld in rec['other']:
            if fld[0]:
                o = Refname(fld[1])
                o.oid = fld[0]
                if fld[2]:
                    o.gender = fld[2]
                otherlist.append(o)

        namelist.append((r,baselist,otherlist))
    
    logging.info("TIME get_named_refnames {} sek".format(time.time()-t0))

    return (namelist)


def get_people_by_surname(surname):
    people = []
    result = Name.get_people_with_surname(surname)
    for record in result:
        handle = record['handle']
        p = Person()
        p.handle = handle
        p.get_person_and_name_data()
        people.append(p)
        
    return (people)


def get_person_data_by_id(uniq_id):
    p = Person()
    p.uniq_id = uniq_id
    p.get_person_and_name_data_by_id()
    p.get_hlinks_by_id()
    event = Event()
    event.handle = p.eventref_hlink
    event.get_event_data()
    
    events = []
    for link in p.eventref_hlink:
        e = Event_for_template()
        e.uniq_id = link
        e.get_event_data_by_id()
        place = Place()
        place.uniq_id = e.place_hlink
        place.get_place_data_by_id()
        
        e.place = place.pname
        events.append(e)
        
    return (p, events)


def get_families_data_by_id(uniq_id):
    families = []
    
    p = Person()
    p.uniq_id = uniq_id
    p.get_person_and_name_data_by_id()
    if p.gender == 'M':
        result = p.get_his_families_by_id()
    else:
        result = p.get_her_families_by_id()
        
    for record in result:
        f = Family_for_template()
        f.uniq_id = record['uniq_id']
        f.get_family_data_by_id()
        
        spouse = Person()
        if p.gender == 'M':
            spouse.uniq_id = f.mother
        else:
            spouse.uniq_id = f.father
        spouse.get_person_and_name_data_by_id()
        f.spouse_data = spouse
            
        for child_id in f.childref_hlink:
            child = Person()
            child.uniq_id = child_id
            child.get_person_and_name_data_by_id()
            f.children_data.append(child)
            
        families.append(f)
        
    return (p, families)


def handle_citations(collection):
    # Get all the citations in the collection
    citations = collection.getElementsByTagName("citation")
    
    print ("*****Citations*****")
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
            print("Error: More than one dateval tag in a citation")
    
        if len(citation.getElementsByTagName('page') ) == 1:
            citation_page = citation.getElementsByTagName('page')[0]
            c.page = citation_page.childNodes[0].data
        elif len(citation.getElementsByTagName('page') ) > 1:
            print("Error: More than one page tag in a citation")
    
        if len(citation.getElementsByTagName('confidence') ) == 1:
            citation_confidence = citation.getElementsByTagName('confidence')[0]
            c.confidence = citation_confidence.childNodes[0].data
        elif len(citation.getElementsByTagName('confidence') ) > 1:
            print("Error: More than one confidence tag in a citation")
    
        if len(citation.getElementsByTagName('noteref') ) == 1:
            citation_noteref = citation.getElementsByTagName('noteref')[0]
            if citation_noteref.hasAttribute("hlink"):
                c.noteref_hlink = citation_noteref.getAttribute("hlink")
        elif len(citation.getElementsByTagName('noteref') ) > 1:
            print("Error: More than one noteref tag in a citation")
    
        if len(citation.getElementsByTagName('sourceref') ) == 1:
            citation_sourceref = citation.getElementsByTagName('sourceref')[0]
            if citation_sourceref.hasAttribute("hlink"):
                c.sourceref_hlink = citation_sourceref.getAttribute("hlink")
        elif len(citation.getElementsByTagName('sourceref') ) > 1:
            print("Error: More than one sourceref tag in a citation")
                
        c.save()
        counter += 1
        
    msg = "Citations stored: " + str(counter)
        
    return(msg)



def handle_events(collection, userid):
    # Get all the events in the collection
    events = collection.getElementsByTagName("event")
    
    print ("*****Events*****")
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
            print("Error: More than one type tag in an event")
            
        if len(event.getElementsByTagName('description') ) == 1:
            event_description = event.getElementsByTagName('description')[0]
            # If there are description tags, but no description data
            if (len(event_description.childNodes) > 0):
                e.description = event_description.childNodes[0].data
            else:
                e.description = ''
        elif len(event.getElementsByTagName('description') ) > 1:
            print("Error: More than one description tag in an event")
    
        if len(event.getElementsByTagName('dateval') ) == 1:
            event_dateval = event.getElementsByTagName('dateval')[0]
            if event_dateval.hasAttribute("val"):
                e.date = event_dateval.getAttribute("val")
        elif len(event.getElementsByTagName('dateval') ) > 1:
            print("Error: More than one dateval tag in an event")
    
        if len(event.getElementsByTagName('place') ) == 1:
            event_place = event.getElementsByTagName('place')[0]
            if event_place.hasAttribute("hlink"):
                e.place_hlink = event_place.getAttribute("hlink")
        elif len(event.getElementsByTagName('place') ) > 1:
            print("Error: More than one place tag in an event")
    
        if len(event.getElementsByTagName('attribute') ) == 1:
            event_attr = event.getElementsByTagName('attribute')[0]
            if event_attr.hasAttribute("type"):
                e.attr_type = event_attr.getAttribute("type")
            if event_attr.hasAttribute("value"):
                e.attr_value = event_attr.getAttribute("value")
        elif len(event.getElementsByTagName('attribute') ) > 1:
            print("Error: More than one attribute tag in an event")
    
        if len(event.getElementsByTagName('citationref') ) == 1:
            event_citationref = event.getElementsByTagName('citationref')[0]
            if event_citationref.hasAttribute("hlink"):
                e.citationref_hlink = event_citationref.getAttribute("hlink")
        elif len(event.getElementsByTagName('citationref') ) > 1:
            print("Error: More than one citationref tag in an event")
                
        e.save(userid)
        counter += 1
        
        # There can be so many individs to store that Cypher needs a pause
        # time.sleep(0.1)
        
    msg = "Events stored: " + str(counter)
        
    return(msg)


def handle_families(collection):
    # Get all the families in the collection
    families = collection.getElementsByTagName("family")
    
    print ("*****Families*****")
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
            print("Error: More than one rel tag in a family")
    
        if len(family.getElementsByTagName('father') ) == 1:
            family_father = family.getElementsByTagName('father')[0]
            if family_father.hasAttribute("hlink"):
                f.father = family_father.getAttribute("hlink")
        elif len(family.getElementsByTagName('father') ) > 1:
            print("Error: More than one father tag in a family")
    
        if len(family.getElementsByTagName('mother') ) == 1:
            family_mother = family.getElementsByTagName('mother')[0]
            if family_mother.hasAttribute("hlink"):
                f.mother = family_mother.getAttribute("hlink")
        elif len(family.getElementsByTagName('mother') ) > 1:
            print("Error: More than one mother tag in a family")
    
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
                    
        f.save()
        counter += 1
        
    msg = "Families stored: " + str(counter)
        
    return(msg)


def handle_notes(collection):
    # Get all the notes in the collection
    notes = collection.getElementsByTagName("note")

    print ("*****Notes*****")
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
        if note.hasAttribute("type"):
            n.type = note.getAttribute("type")
    
        if len(note.getElementsByTagName('text') ) == 1:
            note_text = note.getElementsByTagName('text')[0]
            n.text = note_text.childNodes[0].data
            
        n.save()
        counter += 1
        
    msg = "Notes stored: " + str(counter)
        
    return(msg)


def handle_people(collection, userid):
    # Get all the people in the collection
    people = collection.getElementsByTagName("person")
    
    print ("*****People*****")
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
    
        if len(person.getElementsByTagName('gender') ) == 1:
            person_gender = person.getElementsByTagName('gender')[0]
            p.gender = person_gender.childNodes[0].data
        elif len(person.getElementsByTagName('gender') ) > 1:
            print("Error: More than one gender tag in a person")
    
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
                        print("Error: More than one child node in a first name of a person")
                elif len(person_name.getElementsByTagName('first') ) > 1:
                    print("Error: More than one first name in a person")
    
                if len(person_name.getElementsByTagName('surname') ) == 1:
                    person_surname = person_name.getElementsByTagName('surname')[0]
                    if len(person_surname.childNodes ) == 1:
                        pname.surname = person_surname.childNodes[0].data
                    elif len(person_surname.childNodes) > 1:
                        print("Error: More than one child node in a surname of a person")
                elif len(person_name.getElementsByTagName('surname') ) > 1:
                    print("Error: More than one surname in a person")
    
                if len(person_name.getElementsByTagName('suffix') ) == 1:
                    person_suffix = person_name.getElementsByTagName('suffix')[0]
                    pname.suffix = person_suffix.childNodes[0].data
                elif len(person_name.getElementsByTagName('suffix') ) > 1:
                    print("Error: More than one suffix in a person")
                    
                p.name.append(pname)
    
        if len(person.getElementsByTagName('eventref') ) >= 1:
            for i in range(len(person.getElementsByTagName('eventref') )):
                person_eventref = person.getElementsByTagName('eventref')[i]
                if person_eventref.hasAttribute("hlink"):
                    p.eventref_hlink.append(person_eventref.getAttribute("hlink"))
                if person_eventref.hasAttribute("role"):
                    p.eventref_role.append(person_eventref.getAttribute("role"))
                    
        if len(person.getElementsByTagName('parentin') ) >= 1:
            for i in range(len(person.getElementsByTagName('parentin') )):
                person_parentin = person.getElementsByTagName('parentin')[i]
                if person_parentin.hasAttribute("hlink"):
                    p.parentin_hlink.append(person_parentin.getAttribute("hlink"))
    
        if len(person.getElementsByTagName('citationref') ) >= 1:
            for i in range(len(person.getElementsByTagName('citationref') )):
                person_citationref = person.getElementsByTagName('citationref')[i]
                if person_citationref.hasAttribute("hlink"):
                    p.citationref_hlink.append(person_citationref.getAttribute("hlink"))
                    
        p.save(userid)
        counter += 1
        
        # There can be so many individs to store that Cypher needs a pause
        # time.sleep(0.1)
        
    msg = "People stored: " + str(counter)
        
    return(msg)



def handle_places(collection):
    # Get all the places in the collection
    places = collection.getElementsByTagName("placeobj")
    
    print ("*****Places*****")
    counter = 0
    
    # Print detail of each placeobj
    for placeobj in places:
        
        place = Place()

        if placeobj.hasAttribute("handle"):
            place.handle = placeobj.getAttribute("handle")
        if placeobj.hasAttribute("change"):
            place.change = placeobj.getAttribute("change")
        if placeobj.hasAttribute("id"):
            place.id = placeobj.getAttribute("id")
        if placeobj.hasAttribute("type"):
            place.type = placeobj.getAttribute("type")
    
        if len(placeobj.getElementsByTagName('ptitle') ) == 1:
            placeobj_ptitle = placeobj.getElementsByTagName('ptitle')[0]
            place.ptitle = placeobj_ptitle.childNodes[0].data
        elif len(placeobj.getElementsByTagName('ptitle') ) > 1:
            print("Error: More than one ptitle in a place")
    
        if len(placeobj.getElementsByTagName('pname') ) >= 1:
            for i in range(len(placeobj.getElementsByTagName('pname') )):
                placeobj_pname = placeobj.getElementsByTagName('pname')[i]
                if placeobj_pname.hasAttribute("value"):
                    place.pname = placeobj_pname.getAttribute("value")
    
        if len(placeobj.getElementsByTagName('placeref') ) == 1:
            placeobj_placeref = placeobj.getElementsByTagName('placeref')[0]
            if placeobj_placeref.hasAttribute("hlink"):
                place.placeref_hlink = placeobj_placeref.getAttribute("hlink")
        elif len(placeobj.getElementsByTagName('placeref') ) > 1:
            print("Error: More than one placeref in a place")
                
        place.save()
        counter += 1
        
        # There can be so many individs to store that Cypher needs a pause
        # time.sleep(0.1)
        
    msg = "Places stored: " + str(counter)
        
    return(msg)


def handle_repositories(collection):
    # Get all the repositories in the collection
    repositories = collection.getElementsByTagName("repository")
    
    print ("*****Repositories*****")
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
            print("Error: More than one rname in a repository")
    
        if len(repository.getElementsByTagName('type') ) == 1:
            repository_type = repository.getElementsByTagName('type')[0]
            r.type =  repository_type.childNodes[0].data
        elif len(repository.getElementsByTagName('type') ) > 1:
            print("Error: More than one type in a repository")
    
        r.save()
        counter += 1
        
    msg = "Repositories stored: " + str(counter)
        
    return(msg)


def handle_sources(collection):
    # Get all the sources in the collection
    sources = collection.getElementsByTagName("source")
    
    print ("*****Sources*****")
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
            print("Error: More than one stitle in a source")
    
        if len(source.getElementsByTagName('noteref') ) == 1:
            source_noteref = source.getElementsByTagName('noteref')[0]
            if source_noteref.hasAttribute("hlink"):
                s.noteref_hlink = source_noteref.getAttribute("hlink")
        elif len(source.getElementsByTagName('noteref') ) > 1:
            print("Error: More than one noteref in a source")
    
        if len(source.getElementsByTagName('reporef') ) == 1:
            source_reporef = source.getElementsByTagName('reporef')[0]
            if source_reporef.hasAttribute("hlink"):
                s.reporef_hlink = source_reporef.getAttribute("hlink")
            if source_reporef.hasAttribute("medium"):
                s.reporef_medium = source_reporef.getAttribute("medium")
        elif len(source.getElementsByTagName('reporef') ) > 1:
            print("Error: More than one reporef in a source")
    
        s.save()
        counter += 1
        
    msg = "Sources stored: " + str(counter)
        
    return(msg)


def xml_to_neo4j(pathname, userid='Taapeli'):
    """ Lukee xml-tiedostosta aineiston, ja tallettaa kustakin syöttörivistä
         tiedot Neo4j-kantaan
    """
    
    DOMTree = xml.dom.minidom.parse(open(pathname))
    collection = DOMTree.documentElement
    
    # Create User if needed
    user = User(userid)
    user.save()

    result = handle_notes(collection)
    print("Notes stored: " + str(result))
    result = handle_repositories(collection)
    print("Repositories stored: " + str(result))
    result = handle_places(collection)
    print("Places stored: " + str(result))
    result = handle_sources(collection)
    print("Sources stored: " + str(result))
    result = handle_citations(collection)
    print("Citations stored: " + str(result))
    result = handle_events(collection, userid)
    print("Events stored: " + str(result))
    result = handle_people(collection, userid)
    print("People stored: " + str(result))
    result = handle_families(collection)
    print("Families stored: " + str(result))
    
    msg = "XML file stored to Neo4j database"

    return(msg)    
        