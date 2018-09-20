'''
    Citation class for handling Citation nodes and relations and
    NodeRef class to store data of referring nodes and Source

Created on 2.5.2017 from Ged-prepare/Bus/classes/genealogy.py

@author: Jorma Haapasalo <jorma.haapasalo@pp.inet.fi>
'''

from sys import stderr

from .source import Source
from models.cypher_gramps import Cypher_citation_w_handle
import shareds


class Citation:
    """ Viittaus
            
        Properties:
                handle          
                change
                id               esim. "C0001"
                dateval          str date
                page             str page
                confidence       str confidence
                noteref_hlink    str huomautuksen osoite
                source_handle    str handle of source   _or_
                source_id        int uniq_id of source
     """

    def __init__(self):
        """ Luo uuden citation-instanssin """
        self.handle = ''
        self.change = 0
        self.id = ''
        self.dateval = ''
        self.page = ''
        self.noteref_hlink = []
        self.source_handle = ''
        self.source_id = None
        self.sources = []   # For creating display sets
        self.citators = []  # For creating display sets


    def __str__(self):
        return "{} '{}'".format(self.id, self.page)


    @staticmethod       
    def get_persons_citations (uniq_id):
        """ Read 'Person -> Event -> Citation' and 'Person -> Citation' paths

            Haetaan henkilön Citationit, suoraan tai välisolmujen kautta
            
            Returns list of Citations and list of Source ids
        """
        get_persons_citation_paths = """
match path = (p) -[*]-> (c:Citation) -[:SOURCE]-> (s:Source)
    where id(p) = 72104 
    with relationships(path) as rel, c, id(s) as source_id
return extract(x IN rel | endnode(x))  as end, source_id
    order by source_id, size(end)"""

