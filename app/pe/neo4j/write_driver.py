'''
Created on 23.3.2020

@author: jm
'''
import logging
logger = logging.getLogger('stkserver')
from datetime import date #, datetime

from bl.base import Status
from bl.place import PlaceBl, PlaceName

from pe.neo4j.cypher.cy_person import CypherPerson
from pe.neo4j.cypher.cy_batch_audit import CypherBatch
from pe.neo4j.cypher.cy_place import CypherPlace
from pe.neo4j.cypher.cy_gramps import CypherObjectWHandle


class Neo4jWriteDriver:
    '''
    This driver for Neo4j database maintains transaction and executes
    different update functions.
    '''

    def __init__(self, driver, use_transaction=True):
        ''' Create a writer/updater object with db driver and user context.
        
            - driver             neo4j.DirectDriver object
            - use_transaction    bool
        '''
        self.driver = driver
        self.use_transaction = use_transaction
        if use_transaction:
            self.tx = driver.session().begin_transaction()
        else:
            # No transaction
            self.tx = driver.session()


    def dw_commit(self):
        """ Commit transaction.
        """
        if self.tx.closed():
            print("Transaction already closed!")
            return 0
        try:
            self.tx.commit()
            logger.info(f'-> bp.gramps.xml_dom_handler.DOM_handler.commit/ok f="{self.file}"')
            print("Transaction committed")
            return 0
        except Exception as e:
            msg = f'{e.__class__.__name__}, {e}'
            logger.info('-> bp.gramps.xml_dom_handler.DOM_handler.commit/fail"')
            print("pe.db_writer.DbWriter.commit: Transaction failed "+ msg)
            self.blog.log_event({'title':_("Database save failed due to {}".\
                                 format(msg)), 'level':"ERROR"})
            return msg

    def dw_rollback(self):
        """ Rollback transaction.
        """
        self.tx.rollback()
        print("Transaction discarded")
        logger.info('-> pe.neo4j.write_driver.Neo4jWriteDriver.dw_rollback')


    # ----- Batch -----

    def dw_get_new_batch_id(self):
        ''' Find next unused Batch id.
        
            Returns {id, status, [statustext]}
        '''
        
        # 1. Find the latest Batch id of today from the db
        base = str(date.today())
        ext = 0
        try:
            result = self.tx.run(CypherBatch.batch_find_id,
                                 batch_base=base).single()
            if result:
                batch_id = result.get('bid')
                print(f"# Pervious batch_id={batch_id}")
                i = batch_id.rfind('.')
                ext = int(batch_id[i+1:])
        except AttributeError as e:
            # Normal exception: this is the first batch of day
            ext = 0
        except Exception as e:
            print(f"pe.neo4j.write_driver.Neo4jWriteDriver.dw_get_new_batch_id: {e}")
            return {'status':Status.ERROR, 
                    'statustext':'Neo4jWriteDriver.dw_get_new_batch_id: '
                    '{e.__class__.name} {e}'}
        
        # 2. Form a new batch id
        batch_id = "{}.{:03d}".format(base, ext + 1)

        print("# New batch_id='{}'".format(batch_id))
        return {'status':Status.OK, 'id':batch_id}


    def dw_batch_save(self, attr):
        ''' Creates or updates Batch node.

            attr = {"mediapath", "file", "id", "user", "status"}

            Batch.timestamp is created in Cypher clause.
       '''
        try:
            attr = {
                "mediapath": self.mediapath,
                "file": self.file,
                "id": self.bid,
                "user": self.user,
                #timestamp": <to be set in cypher>,
                "status": self.status
            }
            self.driver##########       
            self.tx.run(CypherBatch.batch_create, b_attr=attr)
        except Exception as e:
            print(f"pe.neo4j.write_driver.Neo4jWriteDriver.dw_batch_save failed: {e}")
            return {'status':Status.ERROR, 
                    'statustext':'Neo4jWriteDriver.dw_batch_save: '
                    '{e.__class__.name} {e}'}


    # ----- Person ----

    def dw_update_person_confidence(self, uniq_id:int):
        """ Collect Person confidence from Person and Event nodes and store result in Person.
 
            Voidaan lukea henkilön tapahtumien luotettavuustiedot kannasta
        """
        sumc = 0
        new_conf = None
        try:
            result = self.tx.run(CypherPerson.get_confidences, id=uniq_id)
            for record in result:
                # Returns person.uniq_id, COLLECT(confidence) AS list
                orig_conf = record['confidence']
                confs = record['list']
                for conf in confs:
                    sumc += int(conf)

            conf_float = sumc/len(confs)
            new_conf = "%0.1f" % conf_float # string with one decimal
            if orig_conf != new_conf:
                # Update confidence needed
                self.tx.run(CypherPerson.set_confidence,
                            id=self.uniq_id, confidence=new_conf)

                return {'confidence':new_conf, 'status':Status.UPDATED}
            return {'confidence':new_conf, 'status':Status.OK}

        except Exception as e:
            msg = f'Neo4jWriteDriver.dr_update_person_confidence: {e.e.__class__.__name__} {e}'
            print(msg)
            return {'confidence':new_conf, 'status':Status.ERROR,
                    'statustext': msg}


    # ----- Place -----

    def dw_place_set_default_names(self, place_id, fi_id, sv_id):
        ''' Creates default links from Place to fi and sv PlaceNames.

            - place_id      Place object id
            - fi_id         PlaceName object id for fi
            - sv_id         PlaceName object id for sv
        '''
        try:
            if fi_id == sv_id:
                result = self.tx.run(CypherPlace.link_name_lang_single, 
                                     place_id=place_id, fi_id=fi_id)
            else:
                result = self.tx.run(CypherPlace.link_name_lang, 
                                     place_id=place_id, fi_id=fi_id, sv_id=sv_id)
            x = None
            for x, _fi, _sv in result:
                #print(f"# Linked ({x}:Place)-['fi']->({fi}), -['sv']->({sv})")
                pass

            if not x:
                logger.warning("eo4jWriteDriver.place_set_default_names: not created "
                     f"Place {place_id}, names fi:{fi_id}, sv:{sv_id}")

        except Exception as err:
            logger.error(f"Neo4jWriteDriver.place_set_default_names: {err}")
            return err


    def dw_media_save_w_handles(self, uniq_id:int, media_refs:list):
        ''' Save media object and it's Note and Citation references
            using their Gramps handles.
            
            media_refs:
                media_handle      # Media object handle
                media_order       # Media reference order nr
                crop              # Four coordinates
                note_handles      # list of Note object handles
                citation_handles  # list of Citation object handles
        '''
        doing = "?"
        try:
            for resu in media_refs:
                r_attr = {'order':resu.media_order}
                if resu.crop:
                    r_attr['left'] = resu.crop[0]
                    r_attr['upper'] = resu.crop[1]
                    r_attr['right'] = resu.crop[2]
                    r_attr['lower'] = resu.crop[3]
                doing = f"(src:{uniq_id}) -[{r_attr}]-> Media {resu.media_handle}"
