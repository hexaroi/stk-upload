'''
    Person compound includes operations for accessing
    - Person and her Names
    - related Events and Places
    
    Note. Use Person_combo.from_node(node) to create a Person_combo instance
          ( defined as classmethod Person.from_node() )

    class gen.person_combo.Person_combo(Person): 
        - __init__()
        - get_person_w_names(self)      Luetaan kaikki henkilön tiedot ja nimet
        - get_people_with_same_birthday() Etsi henkilöt, joiden syntymäaika on sama
        - get_people_with_same_deathday() Etsi henkilöt, joiden kuolinaika on sama
        - get_people_wo_birth()         Luetaan henkilöt ilman syntymätapahtumaa
        - get_old_people_top()          Henkilöt joilla syntymä- ja kuolintapahtuma
        - get_confidence (uniq_id=None) Henkilön tapahtumien luotettavuustiedot
        - set_confidence (self, tx)     Asetetaan henkilön tietojen luotettavuusarvio
        - get_person_events (nmax=0, pid=None, names=None)
                                        Luetaan henkilöitä tapahtumineen
        - get_person_combos (keys, currentuser, take_refnames=False, order=0):
                                        Read Persons with Names, Events and Refnames
        - get_my_places(self)              Tallettaa liittyvät Paikat henkilöön
        - get_all_citation_source(self) Tallettaa liittyvät Cition ja Source
        - get_all_notes(self)           Tallettaa liittyvät Note ja Weburl
        - get_family_members (uniq_id)  Luetaan liittyvät Names, Families and Events
        - get_refnames(pid)             Luetaan liittyvät Refnames
        - get_ref_weburls(pid_list)     Luetaan mainittuihin nodeihin liittyvät Weburlit
        - set_estimated_dates()         Aseta est_birth ja est_death
        - save(self, username, tx)      Tallettaa Person, Names, Events ja Citations

    Not in use or obsolete:
        - get_citation_id(self)         Luetaan henkilöön liittyvän viittauksen id
        - get_event_data_by_id(self)    Luetaan henkilön tapahtumien id:t
        - get_her_families_by_id(self)  Luetaan naisen perheiden id:t
        - get_his_families_by_id(self)  Luetaan miehen perheiden id:t
        - get_hlinks_by_id(self)        Luetaan henkilön linkit (_hlink)
        - get_media_id(self)            Luetaan henkilön tallenteen id
        - get_parentin_id(self)         Luetaan henkilön syntymäperheen id
        - get_person_and_name_data_by_id(self)
                                        Luetaan kaikki henkilön tiedot ja nimet
        - get_points_for_compared_data(self, comp_person, print_out=True)
                                        Tulostaa kahden henkilön tiedot vieretysten
        - print_compared_data(self, comp_person, print_out=True) 
                                        Tulostaa kahden henkilön tiedot vieretysten


        - save() # with relations to UserProfile, Person, Place, Note, Citation, Media


@author: Jorma Haapasalo <jorma.haapasalo@pp.inet.fi> & Juha Mäkeläinen
'''

import datetime
from sys import stderr
#import logging

import shareds
import models.dbutil

from .person import Person
from .person_name import Name
from .cypher import Cypher_person
from .place import Place, Place_name
from .dates import DateRange
from .weburl import Weburl

from models.cypher_gramps import Cypher_person_w_handle

