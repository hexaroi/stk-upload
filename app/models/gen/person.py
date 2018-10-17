'''
    Person and Name classes

    Person hierarkiasuunnitelma 10.9.2018/JMä

    class gen.person.Person(): 
        Person-noden parametrit 
         - uniq_id
         - properties { handle:"_dd2c613026e7528c1a21f78da8a",
                        id:"I0000",
                        priv:"",
                        gender:"M",
                        confidence:"2.0",
                        change:1536324580}
        - __init__()
        
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
        - get_places(self)              Tallettaa liittyvät Paikat henkilöön
        - get_all_citation_source(self) Tallettaa liittyvät Cition ja Source
        - get_all_notes(self)           Tallettaa liittyvät Note ja Weburl
        - get_family_members (uniq_id)  Luetaan liittyvät Names, Families and Events
        - get_refnames(pid)             Luetaan liittyvät Refnames
        - get_ref_weburls(pid_list)     Luetaan mainittuihin nodeihin liittyvät Weburlit
        - set_estimated_dates()         Aseta est_birth ja est_death
        - save(self, username, tx)      Tallettaa Person, Names, Events ja Citations

    Not in use or obsolete:
    - from models.datareader.get_person_data_by_id 
      (returns list: person, events, photos, sources, families)
        - get_hlinks_by_id(self)        Luetaan henkilön linkit (_hlink)
        - get_event_data_by_id(self)    Luetaan henkilön tapahtumien id:t
        - get_media_id(self)            Luetaan henkilön tallenteen id
    - from models.datareader.get_families_data_by_id and Person_combo.get_hlinks_by_id
        - get_her_families_by_id(self)  Luetaan naisen perheiden id:t
        - get_his_families_by_id(self)  Luetaan miehen perheiden id:t
        - get_parentin_id(self)         Luetaan henkilön syntymäperheen id
    - from Person_combo.get_hlinks_by_id
        - get_citation_id(self)         Luetaan henkilöön liittyvän viittauksen id

    - table-näyttöjä varten
        - get_person_and_name_data_by_id(self)
                                        Luetaan kaikki henkilön tiedot ja nimet
        - get_points_for_compared_data(self, comp_person, print_out=True)
                                        Tulostaa kahden henkilön tiedot vieretysten
        - print_compared_data(self, comp_person, print_out=True) 
                                        Tulostaa kahden henkilön tiedot vieretysten


Created on 2.5.2017 from Ged-prepare/Bus/classes/genealogy.py

@author: Jorma Haapasalo <jorma.haapasalo@pp.inet.fi>
'''

import shareds
from .cypher import Cypher_person


class Person:
    """ Henkilö

         - uniq_id                int database key
         - Node properties: {
            handle                str "_dd2c613026e7528c1a21f78da8a"
            id                    str "I0000"
            priv                  int 1 = merkitty yksityiseksi
            gender                str "M", "N", "" sukupuoli
            confidence            float "2.0" tietojen luotettavuus
            change                int 1536324580
           }
     """

    def __init__(self):
        """ Luo uuden person-instanssin """
        self.handle = ''
        self.change = 0
        self.uniq_id = None
        self.id = ''
        self.priv = 0
        self.gender = ''
        self.confidence = ''
#         # Todo: Poista: Nämä vain Person_combossa
#         self.events = []                # For creating display sets
#         self.eventref_hlink = []        # Gramps event handles
#         self.eventref_role = []
#         self.objref_hlink = []
#         self.urls = []
#         self.parentin_hlink = []
#         self.noteref_hlink = []
#         self.citationref_hlink = []
#         self.est_birth = ''
#         self.est_death = ''

    def __str__(self):
        # Person_combo 79584 I1234
        if self.gender == 'M':  sex = 'male'
        elif self.gender == 'F':  sex = 'female'
        else: sex = 'unknown'
        return "{} {}".format(sex, self.id)

    @classmethod
    def from_node(cls, node, obj=None):
        '''
        Transforms a db node to an object of type Person.
        
        Youc can create a Person or Person_node instance. (cls is the class 
        where we are, either Person or Person_combo)
        
        <Node id=80307 labels={'Person'} 
            properties={'id': 'I0119', 'confidence': '2.5', 'gender': 'F', 'change': 1507492602, 
            'handle': '_da692a09bac110d27fa326f0a7', 'priv': ''}>
        '''
        if not obj:
            obj = cls()
        obj.uniq_id = node.id
        obj.id = node['id']
        obj.gender = node['gender']
        obj.handle = node['handle']
        obj.change = node['change']
        obj.confidence = node['confidence']
        obj.priv = node['priv']
        return obj

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
    def get_total():
        """ Tulostaa henkilöiden määrän tietokannassa """

        query = """
            MATCH (p:Person) RETURN COUNT(p)
            """
        results =  shareds.driver.session().run(query)

        for result in results:
            return str(result[0])


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
        for i in range(len(self.citation_ref)):
            print ("Citationref_hlink: " + self.citation_ref[i])
        return True