#                 print(doing)
                result = self.tx.run(CypherObjectWHandle.link_media, 
                                     root_id=uniq_id, handle=resu.media_handle, 
                                     r_attr=r_attr)
                media_uid = result.single()[0]    # for media object

                for handle in resu.note_handles:
                    doing = f"{media_uid}->Note {handle}"
#                     result = self.tx.run('MATCH (s), (t) WHERE ID(s)=$root_id and t.handle=$handle RETURN s,t', 
#                         root_id=media_uid, handle=handle)
#                     for s,t in result: print(f"\nMedia {s}\nNote {t}")
                    self.tx.run(CypherObjectWHandle.link_note, 
                                root_id=media_uid, handle=handle)

                for handle in resu.citation_handles:
                    doing = f"{media_uid}->Citation {handle}"
#                     result = self.tx.run('MATCH (s), (t) WHERE ID(s)=$root_id and t.handle=$handle RETURN s,t', 
#                         root_id=media_uid, handle=handle)
#                     for s,t in result: print(f"\nMedia {s}\nCite {t}")
                    self.tx.run(CypherObjectWHandle.link_citation, 
                                root_id=media_uid, handle=handle)

        except Exception as err:
            logger.error(f"Neo4jWriteDriver.media_save_w_handles {doing}: {err}")


    def dw_mergeplaces(self, id1, id2):
        ''' Merges given two Place objects using apoc library.
        '''
        cypher_delete_namelinks = """
            match (node) -[r:NAME_LANG]-> (pn)
            where id(node) = $id
            delete r
        """
        cypher_mergeplaces = """
            match (p1:Place)        where id(p1) = $id1 
            match (p2:Place)        where id(p2) = $id2
            call apoc.refactor.mergeNodes([p1,p2],
                {properties:'discard',mergeRels:true})
            yield node
            with node
            match (node) -[r2:NAME]-> (pn2)
            return node, collect(pn2) as names
        """
        self.tx.run(cypher_delete_namelinks,id=id1).single()
        rec = self.tx.run(cypher_mergeplaces,id1=id1,id2=id2).single()
        node = rec['node']
        place = PlaceBl.from_node(node)
        name_nodes = rec['names']
        name_objects = [PlaceName.from_node(n) for n in name_nodes]
        return place, name_objects
    