class Person_combo(Person):
    """ Henkilö
    
        From Person.__init__(): 
            uniq_id, handle, id, priv, gender, confidence, change

        Other properties:
            names[]:
               alt             str muun nimen nro
               type            str nimen tyyppi
               firstname       str etunimi
               #refname        str referenssinimi (entinen toteutus)
               surname         str sukunimi
               suffix          str patronyymi
            confidence         str tietojen luotettavuus
            est_birth          str arvioitu syntymäaika
            est_death          str arvioitu kuolinaika

        The indexes of referred objects are in variables:
            eventref_hlink[]   int tapahtuman uniq_id, rooli 
            - eventref_role[]  str edellisen rooli
            objref_hlink[]     int median uniq_id
            urls[]             list of Weburl nodes
                priv           int 1 = salattu tieto
                href           str osoite
                type           str tyyppi
                description    str kuvaus
            parentin_hlink[]   int vanhempien uniq_id
            noteref_hlink[]    int huomautuksen uniq_id
            citationref_hlink[] int viittauksen uniq_id            


    #TODO: urls[] list should contain Weburl instances
     """

    def __init__(self):
        """ Luo uuden person-instanssin
        
        """
        Person.__init__(self)

        self.events = []                # For creating display sets
        self.citations = []
        self.eventref_hlink = []        # Gramps event handles
        self.eventref_role = []
        self.objref_hlink = []
        self.urls = []
        self.parentin_hlink = []
        self.noteref_hlink = []
        self.citationref_hlink = []
        self.est_birth = ''
        self.est_death = ''


    @staticmethod
    def get_person_paths(uniq_id):
        ''' Read a person and paths for all connected nodes
        '''
        query = """
match path = (p) -[*]-> (x)
    where id(p) = $pid 
return path"""
#         query2="""
# match path = (p) -[*]-> () where id(p) = $pid 
#     with p, relationships(path) as rel
# return extract(x IN rel | [id(startnode(x)), type(x), x.role, endnode(x)]) as relations"""
        return  shareds.driver.session().run(query, pid=uniq_id)

    @staticmethod
    def get_person_paths_apoc(uniq_id):
        ''' Read a person and paths for all connected nodes
        '''
        all_nodes_query_w_apoc="""
MATCH (p:Person) WHERE id(p) = $pid
CALL apoc.path.subgraphAll(p, {maxLevel:4, 
        relationshipFilter: 'EVENT>|NAME>|PLACE>|CITATION>|SOURCE>|<CHILD|<FATHER|<MOTHER'}) 
    YIELD nodes, relationships
RETURN extract(x IN relationships | 
        [id(startnode(x)), type(x), x.role, id(endnode(x))]) as relations,
        extract(x in nodes | x) as nodelist"""
        return  shareds.driver.session().run(all_nodes_query_w_apoc, pid=uniq_id)


    def get_citation_id(self):
        """ Luetaan henkilön viittauksen id """

        query = """
            MATCH (person:Person)-[r:CITATION]->(c:Citation)
                WHERE ID(person)={}
                RETURN ID(c) AS citationref_hlink
            """.format(self.uniq_id)
        return  shareds.driver.session().run(query)


    def get_event_data_by_id(self):
        """ Luetaan henkilön tapahtumien id:t 
            Korvaava versio models.gen.event_combo.Event_combo.get_connected_events_w_links
        """

        root = int(self.uniq_id)
        query = """
MATCH (person:Person)-[r:EVENT]->(event:Event)
  WHERE ID(person)=$pid
RETURN r.role AS eventref_role, ID(event) AS eventref_hlink"""
        return  shareds.driver.session().run(query, {"pid": root})


    def get_her_families_by_id(self):
        """ Luetaan naisen perheiden id:t """

        pid = int(self.uniq_id)
        query = """
MATCH (person:Person)<-[r:MOTHER]-(family:Family)
  WHERE ID(person)=$pid
RETURN ID(family) AS uniq_id"""
        return  shareds.driver.session().run(query, {"pid": pid})


    def get_his_families_by_id(self):
        """ Luetaan miehen perheiden id:t """

        pid = int(self.uniq_id)
        query = """
MATCH (person:Person)<-[r:FATHER]-(family:Family)
  WHERE ID(person)=$pid
RETURN ID(family) AS uniq_id"""
        return  shareds.driver.session().run(query, {"pid": pid})


    def get_hlinks_by_id(self):
        """ Luetaan henkilön linkit """

        event_result = self.get_event_data_by_id()
        for event_record in event_result:
            self.eventref_hlink.append(event_record["eventref_hlink"])
            self.eventref_role.append(event_record["eventref_role"])

        media_result = self.get_media_id()
        for media_record in media_result:
            self.objref_hlink.append(media_record["objref_hlink"])

        family_result = self.get_parentin_id()
        for family_record in family_result:
            self.parentin_hlink.append(family_record["parentin_hlink"])

        citation_result = self.get_citation_id()
        for citation_record in citation_result:
            self.citationref_hlink.append(citation_record["citationref_hlink"])

        return True


    def get_media_id(self):
        """ Luetaan henkilön tallenteen id """

        query = """
            MATCH (person:Person)-[r:MEDIA]->(obj:Media)
                WHERE ID(person)={}
                RETURN ID(obj) AS objref_hlink
            """.format(self.uniq_id)
        return  shareds.driver.session().run(query)


    def get_parentin_id(self):
        """ Luetaan henkilön syntymäperheen id """

        query = """
            MATCH (person:Person)<-[r:CHILD]-(family:Family)
                WHERE ID(person)={}
                RETURN ID(family) AS parentin_hlink
            """.format(self.uniq_id)
        return  shareds.driver.session().run(query)


    def get_person_and_name_data_by_id(self):
        """ Luetaan kaikki henkilön tiedot ja nimet
            ╒══════════════════════════════╤══════════════════════════════╕
            │"person"                      │"name"                        │
            ╞══════════════════════════════╪══════════════════════════════╡
            │{"gender":"F","url_type":[],"c│{"firstname":"Margareta Elisab│
            │hange":"1507492602","gramps_ha│et","surname":"Enckell","alt":│
            │ndle":"_d9ea5e7f9a00a0482af","│"","type":"Birth Name","suffix│
            │id":"I0098","url_href":[],"url│":"","refname":"Margareta Elis│
            │_description":[]}             │abeth/Enckell/"}              │
            ├──────────────────────────────┼──────────────────────────────┤
            │{"gender":"F","url_type":[],"c│{"firstname":"Margareta","surn│
            │hange":"1507492602","gramps_ha│ame":"Utter","alt":"1","type":│
            │ndle":"_d9ea5e7f9a00a0482af","│"Married Name","suffix":"","re│
            │id":"I0098","url_href":[],"url│fname":"Margareta/Utter/"}    │
            │_description":[]}             │                              │
            └──────────────────────────────┴──────────────────────────────┘
        """
        pid = int(self.uniq_id)
        query = """
MATCH (person:Person)-[r:NAME]->(name:Name)
  WHERE ID(person)=$pid
RETURN person, name
  ORDER BY name.alt"""
        person_result = shareds.driver.session().run(query, {"pid": pid})
        self.id = None

        for person_record in person_result:
            if self.id == None:
                self.handle = person_record["person"]['handle']
                self.change = int(person_record["person"]['change'])  #TODO only temporary int()
                self.id = person_record["person"]['id']
                self.priv = person_record["person"]['priv']
                self.gender = person_record["person"]['gender']
                self.confidence = person_record["person"]['confidence']
                self.est_birth = person_record["person"]['est_birth']
                self.est_death = person_record["person"]['est_death']

            if len(person_record["name"]) > 0:
                pname = Name()
                pname.alt = person_record["name"]['alt']
                pname.type = person_record["name"]['type']
                pname.firstname = person_record["name"]['firstname']
#                 pname.refname = person_record["name"]['refname']
                pname.surname = person_record["name"]['surname']
                pname.suffix = person_record["name"]['suffix']
                self.names.append(pname)


    def get_person_w_names(self):
        """ Returns Person with Names and Weburls included

            Luetaan kaikki henkilön tiedot ja nimet
            ╒══════════════════════════════╤══════════════════════════════╕
            │"person"                      │"names"                       │
            ╞══════════════════════════════╪══════════════════════════════╡
            │{"gender":"F","url_type":[],"c│[{"firstname":"Margareta Elisa│
            │hange":"1507492602","gramps_ha│bet","surname":"Enckell","alt"│
            │ndle":"_d9ea5e7f9a00a0482af","│:"","type":"Birth Name","suffi│
            │id":"I0098","url_href":[],"url│x":"","refname":"Margareta Eli│
            │_description":[]}             │sabeth/Enckell/"},            │
            │                              │                  {"firstname"│
            │                              │:"Margareta","surname":"Utter"│
            │                              │,"alt":"1","type":"Married Nam│
            │                              │e","suffix":"","refname":"Marg│
            │                              │areta/Utter/"}]               │
            └──────────────────────────────┴──────────────────────────────┘        """