# ╒══════════════════════════════════════════════════════════════════════╤═══════════╕
# │"end"                                                                 │"source_id"│
# ╞══════════════════════════════════════════════════════════════════════╪═══════════╡
# │[{"datetype":0,"change":1521882842,"description":"","handle":"_dd7681e│91637      │
# │08a259cca1aa0c055cb2","attr_type":"","id":"E2820","date2":1869085,"typ│           │
# │e":"Birth","date1":1869085,"attr_value":""},                          │           │
# │                                            {"handle":"_dd768dca3a6265│           │
# │4475a5726dfcd","page":"s. 336 1825 Augusti 29 kaste 27","id":"C1362","│           │
# │dateval":"","confidence":"2","change":1521882911},{"handle":"_dd162a3b│           │
# │cb7533c6d1779e039c6","id":"S0409","stitle":"Askainen syntyneet 1783-18│           │
# │25","change":"1519858899"}]                                           │           │
# ├──────────────────────────────────────────────────────────────────────┼───────────┤
# │[{"handle":"_dd7686926d946cd18c5642e61e2","id":"C1361","page":"1891 Sy│91657      │
# │yskuu 22","dateval":"","change":1521882215,"confidence":"2"},{"handle"│           │
# │:"_dd3d7f7206c3ca3408c9daf6c58","id":"S0333","stitle":"Askainen kuolle│           │
# │et 1890-1921","change":"1520351255"}]                                 │           │
# ├──────────────────────────────────────────────────────────────────────┼───────────┤
# │[{"datetype":0,"change":1521882240,"description":"","handle":"_dd76825│91657      │
# │122e5977bf3ee88e213f","attr_type":"","id":"E2821","date2":1936694,"typ│           │
# │e":"Death","date1":1936694,"attr_value":""},                          │           │
# │                                            {"handle":"_dd7686926d946c│           │
# │d18c5642e61e2","id":"C1361","page":"1891 Syyskuu 22","dateval":"","cha│           │
# │nge":1521882215,"confidence":"2"},{"handle":"_dd3d7f7206c3ca3408c9daf6│           │
# │c58","id":"S0333","stitle":"Askainen kuolleet 1890-1921","change":"152│           │
# │0351255"}]                                                            │           │
# └──────────────────────────────────────────────────────────────────────┴───────────┘
        
        result = shareds.driver.session().run(get_persons_citation_paths, 
                                              pid=uniq_id)
        citations = []
        source_ids = []
        for record in result:
            nodes = record['end']
            c = Citation()
            c.source_id = record['source_id']
            if len(source_ids) == 0 or c.source_id != source_ids[-1]:
                # Get data of this source
                source_ids.append(c.source_id)

            if len(nodes) == 1:
                # Direct link (:Person) --> (:Citation)
                # Nodes[0] ~ Citation
                # <Node id=89360 labels={'Citation'} 
                #       properties={'change': 1521882911, 
                #                   'handle': '_dd768dca3a62654475a5726dfcd', 
                #                   'page': 's. 336 1825 Augusti 29 kaste 27', 
                #                   'id': 'C1362', 'confidence': '2', 'dateval': ''
                #                  }>
                cit = nodes[0]
            else:
                # Longer path (:Person) -> (x) -> (:Citation)
                # Nodes[0] ~ Event (or something else)
                # Nodes[1] ~ Citation
                eve = nodes[0]
                cit = nodes[1]
                e = NodeRef()
                e.uniq_id = eve.id
                e.eventtype = eve['type']
                c.citators.append(e)

            c.uniq_id = cit.id
            c.id = cit['id']
            c.label = cit.labels.pop()
            c.page = cit['page']
            c.confidence = cit['confidence']

            citations.append(c)
        
        return [citations, source_ids]


    @staticmethod       
    def get_source_repo (uniq_id=None):
        """ Read Citation -> Source -> Repository chain
            and optionally Notes.            
            Citation has all data but c.handle

            Voidaan lukea annetun Citationin lähde ja arkisto kannasta
        """

        if uniq_id:
            where = "WHERE ID(c)={} ".format(uniq_id)
        else:
            where = ''
        
        query = """
 MATCH (c:Citation) -[r:SOURCE]-> (source:Source) 
    -[p:REPOSITORY]-> (repo:Repository) {0}
 OPTIONAL MATCH (c) -[n:NOTE]-> (note:Note)
   WITH c, r, source, p, repo 
   ORDER BY c.page, note
 RETURN ID(c) AS id, 
    c.dateval AS date,
    c.page AS page,
    c.confidence AS confidence, 
    note.text AS notetext,
    COLLECT(DISTINCT [ID(source), 
             source.stitle, 
             p.medium, 
             ID(repo), 
             repo.rname, 
             repo.type]) AS sources
 """.format(where)
                
        return shareds.driver.session().run(query)
    
    
    def get_sourceref_hlink(self):
        """ Voidaan lukea lähdeviittauksen lähteen uniq_id kannasta
        """
        
        query = """
 MATCH (citation:Citation)-[r:SOURCE]->(source:Source) WHERE ID(citation)={}
 RETURN ID(source) AS id
 """.format(self.uniq_id)
                
        result = shareds.driver.session().run(query)
        for record in result:
            if record['id']:
                self.source_handle = record['id']

    
    @staticmethod       
    def get_total():
        """ Tulostaa lähteiden määrän tietokannassa """
                        
        query = """
            MATCH (c:Citation) RETURN COUNT(c)
            """
        results = shareds.driver.session().run(query)
        
        for result in results:
            return str(result[0])


    def print_data(self):
        """ Tulostaa tiedot """
        print ("*****Citation*****")
        print ("Handle: " + self.handle)
        print ("Change: {}".format(self.change))
        print ("Id: " + self.id)
        print ("Dateval: " + self.dateval)
        print ("Page: " + self.page)
        print ("Confidence: " + self.confidence)
        if len(self.noteref_hlink) > 0:
            for i in range(len(self.noteref_hlink)):
                print ("Noteref_hlink: " + self.noteref_hlink[i])
        if self.source_handle != '':
            print ("Sourceref_hlink: " + self.source_handle)
        return True


    def save(self, tx):
        """ Saves this Citation and connects it to it's Notes and Sources"""

        try:
            # Create a new Citation node
                
            c_attr = {
                "handle": self.handle,
                "change": self.change,
                "id": self.id,
                "dateval": self.dateval, 
                "page": self.page, 
                "confidence": self.confidence
            }
            tx.run(Cypher_citation_w_handle.create, c_attr=c_attr)
        except Exception as err:
            print("Virhe (Citation.save): {0}".format(err), file=stderr)
            raise SystemExit("Stopped due to errors")    # Stop processing
            #TODO raise ConnectionError("Citation.save: {0}".format(err))

        # Make relations to the Note nodes
        for hlink in self.noteref_hlink:
            try:
                tx.run(Cypher_citation_w_handle.link_note, 
                       handle=self.handle, hlink=hlink)
            except Exception as err:
                print("Virhe (Citation.save:Note hlink): {0}".format(err), file=stderr)

        try:   
            # Make relation to the Source node
            if self.source_handle != '':
                tx.run(Cypher_citation_w_handle.link_source,
                       handle=self.handle, hlink=self.source_handle)
        except Exception as err:
            print("Virhe: {0}".format(err), file=stderr)
            
        return


class NodeRef():
    ''' Carries data of citating nodes
            label            str Person or Event
            uniq_id          int Persons uniq_id
            source_id        int The uniq_id of the Source citated
            clearname        str Persons display name
            eventtype        str type for Event
            edates           DateRange date expression for Event
            date             str date for Event
    '''
    def __init__(self):
        self.label = ''
        self.uniq_id = ''
        self.source_id = None
        self.clearname = ''
        self.eventtype = ''
        self.edates = None
        self.date = ''

    def __str__(self):
        return "{} {} '{}'".format(self.uniq_id, self.eventtype, self.clearname)