#         query = """
# MATCH (person:Person)-[r:NAME]-(name:Name)
#   WHERE ID(person)=$pid
# RETURN person, name
#   ORDER BY name.alt"""
        query = """
MATCH (person:Person)-[r:NAME]->(name:Name)
  WHERE ID(person)=$pid
OPTIONAL MATCH (person)-[wu:WEBURL]->(weburl:Weburl)
  WITH person, name, COLLECT (weburl) AS urls ORDER BY name.alt
RETURN person, urls, COLLECT (name) AS names
        """
        person_result = shareds.driver.session().run(query, pid=int(self.uniq_id))

        for person_record in person_result:
            self.handle = person_record["person"]['handle']
            self.change = int(person_record["person"]['change'])  #TODO only temporary int()
            self.id = person_record["person"]['id']
            self.priv = person_record["person"]['priv']
            self.gender = person_record["person"]['gender']
            self.confidence = person_record["person"]['confidence']
            self.est_birth = person_record["person"]['est_birth']
            self.est_death = person_record["person"]['est_death']

            for name in person_record["names"]:
                pname = Name()
                pname.alt = name['alt']
                pname.type = name['type']
                pname.firstname = name['firstname']
#                 pname.refname = name['refname']
                pname.surname = name['surname']
                pname.suffix = name['suffix']
                self.names.append(pname)

            for url in person_record["urls"]:
                weburl = Weburl()
                weburl.priv = url['priv']
                weburl.href = url['href']
                weburl.type = url['type']
                weburl.description = url['description']
                self.urls.append(weburl)


    @staticmethod
    def get_people_with_same_birthday():
        """ Etsi kaikki henkilöt, joiden syntymäaika on sama"""

        query = """
            MATCH (p1:Person)-[r1:NAME]->(n1:Name) WHERE p1.est_birth<>''
            MATCH (p2:Person)-[r2:NAME]->(n2:Name) WHERE ID(p1)<ID(p2) AND
                p2.gender = p1.gender AND p2.est_birth = p1.est_birth
                RETURN COLLECT ([ID(p1), p1.est_birth, p1.est_death,
                n1.firstname, n1.suffix, n1.surname,
                ID(p2), p2.est_birth, p2.est_death,
                n2.firstname, n2.suffix, n2.surname]) AS ids
            """.format()
        return shareds.driver.session().run(query)


    @staticmethod
    def get_people_with_same_deathday():
        """ Etsi kaikki henkilöt, joiden kuolinaika on sama"""

        query = """
            MATCH (p1:Person)-[r1:NAME]->(n1:Name) WHERE p1.est_death<>''
            MATCH (p2:Person)-[r2:NAME]->(n2:Name) WHERE ID(p1)<ID(p2) AND
                p2.gender = p1.gender AND p2.est_death = p1.est_death
                RETURN COLLECT ([ID(p1), p1.est_birth, p1.est_death,
                n1.firstname, n1.suffix, n1.surname,
                ID(p2), p2.est_birth, p2.est_death,
                n2.firstname, n2.suffix, n2.surname]) AS ids
            """.format()
        return shareds.driver.session().run(query)


    @staticmethod
    def get_people_wo_birth():
        """ Voidaan lukea henkilöitä ilman syntymätapahtumaa kannasta
        """

        query = """
 MATCH (p:Person) WHERE NOT EXISTS ((p)-[:EVENT]->(:Event {type:'Birth'}))
 WITH p
 MATCH (p)-[:NAME]->(n:Name)
 RETURN ID(p) AS uniq_id, p, n ORDER BY n.surname, n.firstname"""

        result = shareds.driver.session().run(query)

        titles = ['uniq_id', 'handle', 'change', 'id', 'priv', 'gender',
                  'firstname', 'surname']
        lists = []

        for record in result:
            data_line = []
            if record['uniq_id']:
                data_line.append(record['uniq_id'])
            else:
                data_line.append('-')
            if record["p"]['handle']:
                data_line.append(record["p"]['handle'])
            else:
                data_line.append('-')
            if record["p"]['change']:
                data_line.append(int(record["p"]['change']))  #TODO only temporary int()
            else:
                data_line.append('-')
            if record["p"]['id']:
                data_line.append(record["p"]['id'])
            else:
                data_line.append('-')
            if record["p"]['priv']:
                data_line.append(record["p"]['priv'])
            else:
                data_line.append('-')
            if record["p"]['gender']:
                data_line.append(record["p"]['gender'])
            else:
                data_line.append('-')
            if record["n"]['firstname']:
                data_line.append(record["n"]['firstname'])
            else:
                data_line.append('-')
            if record["n"]['surname']:
                data_line.append(record["n"]['surname'])
            else:
                data_line.append('-')

            lists.append(data_line)

        return (titles, lists)


    @staticmethod
    def get_old_people_top():
        """ Voidaan lukea henkilöitä joilla syntymä- ja kuolintapahtumaa kannasta
        """

        persons_get_oldest = """
 MATCH (p:Person)-[:EVENT]->(a:Event) 
     WHERE EXISTS ((p)-[:EVENT]->(a:Event {type:'Birth'}))
 WITH p, a 
 MATCH (p)-[:EVENT]->(b:Event) 
     WHERE EXISTS ((p)-[:EVENT]->(b:Event {type:'Death'}))
 WITH p, a, b
 MATCH (p)-[:NAME]->(n:Name)
 RETURN ID(p) AS uniq_id, p, n, 
     [a.datetype, a.date1, a.date2] AS birth, 
     [b.datetype, b.date1, b.date2] AS death 
 ORDER BY n.surname, n.firstname"""
                
        result = shareds.driver.session().run(persons_get_oldest)

        titles = ['uniq_id', 'firstname', 'surname', 'birth', 'death',
                  'age (years)', 'age (months)', 'age(12*years + months)']
        lists = []

        for record in result:
            data_line = []
            if record['uniq_id']:
                data_line.append(record['uniq_id'])
            else:
                data_line.append('-')
            if record["n"]['firstname']:
                data_line.append(record["n"]['firstname'])
            else:
                data_line.append('-')
            if record["n"]['surname']:
                data_line.append(record["n"]['surname'])
            else:
                data_line.append('-')
            if record['birth'][0] != None:
                birth = DateRange(record['birth'])
                birth_str = birth.estimate()
                birth_data = birth_str.split("-")
                data_line.append(str(birth))
            else:
                data_line.append('-')
            if record['death'][0] != None:
                death = DateRange(record['death'])
                death_str = death.estimate()
                death_data = death_str.split("-")
                data_line.append(str(death))
#                 death_str = record['death']
#                 death_data = death_str.split("-")
#                 data_line.append(record['death'])
            else:
                data_line.append('-')

            # Counting the age when the dates are as YYYY-mm-dd
            if birth_data[0] != None and death_data[0] != None:
                years = int(death_data[0])-int(birth_data[0])
                months = int(death_data[1])-int(birth_data[1])

                if int(death_data[2]) < int(death_data[2]):
                    months -= 1

                if months < 0:
                    months += 12
                    years -= 1

                years_months = years * 12 + months
            else:
                years = '-'
                months = '-'
                years_months = 0

            data_line.append(years)
            data_line.append(months)
            data_line.append(years_months)


            lists.append(data_line)

        return (titles, lists)


    @staticmethod
    def get_confidence (uniq_id=None):
        """ Voidaan lukea henkilön tapahtumien luotettavuustiedot kannasta
        """
        if uniq_id:
            return shareds.driver.session().run(Cypher_person.get_confidence,
                                                id=uniq_id)
        else:
            return shareds.driver.session().run(Cypher_person.get_confidences_all)


    def set_confidence (self, tx):
        """ Sets a quality rate to this Person
            Voidaan asettaa henkilön tietojen luotettavuusarvio kantaan
        """
        return tx.run(Cypher_person.set_confidence,
                      id=self.uniq_id, confidence=self.confidence)


    @staticmethod
    def get_person_events (nmax=0, pid=None, names=None):
        """ Voidaan lukea henkilöitä tapahtumineen kannasta seuraavasti:
            get_persons()               kaikki
            get_persons(pid=123)        tietty henkilö oid:n mukaan poimittuna
            get_persons(names='And')    henkilöt, joiden sukunimen alku täsmää
            - lisäksi (nmax=100)         rajaa luettavien henkilöiden määrää

        Palauttaa riveillä listan muuttujia:
        n.oid, n.firstname, n.lastname, n.occu, n.place, type(r), events
          0      1            2           3       4      5        6
         146    Bengt       Bengtsson   soldat   null    OSALLISTUI [[...]]

        jossa 'events' on lista käräjiä, jonka jäseninä on lista ko
        käräjäin muuttujia:
        [[e.oid, e.kind,  e.name,  e.date,          e.name_orig]...]
            0      1        2        3                4
        [[ 147,  Käräjät, Sakkola, 1669-03-22 … 23, Sakkola 1669.03.22-23]]

        │ Person                       │   │ Name                         │
        ├──────────────────────────────┼───┼──────────────────────────────┤
        │{"gender":"","handle":"       │{} │{"surname":"Andersen","alt":""│
        │handle_6","change":0,"id":"6"}│   │,"type":"","suffix":"","firstn│
        │                              │   │ame":"Alexander","refname":""}│
        ├──────────────────────────────┼───┼──────────────────────────────┤
        """

        #TODO nmax now not available
        if nmax > 0:
            qmax = "LIMIT " + str(nmax)
        else:
            qmax = ""
        if pid:
            where = "WHERE n.oid={} ".format(pid)
        elif names:
            where = "WHERE n.lastname STARTS WITH '{}' ".format(names)
        else:
            where = ""
#         query = """
#  MATCH (n:Person) {0}
#  OPTIONAL MATCH (n)-[r]->(e)
#  RETURN n.oid, n.firstname, n.lastname, n.occu, n.place, type(r),
#   COLLECT([e.oid, e.kind, e.name, e.date, e.name_orig]) AS events
#  ORDER BY n.lastname, n.firstname {1}""".format(where, qmax)

        query = """
MATCH (n:Person) -[:NAME]->( k:Name) {0}
    OPTIONAL MATCH (n) -[r:EVENT]-> (e)
RETURN n.id, k.firstname, k.surname,
       COLLECT([e.name, e.kind]) AS events
    ORDER BY k.surname, k.firstname {1}""".format(where, qmax)

        return shareds.driver.session().run(query)


    @staticmethod
    def get_person_combos (keys, currentuser, take_refnames=False, order=0):
        """ Read Persons with Names, Events, Refnames (reference names) and Places
            called from models.datareader.read_persons_with_events
            
            UUSI KORVAAMAAN get_events_k:n

             a) selected by unique id
                keys=['uniq_id', uid]    by person's uniq_id (for table_person_by_id.html)
             b) selected by name
                keys=['all']             all
                keys=['surname', name]   by start of surname
                keys=['firstname', name] by start of the first of first names
                keys=['patronyme', name] by start of patronyme name
                keys=['refname', name]   by exact refname
            If currentuser is defined, select only her Events

            #TODO: take_refnames should determine, if refnames are returned, too
            #TODO: filter by owner
        """
        if keys:
            rule=keys[0]
            key=keys[1].title() if len(keys) > 1 else None
            print("Selected {} '{}'".format(rule, key))
        else:
            rule="all"
            key=""
# ╒════════════════════╤════════════════════╤════════════════════╤════════════════════╤═════════╕
# │"person"            │"name"              │"refnames"          │"events"            │"initial"│
# ╞════════════════════╪════════════════════╪════════════════════╪════════════════════╪═════════╡
# │{"handle":"_da692a09│{"alt":"","firstname│["Helena","Brita","K│[["Primary",{"datety│"K"      │
# │bac110d27fa326f0a7",│":"Brita Helena","ty│lick"]              │pe":0,"change":15009│         │
# │"id":"I0119","priv":│pe":"Birth Name","su│                    │07890,"description":│         │
# │"","gender":"F","con│ffix":"","surname":"│                    │"","handle":"_da692d│         │
# │fidence":"2.5","chan│Klick"}             │                    │0fb975c8e8ae9c4986d2│         │
# │ge":1507492602}     │                    │                    │3","attr_type":"","i│         │
# │                    │                    │                    │d":"E0161","date2":1│         │
# │                    │                    │                    │754183,"type":"Birth│         │
# │                    │                    │                    │","date1":1754183,"a│         │
# │                    │                    │                    │ttr_value":""},null]│         │
# │                    │                    │                    │,...]               │         │
# └────────────────────┴────────────────────┴────────────────────┴────────────────────┴─────────┘

        try:
            with shareds.driver.session() as session:
                if rule == 'uniq_id':
                    return session.run(Cypher_person.get_events_uniq_id, id=int(key))
                elif rule == 'refname':
                    return session.run(Cypher_person.get_events_by_refname, name=key)
                elif rule == 'all':
                    if order == 1:      # order by first name
                        return session.run(Cypher_person.get_events_all_firstname)
                    elif order == 2:    # order by patroname
                        return session.run(Cypher_person.get_events_all_patronyme)
                    else:
                        return session.run(Cypher_person.get_events_all)
                else:
                    # Selected names and name types (untested?)
                    return session.run(Cypher_person.get_events_by_refname_use,
                                       attr={'use':rule, 'name':key})
        except Exception as err:
            print("Virhe-get_person_combos: {1} {0}".format(err, keys), file=stderr)


    @staticmethod
    def get_events_k (keys, currentuser, take_refnames=False, order=0):
        """ OBSOLETE - tilalle tulee Person_combo.get_person_combos

            Read Persons with Names, Events and Refnames (reference names)
            called from models.datareader.read_persons_with_events

             a) selected by unique id
                keys=['uniq_id', uid]    by person's uniq_id (for table_person_by_id.html)
             b) selected by name
                keys=['all']             all
                keys=['surname', name]   by start of surname
                keys=['firstname', name] by start of the first of first names
                keys=['patronyme', name] by start of patronyme name
                keys=['refname', name]   by exact refname
            If currentuser is defined, select only her Events

            #TODO: take_refnames should determine, if refnames are returned, too
        """
        if keys:
            rule=keys[0]
            key=keys[1].title() if len(keys) > 1 else None
            print("Selected {} '{}'".format(rule, key))
        else:
            rule="all"
            key=""

# ╒═════╤════════════════╤═══════════╤════════╤═════════════════╤═════════════════╕
# │"id" │"firstname"     │"surname"  │"suffix"│"refnames"       │"events"         │
# ╞═════╪════════════════╪═══════════╪════════╪═════════════════╪═════════════════╡
# │31844│"August Wilhelm"│"Wallenius"│""      │["August","Wilhel│[[29933,"Baptism"│
# │     │                │           │        │m","Wallenius"]  │, ...            │
# └─────┴────────────────┴───────────┴────────┴─────────────────┴─────────────────┘
# There is also fields confidence, est_birth, est_death, which are empty for now

#TODO: filter by owner

        try:
            with shareds.driver.session() as session:
                if rule == 'uniq_id':
                    return session.run(Cypher_person.get_events_uniq_id, id=int(key))
                elif rule == 'refname':
                    return session.run(Cypher_person.get_events_by_refname, name=key)
                elif rule == 'all':
                    if order == 1:      # order by first name
                        return session.run(Cypher_person.get_events_all_firstname)
                    elif order == 2:    # order by patroname
                        return session.run(Cypher_person.get_events_all_patronyme)
                    else:
                        return session.run(Cypher_person.get_events_all)
                else:
                    # Selected names and name types (untested?)
                    return session.run(Cypher_person.get_events_by_refname_use,
                                       attr={'use':rule, 'name':key})
        except Exception as err:
            print("Virhe-get_events_k: {1} {0}".format(err, keys), file=stderr)


    def set_my_places(self, cleartext_list=False):
        ''' Finds all Places with their Place_names
            which are connected to any personal Events
            and stores them in self.places list
        '''

        get_places_w_names = """
match (p:Person) -[r:EVENT]-> (e:Event) -[:PLACE]-> (pl:Place)
    where id(p)=$pid
with r, e, pl
    optional match (pl) -[:NAME]-> (pname:Place_name)
    return r.role as r_role, id(e) as e_id, 
        pl as place, collect(pname) as pnames"""
    
# ╒═════════╤══════╤════════════════════════════════╤════════════════════════════════╕
# │"r_role" │"e_id"│"place"                         │"pnames"                        │
# ╞═════════╪══════╪════════════════════════════════╪════════════════════════════════╡
# │"Primary"│72501 │{"coord":[60.5,27.2],"handle":"_│[{"name":"Hamina","lang":""}]   │
# │         │      │de189e6c36c3f1e676c22ed6559","id│                                │
# │         │      │":"P0004","type":"Town","pname":│                                │
# │         │      │"Hamina","change":1536051348}   │                                │
# ├─────────┼──────┼────────────────────────────────┼────────────────────────────────┤
# │"Primary"│72500 │{"handle":"_ddd39c4088f165882c16│[{"name":"Kaivopuisto","lang":""│
# │         │      │0493e88","id":"P0001","type":"Bo│},{"name":"Brunspark","lang":"sv│
# │         │      │rough","pname":"Kaivopuisto","ch│"}]                             │
# │         │      │ange":1536051387}               │                                │
# └─────────┴──────┴────────────────────────────────┴────────────────────────────────┘

        result = shareds.driver.session().run(get_places_w_names, pid=self.uniq_id)
        for record in result:
            ''' <Record r_role='Primary' e_id=72501 pl_id=72486 
                    place=<Node id=72486 labels={'Place'} 
                        properties={'handle': '_de189e6c36c3f1e676c22ed6559', 
                        'change': 1536051348, 'id': 'P0004', 'type': 'Town', 
                        'pname': 'Hamina', 'coord': [60.5, 27.2]}> 
                    pnames=[<Node id=72487 labels={'Place_name'} 
                        properties={'lang': '', 'name': 'Hamina'}>]>
            '''
            # Fill Place properties:
            #     handle
            #     change
            #     id                  esim. "P0001"
            #     type                str paikan tyyppi
            #     pname               str paikan nimi
            #     names[]:
            #        name             str paikan nimi
            #        lang             str kielikoodi
            #        dates            DateRange date expression

            e_id = record['e_id']
            
            for my_e in self.events:
                if e_id == my_e.uniq_id:
                    # Found current event, create a Place there
                    placerec = record['place']
                    print("event {}: {} <- place {}: {}".\
                          format(my_e.uniq_id, my_e, placerec.id, placerec['pname']))
                    # Get Place data
                    pl = Place()
                    pl.uniq_id = placerec.id
                    pl.type = placerec['type']
                    pl.pname = placerec['pname']
                    pl.id = placerec['id']
                    pl.handle = placerec['handle']
                    pl.change = placerec['change']
                    # Get the Place_names
                    for node in record['pnames']:
                        pn = Place_name.from_node(node)
                        pl.names.append(pn)

                    if cleartext_list:
                        my_e.clearnames = my_e.clearnames + pl.show_names_list()
                    my_e.place = pl

#         for e in self.events:
#             print("event {}: {}".format(e.uniq_id, e))
#             if e.place == None:
#                 print("- no place")
#             else:
#                 for n in e.place.names:
#                     print("- place {} name {}: {}".format(e.place.uniq_id, n.uniq_id, n))


    def get_all_notes(self):
        ''' Finds all Note and Weburl
            which are connected to Person, Events or Families
            and stores them in self.notes and self.Weburl lists
        '''
        pass


    @staticmethod
    def get_family_members (uniq_id):
        """ Read the Names, Families and Events connected to this Person.
            for '/scene/person=<string:uniq_id>'
        """
        query="""
MATCH (p:Person) <-- (f:Family) -[r1]-> (m:Person) -[:NAME]-> (n:Name) 
    WHERE ID(p) = $id
OPTIONAL MATCH (m) -[:EVENT]-> (birth {type:'Birth'})
    WITH f.id AS family_id, ID(f) AS f_uniq_id, 
         TYPE(r1) AS role,
         m.id AS m_id, ID(m) AS uniq_id, m.gender AS gender, 
         n.alt AS alt, n.type AS ntype, n.firstname AS fn, n.surname AS sn, n.suffix AS sx,
         birth.date AS birth_date
    ORDER BY n.alt
    RETURN family_id, f_uniq_id, role, 
           m_id, uniq_id, gender, birth_date,
           COLLECT([alt, ntype, fn, sn, sx]) AS names
    ORDER BY family_id, role, birth_date
UNION
MATCH (p:Person) <-[r2]- (f:Family) 
    WHERE id(p) = $id
    RETURN f.id AS family_id, ID(f) AS f_uniq_id, TYPE(r2) AS role, 
           p.id AS m_id, ID(p) AS uniq_id, p.gender AS gender, "" AS birth_date,
           [] AS names"""

# ╒═══════════╤═══════════╤════════╤═══════╤═════════╤════════╤════════════╤══════════════════════════════╕
# │"family_id"│"f_uniq_id"│"role"  │"m_id" │"uniq_id"│"gender"│"birth_date"│"names"                       │
# ╞═══════════╪═══════════╪════════╪═══════╪═════════╪════════╪════════════╪══════════════════════════════╡
# │"F0012"    │"40506"    │"CHILD" │"27044"│"27044"  │"M"     │"1869-03-28"│[["","Birth Name","Christian",│
# │           │           │        │       │         │        │            │"Sibelius",""],["1","Also Know│
# │           │           │        │       │         │        │            │n As","Kristian","Sibelius",""│
# │           │           │        │       │         │        │            │]]                            │
# ├───────────┼───────────┼────────┼───────┼─────────┼────────┼────────────┼──────────────────────────────┤

        return shareds.driver.session().run(query, id=int(uniq_id))


    @staticmethod
    def get_refnames(pid):
        """ List Person's all Refnames with name use"""
        # ╒══════════════════════════╤═════════════════════╕
        # │"a"                       │"li"                 │
        # ╞══════════════════════════╪═════════════════════╡
        # │{"name":"Alfonsus","source│[{"use":"firstname"}]│
        # │":"Messu- ja kalenteri"}  │                     │
        # ├──────────────────────────┼─────────────────────┤
        # │{"name":"Bert-not-exists"}│[{"use":"firstname"}]│
        # └──────────────────────────┴─────────────────────┘
        query = """
MATCH (p:Person) WHERE ID(p) = $pid
MATCH path = (a) -[:BASENAME*]-> (p)
RETURN a, [x IN RELATIONSHIPS(path)] AS li
"""
        return shareds.driver.session().run(query, pid=pid)


    @staticmethod
    def get_ref_weburls(pid_list):
        """ Get all weburls referenced from list of uniq_ids
            #TODO Mitä tietoja halutaan?
        """
#       Example
#                 match (x) 
#                 where id(x) in [72529, 72515, 72528]
#                 with distinct x
#                   match (x) -[r:CITATION|SOURCE|NOTE|WEBURL]-> (y) 
#                   return x.id, type(r), id(y), labels(y)[0] as label, 
#                          y.id as id order by id, x.id

        query="""match (x) where id(x) in $pids
with distinct x
  match (x) -[r:CITATION|SOURCE|NOTE|WEBURL]-> (y) 
  return id(x) as root, x.id as root_id, type(r) as rtype, 
         id(y) as target, labels(y)[0] as label, y.id as id 
  order by root, id"""

        return shareds.driver.session().run(query, pids=pid_list)

# Unused methods:
#     def key(self):
#         "Hakuavain tuplahenkilöiden löytämiseksi sisäänluvussa"
#         key = "{}:{}:{}:{}".format(self.name.firstname, self.name.last,
#               self.occupation, self.place)
#         return key
#
#     def join_events(self, events, kind=None):
#         """
#         Päähenkilöön self yhdistetään tapahtumat listalta events.
#         Yhteyden tyyppi on kind, esim. "OSALLISTUI"
#         """
#         print("**** person.join_events() on toteuttamatta!")
#         eventList = ""
#Todo: TÄMÄ ON RISA, i:hin EI LAINKAAN VIITATTU
#         for i in events:
#             # Luodaan yhteys (Person)-[:kind]->(Event)
#             for event in self.events:
#                 if event.__class__ != "Event":
#                     raise TypeError("Piti olla Event: {}".format(event.__class__))
#
#                 # Tapahtuma-noodi
#                 tapahtuma = Node(Event.label, oid=event.oid, kind=event.kind, \
#                         name=event.name, date=event.date)
#                 osallistui = Relationship(persoona, kind, tapahtuma)
#             try:
#                 graph.create(osallistui)
#             except Exception as e:
#                 flash('Lisääminen ei onnistunut: {}. henkilö {}, tapahtuma {}'.\
#                     format(e, persoona, tapahtuma), 'error')
#                 logging.warning('Lisääminen ei onnistunut: {}'.format(e))
#         logging.debug("Yhdistetään henkilöön {} henkilöt {}".format(str(self), eventList))
#
#     def join_persons(self, others):
#         """
#         Päähenkilöön self yhdistetään henkilöiden others tiedot ja tapahtumat
#         """
#         #TODO Kahden henkilön ja heidän tapahtumiensa yhdistäminen
#         othersList = ""
#         for i in others:
#             othersList.append(str(i) + " ")
#         logging.debug("Yhdistetään henkilöön {} henkilöt {}".format(str(self), othersList))
#         pass
#

    def get_points_for_compared_data(self, comp_person, print_out=True):
        """ Tulostaa kahden henkilön tiedot vieretysten """
        points = 0
        print ("*****Person*****")
        if (print_out):
            print ("Handle: " + self.handle + " # " + comp_person.handle)
            print ("Change: {} # {}".format(self.change, comp_person.change))
            print ("Unique id: " + str(self.uniq_id) + " # " + str(comp_person.uniq_id))
            print ("Id: " + self.id + " # " + comp_person.id)
            print ("Priv: " + self.priv + " # " + comp_person.priv)
            print ("Gender: " + self.gender + " # " + comp_person.gender)
        if len(self.names) > 0:
            alt1 = []
            type1 = []
            first1 = []
            refname1 = []
            surname1 = []
            suffix1 = []
            alt2 = []
            type2 = []
            first2 = []
            refname2 = []
            surname2 = []
            suffix2 = []

            names = self.names
            for pname in names:
                alt1.append(pname.alt)
                type1.append(pname.type)
                first1.append(pname.firstname)
#                 refname1.append(pname.refname)
                surname1.append(pname.surname)
                suffix1.append(pname.suffix)

            names2 = comp_person.names
            for pname in names2:
                alt2.append(pname.alt)
                type2.append(pname.type)
                first2.append(pname.firstname)
#                 refname2.append(pname.refname)
                surname2.append(pname.surname)
                suffix2.append(pname.suffix)

            if (len(first2) >= len(first1)):
                for i in range(len(first1)):
                    # Give points if refnames match
                    if refname1[i] != ' ':
                        if refname1[i] == refname2[i]:
                            points += 1
                    if (print_out):
                        print ("Alt: " + alt1[i] + " # " + alt2[i])
                        print ("Type: " + type1[i] + " # " + type2[i])
                        print ("First: " + first1[i] + " # " + first2[i])
                        print ("Refname: " + refname1[i] + " # " + refname2[i])
                        print ("Surname: " + surname1[i] + " # " + surname2[i])
                        print ("Suffix: " + suffix1[i] + " # " + suffix2[i])
            else:
                for i in range(len(first2)):
                    # Give points if refnames match
                    if refname1[i] == refname2[i]:
                        points += 1
                    if (print_out):
                        print ("Alt: " + alt1[i] + " # " + alt2[i])
                        print ("Type: " + type1[i] + " # " + type2[i])
                        print ("First: " + first1[i] + " # " + first2[i])
                        print ("Refname: " + refname1[i] + " # " + refname2[i])
                        print ("Surname: " + surname1[i] + " # " + surname2[i])
                        print ("Suffix: " + suffix1[i] + " # " + suffix2[i])

        return points


    @staticmethod
    def set_estimated_dates():
        # Set est_birth
        try:
            dtype = 'Birth'
            query = """
MATCH (n:Person)-[r:EVENT]->(m:Event)
    WHERE m.type=$type
SET r.type =$type
SET n.est_birth = m.daterange_start"""
            result = shareds.driver.session().run(query,
               {"type": dtype})
            counters = result.consume().counters
            msg = "Muutettu {} est_birth-tietoa".format(counters.properties_set)
        except Exception as err:
            print("Virhe (Person.save:est_birth): {0}".format(err), file=stderr)

        # Set est_birth
        try:
            dtype = 'Death'
            query = """
MATCH (n:Person)-[r:EVENT]->(m:Event)
    WHERE m.type=$type
SET r.type =$type
SET n.est_death = m.daterange_start"""
            result = shareds.driver.session().run(query,
               {"type": dtype})
            counters = result.consume().counters
            msg = msg + " ja {} est_death-tietoa.".format(counters.properties_set)
            return msg
        except Exception as err:
            print("Virhe (Person.save:est_death): {0}".format(err), file=stderr)


    def print_data(self):
        """ Tulostaa tiedot """
        print ("*****Person*****")
        print ("Handle: " + self.handle)
        print ("Change: {}".format(self.change))
        print ("Id: " + self.id)
        print ("Priv: " + self.priv)
        print ("Gender: " + self.gender)

        if len(self.names) > 0:
            for pname in self.names:
                print ("Alt: " + pname.alt)
                print ("Type: " + pname.type)
                print ("First: " + pname.firstname)
#                 print ("Refname: " + pname.refname)
                print ("Surname: " + pname.surname)
                print ("Suffix: " + pname.suffix)

        if len(self.urls) > 0:
            for url in self.urls:
                print ("Url priv: " + url.priv)
                print ("Url href: " + url.href)
                print ("Url type: " + url.type)
                print ("Url description: " + url.description)

        if len(self.eventref_hlink) > 0:
            for i in range(len(self.eventref_hlink)):
                print ("Eventref_hlink: " + self.eventref_hlink[i])
                print ("Eventref_role: " + self.eventref_role[i])
        if len(self.parentin_hlink) > 0:
            for i in range(len(self.parentin_hlink)):
                print ("Parentin_hlink: " + self.parentin_hlink[i])
        if len(self.noteref_hlink) > 0:
            for i in range(len(self.noteref_hlink)):
                print ("Noteref_hlink: " + self.noteref_hlink[i])
        if len(self.citationref_hlink) > 0:
            for i in range(len(self.citationref_hlink)):
                print ("Citationref_hlink: " + self.citationref_hlink[i])
        return True


    def print_compared_data(self, comp_person, print_out=True):
        """ Tulostaa kahden henkilön tiedot vieretysten """
        points = 0
        print ("*****Person*****")
        if (print_out):
            print ("Handle: " + self.handle + " # " + comp_person.handle)
            print ("Change: {} # {}".format(self.change, comp_person.change))
            print ("Id: " + self.id + " # " + comp_person.id)
            print ("Priv: " + self.priv + " # " + comp_person.priv)
            print ("Gender: " + self.gender + " # " + comp_person.gender)
        if len(self.names) > 0:
            alt1 = []
            type1 = []
            first1 = []
            refname1 = []
            surname1 = []
            suffix1 = []
            alt2 = []
            type2 = []
            first2 = []
            refname2 = []
            surname2 = []
            suffix2 = []

            names = self.names
            for pname in names:
                alt1.append(pname.alt)
                type1.append(pname.type)
                first1.append(pname.firstname)
#                 refname1.append(pname.refname)
                surname1.append(pname.surname)
                suffix1.append(pname.suffix)

            names2 = comp_person.names
            for pname in names2:
                alt2.append(pname.alt)
                type2.append(pname.type)
                first2.append(pname.firstname)
#                 refname2.append(pname.refname)
                surname2.append(pname.surname)
                suffix2.append(pname.suffix)

            if (len(first2) >= len(first1)):
                for i in range(len(first1)):
                    # Give points if refnames match
                    if refname1[i] != ' ':
                        if refname1[i] == refname2[i]:
                            points += 1
                    if (print_out):
                        print ("Alt: " + alt1[i] + " # " + alt2[i])
                        print ("Type: " + type1[i] + " # " + type2[i])
                        print ("First: " + first1[i] + " # " + first2[i])
#                         print ("Refname: " + refname1[i] + " # " + refname2[i])
                        print ("Surname: " + surname1[i] + " # " + surname2[i])
                        print ("Suffix: " + suffix1[i] + " # " + suffix2[i])
            else:
                for i in range(len(first2)):
                    # Give points if refnames match
                    if refname1[i] == refname2[i]:
                        points += 1
                    if (print_out):
                        print ("Alt: " + alt1[i] + " # " + alt2[i])
                        print ("Type: " + type1[i] + " # " + type2[i])
                        print ("First: " + first1[i] + " # " + first2[i])
                        print ("Refname: " + refname1[i] + " # " + refname2[i])
                        print ("Surname: " + surname1[i] + " # " + surname2[i])
                        print ("Suffix: " + suffix1[i] + " # " + suffix2[i])

        return points


    def save(self, username, tx):
        """ Saves the Person object and possibly the Names, Events ja Citations

            On return, the self.uniq_id is set
        """

        today = str(datetime.date.today())
        if not self.handle:
            handles = models.dbutil.get_new_handles(3)
            self.handle = handles.pop()

        # Save the Person node under UserProfile; all attributes are replaced
        try:
            p_attr = {
                "handle": self.handle,
                "change": self.change,
                "id": self.id,
                "priv": self.priv,
                "gender": self.gender
            }
            result = tx.run(Cypher_person_w_handle.create, 
                            username=username, p_attr=p_attr, date=today)
#             self.uniq_id = result.single()[0]
            for res in result:
                self.uniq_id = res[0]
                print("Person {} ".format(self.uniq_id))

        except Exception as err:
            print("Virhe (Person.save:Person): {0}".format(err), file=stderr)

        # Save Name nodes under the Person node
        try:
            for name in self.names:
                n_attr = {
                    "alt": name.alt,
                    "type": name.type,
                    "firstname": name.firstname,
#                     "refname": name.refname,
                    "surname": name.surname,
                    "suffix": name.suffix
                }
                tx.run(Cypher_person_w_handle.link_name, 
                       n_attr=n_attr, p_handle=self.handle)
        except Exception as err:
            print("Virhe (Person.save:Name): {0}".format(err), file=stderr)

        # Save Weburl nodes under the Person
        for url in self.urls:
            u_attr = {
                "priv": url.priv,
                "href": url.href,
                "type": url.type,
                "description": url.description
            }
            try:
                tx.run(Cypher_person_w_handle.link_weburl, 
                       p_handle=self.handle, u_attr=u_attr)
            except Exception as err:
                print("Virhe (Person.save: {} create Weburl): {0}".\
                      format(self.id, err), file=stderr)

        if len(self.events) > 0:
            # Make Event relations (if Events were stored in self.events)
            # TODO: onkohan tämä käytössä?
            ''' Create and connect to an Person.event[*] '''
            for e in self.events:
                if handles:
                    e.handle = handles.pop()
                e_attr = {
                    "handle": e.handle,
                    "id": e.id,
                    "name": e.name, # "e_type": e.tyyppi,
                    "date": e.date,
                    "descr": e.description
                }
                try:
                    tx.run(Cypher_person_w_handle.link_event_embedded, 
                           p_handle=self.handle, e_attr=e_attr, role="osallistuja")
                except Exception as err:
                    print("Virhe (Person.save:create Event): {0}".format(err), file=stderr)

        # Make Event relations by hlinks (from gramps_loader)
        elif len(self.eventref_hlink) > 0:
            ''' Connect to each Event loaded form Gramps '''
            for i in range(len(self.eventref_hlink)):
                try:
                    tx.run(Cypher_person_w_handle.link_event, 
                           p_handle=self.handle, 
                           e_handle=self.eventref_hlink[i], 
                           role=self.eventref_role[i])
                except Exception as err:
                    print("Virhe (Person.save:Event): {0}".format(err), file=stderr)

        # Make relations to the Media node
        if len(self.objref_hlink) > 0:
            for i in range(len(self.objref_hlink)):
                try:
                    tx.run(Cypher_person_w_handle.link_media, 
                           p_handle=self.handle, m_handle=self.objref_hlink[i])
                except Exception as err:
                    print("Virhe (Person.save:Media): {0}".format(err), file=stderr)

        # The relations to the Family node will be created in Family.save(),
        # because the Family object is not yet created

        # Make relations to the Note node
        if len(self.noteref_hlink) > 0:
            for i in range(len(self.noteref_hlink)):
                try:
                    tx.run(Cypher_person_w_handle.link_note,
                           p_handle=self.handle, n_handle=self.noteref_hlink[i])
                except Exception as err:
                    print("Virhe (Person.save:Note): {0}".format(err), file=stderr)

        # Make relations to the Citation node
        if len(self.citationref_hlink) > 0:
            try:
                tx.run(Cypher_person_w_handle.link_citation,
                       p_handle=self.handle, c_handle=self.citationref_hlink[0])
            except Exception as err:
                print("Virhe (Person.save:Citation): {0}".format(err), file=stderr)
        return


class Person_as_member(Person):
    """ A person as a family member

        Extra properties:
            role         str "CHILD", "FATHER" or "MOTHER"
            birth_date   str (TODO: Should be DateRange)
     """

    def __init__(self):
        """ Luo uuden instanssin """
        Person.__init__(self)
        self.role = ''
        self.birth_date = ''
