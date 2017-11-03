#!/usr/bin/python
# coding=UTF-8
# Taapeli harjoitustyö @ Sss 2016
# JMä 29.12.2015

import logging
from flask import Flask, render_template, request, redirect, url_for, flash, g
from datetime import datetime

global app
app = Flask(__name__, instance_relative_config=True)
#app.config.from_object('config')
app.config.from_pyfile('config.py') # instance-hakemistosta
app.secret_key = "kuu on juustoa"

#import instance.config as config
import models.dbutil
import models.loadfile          # Datan lataus käyttäjältä
import models.datareader        # Tietojen haku kannasta (tai työtiedostosta) 
import models.dataupdater       # Tietojen päivitysmetodit
import models.cvs_refnames      # Referenssinimien luonti
import models.gen.user          # Käyttäjien tiedot
from models.gen.dates import DateRange  # Aikaväit ym. määreet


""" Application route definitions
"""

@app.route('/')
# def index(): 
#     """Aloitussivun piirtäminen"""
#     return render_template("index.html")

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        return render_template("login/login.html")
    else:
        usrname = request.form['usrname']
        return render_template("login/logged.html", usrname = usrname)
    
@app.route('/tables')
def datatables(): 
    """Aloitussivun piirtäminen"""
    return render_template("login/datatables.html")

@app.route('/refnames')
def refnames(): 
    """Aloitussivun piirtäminen"""
    return render_template("login/reference.html")



""" ----------------------------- Kertova-sivut --------------------------------
"""

@app.route('/person/list/<string:selection>')   # <-- Ei käytössä?
@app.route('/person/list/', methods=['POST', 'GET'])
def show_person_list(selection=None):   
    """ tietokannan henkiloiden tai käyttäjien näyttäminen ruudulla """
    models.dbutil.connect_db()
    if request.method == 'POST':
        try:
            # Selection from search form
            name = request.form['name']
            rule = request.form['rule']
            keys = (rule, name)
            persons = models.datareader.lue_henkilot_k(keys)
            return render_template("k_persons.html", persons=persons, selection=keys)
        except Exception:
            flash("Ei oikeita hakukenttiä", category='warning')

    # the code below is executed if the request method
    # was GET or the credentials were invalid
    persons = []
    if selection:
        # Use selection filter
        keys = selection.split('=')
    else:
        keys = ('all',)
    persons = models.datareader.lue_henkilot_k(keys)
    return render_template("k_persons.html", persons=persons, selection=(keys))


@app.route('/person/<string:ehto>')
def show_person_page(ehto): 
    """ Kertova - henkilön tietojen näyttäminen ruudulla 
        uniq_id=arvo    näyttää henkilön tietokanta-avaimen mukaan
    """
    models.dbutil.connect_db()
    key, value = ehto.split('=')
    try:
        if key == 'uniq_id':
            person, events, photos, sources, families = \
                models.datareader.get_person_data_by_id(value)
            for f in families:
                print ("Perhe {} / {}".format(f.uniq_id, f.id))
                if f.mother:
                    print("  Äiti: {} / {} s. {}".format(f.mother.uniq_id, f.mother.id, f.mother.birth_date))
                if f.father:
                    print("  Isä:  {} / {} s. {}".format(f.father.uniq_id, f.father.id, f.father.birth_date))
                if f.children:
                    for c in f.children:
                        print("    Lapsi ({}): {} / {} *{}".format(c.gender, c.uniq_id, c.id, c.birth_date))
        else:
            raise(KeyError("Väärä hakuavain"))
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
    return render_template("k_person.html", 
        person=person, events=events, photos=photos, sources=sources, families=families)


@app.route('/events/loc=<locid>')
def show_location_page(locid): 
    """ Paikan tietojen näyttäminen ruudulla: hierarkia ja tapahtumat
    """
    models.dbutil.connect_db()
    try:
        # List 'locatils' has Place objects with 'parent' field pointing to
        # upper place in hierarcy. Events 
        place, locations, events = models.datareader.get_place_with_events(locid)
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
#     for p in locations:
#         print ("# {} ".format(p))
    return render_template("k_place_events.html", 
                           locid=locid, place=place, events=events, locations=locations)


@app.route('/lista/k_sources')
def show_sources(): 
    """ Lähdeluettelon näyttäminen ruudulla
    """
    models.dbutil.connect_db()
    try:
        sources = models.gen.source_citation.Source.get_source_list()
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
    return render_template("k_sources.html", sources=sources)


@app.route('/events/source=<sourceid>')
def show_source_page(sourceid): 
    """ Lähteen tietojen näyttäminen ruudulla: tapahtumat
    """
    models.dbutil.connect_db()
    try:
        stitle, events = models.datareader.get_source_with_events(sourceid)
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
    return render_template("k_source_events.html", 
                           stitle=stitle, events=events)


""" ------ Listaukset (kertova- tai taulukko-muodossa) -------------------------
"""

@app.route('/lista/<string:subj>')
def nayta_henkilot(subj):   
    """ tietokannan henkiloiden tai käyttäjien näyttäminen ruudulla """
    models.dbutil.connect_db()
    if subj == "k_persons":
        # Kertova-tyyliin
        persons = models.datareader.lue_henkilot_k()
        return render_template("k_persons.html", persons=persons)
    elif subj == "henkilot":
        # dburi vain tiedoksi!
        dbloc = g.driver.address
        dburi = ':'.join((dbloc[0],str(dbloc[1])))

        persons = models.datareader.lue_henkilot()
        return render_template("table_persons.html", persons=persons, uri=dburi)
    elif subj == "henkilot2":
        persons = models.datareader.lue_henkilot_k()
        return render_template("table_persons2.html", persons=persons)
    elif subj == "surnames":
        surnames = models.gen.person.Name.get_surnames()
        return render_template("table_surnames.html", surnames=surnames)
    elif subj == 'events_wo_cites':
        headings, titles, lists = models.datareader.read_events_wo_cites()
        return render_template("table_of_data.html", 
               headings=headings, titles=titles, lists=lists)
    elif subj == 'events_wo_place':
        headings, titles, lists = models.datareader.read_events_wo_place()
        return render_template("table_of_data.html", 
               headings=headings, titles=titles, lists=lists)
    elif subj == 'notes':
        titles, lists = models.datareader.get_notes()
        return render_template("table_of_data.html", 
                               headings=("Huomautusluettelo", "Note-kohteet"),
                               titles=titles, lists=lists)
    elif subj == 'objects':
        objects = models.datareader.read_objects()
        return render_template("table_objects.html", 
                               objects=objects)
    elif subj == 'people_wo_birth':
        headings, titles, lists = models.datareader.read_people_wo_birth()
        return render_template("table_of_data.html", 
               headings=headings, titles=titles, lists=lists)
    elif subj == 'old_people_top':
        headings, titles, lists = models.datareader.read_old_people_top()
        return render_template("table_of_data.html", 
               headings=headings, titles=titles, lists=lists)
    elif subj == 'repositories':
        repositories = models.datareader.read_repositories()
        return render_template("ng_table_repositories.html", 
                               repositories=repositories)
    elif subj == 'sources':
        sources = models.datareader.read_sources()
        return render_template("table_sources.html", 
                               sources=sources)
    elif subj == 'sources_wo_cites':
        headings, titles, lists = models.datareader.read_sources_wo_cites()
        return render_template("table_of_data.html", 
               headings=headings, titles=titles, lists=lists)
    elif subj == 'sources_wo_repository':
        headings, titles, lists = models.datareader.read_sources_wo_repository()
        return render_template("table_of_data.html", 
               headings=headings, titles=titles, lists=lists)
    elif subj == 'places':
        headings, titles, lists = models.datareader.read_places()
        return render_template("table_of_data.html", 
               headings=headings, titles=titles, lists=lists)
    elif subj == "users":
        lista = models.gen.user.User.get_all()
        return render_template("table_users.html", users=lista)
    else:
        return redirect(url_for('virhesivu', code=1, text= \
            "Aineistotyypin '" + subj + "' käsittely puuttuu vielä"))


@app.route('/lista/k_locations')
def show_locations(): 
    """ Paikkaluettelon näyttäminen ruudulla
    """
    models.dbutil.connect_db()
    try:
        # 'locations' has Place objects, which include also the lists of
        # nearest upper and lower Places as place[i].upper[] and place[i].lower[]
        locations = models.gen.place.Place.get_place_names()
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
#     for p in locations:
#         print ("# {} ".format(p))
    return render_template("k_locations.html", locations=locations)


@app.route('/lista/refnimet', defaults={'reftype': None})
@app.route('/lista/refnimet/<string:reftype>')
def nayta_refnimet(reftype): 
    """ referenssinimien näyttäminen ruudulla """
    models.dbutil.connect_db()
    if reftype and reftype != "":
        names = models.datareader.lue_typed_refnames(reftype)
        return render_template("table_refnames_1.html", names=names, reftype=reftype)
    else:
        names = models.datareader.lue_refnames()
        return render_template("table_refnames.html", names=names)
    
    
@app.route('/lista/people_by_surname/', defaults={'surname': ""})
@app.route('/lista/people_by_surname/<string:surname>')
def list_people_by_surname(surname): 
    """ henkilöiden, joilla on sama sukunimi näyttäminen ruudulla """
    models.dbutil.connect_db()
    people = models.datareader.get_people_by_surname(surname)
    return render_template("table_people_by_surname.html", 
                           surname=surname, people=people)
    
    
    #  linkki oli sukunimiluettelosta
@app.route('/lista/person_data/<string:uniq_id>')
def show_person_data(uniq_id): 
    """ henkilön tietojen näyttäminen ruudulla """
    models.dbutil.connect_db()
    person, events, photos, sources, families = models.datareader.get_person_data_by_id(uniq_id)
    return render_template("table_person_by_id.html", 
                       person=person, events=events, photos=photos, sources=sources)


@app.route('/lista/family_data/<string:uniq_id>')
def show_family_data(uniq_id): 
    """ henkilön perheen tietojen näyttäminen ruudulla """
    models.dbutil.connect_db()
    person, families = models.datareader.get_families_data_by_id(uniq_id)
    return render_template("table_families_by_id.html", 
                           person=person, families=families)


@app.route('/poimi/<string:ehto>')
def nayta_ehdolla(ehto):   
    """ Nimien listaus tietokannasta ehtolauseella
        oid=arvo        näyttää nimetyn henkilön
        names=arvo      näyttää henkilöt, joiden nimi alkaa arvolla
    """
    key, value = ehto.split('=')
    models.dbutil.connect_db()
    try:
        if key == 'oid':
            persons = models.datareader.lue_henkilot(oid=value)            
            return render_template("person.html", persons=persons)
        elif key == 'names':
            value=value.title()
            persons = models.datareader.lue_henkilot(names=value)
            return render_template("join_persons.html", 
                                   persons=persons, pattern=value)
        elif key == 'cite_sour_repo':
            events = models.datareader.read_cite_sour_repo(uniq_id=value)
            return render_template("cite_sour_repo.html", 
                                   events=events)
        elif key == 'repo_uniq_id':
            repositories = models.datareader.read_repositories(uniq_id=value)
            return render_template("repo_sources.html", 
                                   repositories=repositories)
        elif key == 'source_uniq_id':
            sources = models.datareader.read_sources(uniq_id=value)
            return render_template("source_citations.html", 
                                   sources=sources)
        elif key == 'uniq_id':
            persons = models.datareader.lue_henkilot_k(("uniq_id",value))            
            return render_template("person2.html", persons=persons)
        else:
            raise(KeyError("Vain oid:llä voi hakea"))
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))



""" -------------------------- Tietojen talletus ------------------------------
"""

@app.route('/lataa', methods=['POST'])
def lataa(): 
    """ Versio 2: Lataa cvs-tiedoston työhakemistoon kantaan talletettavaksi
    """
    try:
        infile = request.files['filenm']
        aineisto = request.form['aineisto']
        logging.debug('Saatiin ' + aineisto + ", tiedosto: " + infile.filename )
        
        models.loadfile.upload_file(infile)
         
    except Exception as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))

    return redirect(url_for('talleta', filename=infile.filename, subj=aineisto))


@app.route('/talleta/<string:subj>/<string:filename>')
def talleta(filename, subj):   
    """ tietojen tallettaminen kantaan """
    pathname = models.loadfile.fullname(filename)
    dburi = models.dbutil.connect_db()
    try:
        if subj == 'henkilot':  # Käräjille osallistuneiden tiedot
            status = models.datareader.datastorer(pathname)
        elif subj == 'refnimet': # Referenssinimet
            # Tallettaa Refname-objekteja 
            status = models.cvs_refnames.referenssinimet(pathname)
        elif subj == 'xml_file': # gramps backup xml file to Neo4j db
            status = models.datareader.xml_to_neo4j(pathname)
        elif subj == 'karajat': # TODO: Tekemättä
            status = "Käräjätietojen lukua ei ole vielä tehty"
        else:
            return redirect(url_for('virhesivu', code=1, text= \
                "Aineistotyypin '" + subj + "' käsittely puuttuu vielä"))
    except KeyError as e:
        return render_template("virhe_lataus.html", code=1, \
               text="Oikeaa sarakeotsikkoa ei löydy: " + str(e))
    return render_template("talletettu.html", text=status, uri=dburi)


""" ----------------------------------------------------------------------------
    Hallinta- ja harjoitusnäyttöjä
"""

@app.route('/tyhjenna/kaikki/kannasta')
def tyhjenna():   
    """ tietokannan tyhjentäminen mitään kyselemättä """
    models.dbutil.connect_db()
    msg = models.dbutil.alusta_kanta()
    return render_template("talletettu.html", text=msg)


@app.route('/aseta/confidence')
def aseta_confidence(): 
    """ tietojen laatuarvion asettaminen henkilöille """
    models.dbutil.connect_db()
    dburi = models.dbutil.connect_db()
    
    message = models.datareader.set_confidence_value()
    return render_template("talletettu.html", text=message, uri=dburi)


@app.route('/aseta/refnames')
def aseta_refnames(): 
    """ referenssinimien asettaminen henkilöille """
    models.dbutil.connect_db()
    dburi = models.dbutil.connect_db()
    
    message = models.datareader.set_refnames()
    return render_template("talletettu.html", text=message, uri=dburi)


@app.route('/yhdista', methods=['POST'])
def nimien_yhdistely():   
    """ Nimien listaus tietokannasta ehtolauseella
        oid=arvo        näyttää nimetyn henkilön
        names=arvo      näyttää henkilöt, joiden nimi alkaa arvolla
    """
    names = request.form['names']
    logging.debug('Poimitaan ' + names )
    return redirect(url_for('nayta_ehdolla', ehto='names='+names))


@app.route('/samahenkilo', methods=['POST'])
def henkiloiden_yhdistely():   
    """ Yhdistetään base-henkilöön join-henkilöt tapahtumineen, 
        minkä jälkeen näytetään muuttunut henkilölista
    """
    names = request.form['names']
    print (dir(request.form))
    base_id = request.form['base']
    join_ids = request.form.getlist('join')
    #TODO lisättävä valitut ref.nimet, jahka niitä tulee
    models.dataupdater.joinpersons(base_id, join_ids)
    flash('Yhdistettiin (muka) ' + str(base_id) + " + " + str(join_ids) )
    return redirect(url_for('nayta_ehdolla', ehto='names='+names))


@app.route('/newuser', methods=['POST'])
def new_user(): 
    """ Lisää tai päivittää käyttäjätiedon
    """
    try:
        models.dbutil.connect_db()
        userid = request.form['userid']
        if userid:
            u = models.gen.user.User(userid)
            u.name = request.form['name']
            u.save()
        else:
            flash("Anna vähintään käyttäjätunnus", 'warning')
         
    except Exception as e:
        flash("Lisääminen ei onnistunut: {} - {}".\
              format(e.__class__.__name__,str(e)), 'error')
        #return redirect(url_for('virhesivu', code=1, text=str(e)))

    return redirect(url_for('nayta_henkilot', subj='users'))


@app.route('/virhe_lataus/<int:code>/<text>')
def virhesivu(code, text=''):
    """ Virhesivu näytetään """
    logging.debug('Virhesivu ' + str(code) )
    return render_template("virhe_lataus.html", code=code, text=text)


""" ----------------------------------------------------------------------------
    Version 1 vanhoja harjoitussivuja ilman tietokantaa
"""

@app.route('/vanhat')
def index_old(): 
    """Vanhan aloitussivun piirtäminen"""
    return render_template("index_1.html")


@app.route('/lataa1a', methods=['POST'])
def lataa1a():
    """ Lataa tiedoston ja näyttää sen """
    try:
        infile = request.files['filenm']
        logging.debug('Ladataan tiedosto ' + infile.filename)
        models.loadfile.upload_file(infile)
    except Exception as e:
        return redirect(url_for('virhesivu', code=415, text=str(e)))

    return redirect(url_for('nayta1', filename=infile.filename, fmt='list'))

        
@app.route('/lataa1b', methods=['POST'])
def lataa1b(): 
    """ Lataa tiedoston ja näyttää sen taulukkona """
    infile = request.files['filenm']
    try:
        models.loadfile.upload_file(infile)
    except Exception as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))

    return redirect(url_for('nayta1', filename=infile.filename, fmt='table'))


@app.route('/lista1/<string:fmt>/<string:filename>')
def nayta1(filename, fmt):   
    """ tiedoston näyttäminen ruudulla """
    try:
        pathname = models.loadfile.fullname(filename)
        with open(pathname, 'r', encoding='UTF-8') as f:
            read_data = f.read()    
    except IOError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
    except UnicodeDecodeError as e:
        return redirect(url_for('virhesivu', code=1, \
               text="Tiedosto ei ole UTF-8. " + str(e)))  

    # Vaihtoehto a:
    if fmt == 'list':   # Tiedosto sellaisenaan
        return render_template("lista1.html", name=pathname, data=read_data)
    
    # Vaihtoehto b: Luetaan tiedot taulukoksi
    else:
        try:
            persons = models.datareader.henkilolista(pathname)
            return render_template("table_persons.html", name=pathname, \
                   persons=persons)
        except Exception as e:
            return redirect(url_for('virhesivu', code=1, text=str(e)))


""" Application filter definitions 
"""
@app.template_filter('pvt')
def _jinja2_filter_dates(daterange):
    """ Aikamääreet suodatetaan suomalaiseksi """
    return str(DateRange(daterange))

@app.template_filter('pvm')
def _jinja2_filter_date(date_str, fmt=None):
    """ ISO-päivämäärä 2017-09-20 suodatetaan suomalaiseksi 20.9.2017 """
    try:
        a = date_str.split('-')
        if len(a) == 3:
            p = int(a[2])
            k = int(a[1])
            return "{}.{}.{}".format(p,k,a[0]) 
        elif len(a) == 2:
            k = int(a[1])
            return "{}.{}".format(k,a[0]) 
        else:
            return "{}".format(a[0])
    except:
        return date_str
    
@app.template_filter('timestamp')
def _jinja2_filter_datestamp(time_str, fmt=None):
    """ Unix time 1506950049 suodatetaan selväkieliseksi 20.9.2017 """
    try:
        s = datetime.fromtimestamp(int(time_str)).strftime('%d.%m.%Y %H:%M:%S')
        return s
    except:
        return time_str


@app.template_filter('transl')
def _jinja2_filter_translate(term, var_name, lang="fi"):
    """ Given term is translated depending of var_name name.
        No language selection yet.
        
        'nt'  = Name types
        'evt' = Event types
        'role' = Event role
        'lt'  = Location types
        'lt_in' = Location types, inessive form
    """
#     print("# {}[{}]".format(var_name, term))
    if var_name == "nt":
        # Name types
        tabl = {
            "Also Known As": "tunnettu myös",
            "Birth Name": "syntymänimi",
            "Married Name": "avionimi"
        }
    if var_name == "evt":
        # Event types    
        tabl = {
            "Residence": "asuinpaikka",
            "Occupation": "ammatti",
            "Birth": "syntymä",
            "Death": "kuolema",
            "Luottamustoimi": "luottamustoimi",
            "Graduation": "valmistuminen",
            "Marriage": "avioliitto",
            "Baptism": "kaste",
            "Burial": "hautaus",
            "Cause Of Death": "kuolinsyy",
            "Education": "koulutus",
            "Degree": "oppiarvo",
            "Christening": "kristillinen kaste",
            "Military Service": "asepalvelus",
            "Confirmation": "ripille pääsy",
            "Ordination": "palkitseminen",
            "Sota": "sota"
        }
    elif var_name == "role":
        # Name types
        tabl = {
            "Kummi": "kummina",
            "Clergy": "pappina"
        }
    elif var_name == "conf":
        # Confidence levels
        tabl = {
            "0":"erittäin matala",
            "1":"alhainen",
            "2":"normaali",
            "3":"korkea",
            "4":"erittäin korkea"
            }
    elif var_name == "conf_star":
        # Confidence level symbols oo, o, *, **, ***
        tabl = {
            "0":"oo",   # fa-exclamation-circle [&#xf06a;]
            "1":"o",
            "2":"*",    # fa-star [&#xf005;]
            "3":"**",
            "4":"***"
            }
    elif var_name == "lt":
        # Location types
        tabl = {
            "Alus": "alus",
            "Borough": "aluehallintoyksikkö",
            "Building": "rakennus tai torppa",  #"rakennus",
            "City": "paikkakunta",              # "kaupunki",
            "Country": "maa",
            "District": "lääni",
            "Farm": "tila",
            "Hamlet": "talo",
            "Hautausmaa": "hautausmaa",
            "Kappeliseurakunta": "kappeliseurakunta",
            "Kartano": "kartano",
            "Kuntakeskus": "kuntakeskus",
            "Linnoitus": "linnoitus",
            "Locality": "kulmakunta",
            "Organisaatio": "organisaatio",
            "Parish": "seurakunta",
            "Region": "alue",
            "State": "valtio",
            "Tontti": "tontti",
            "Village": "kylä",
            "srk": "seurakunta"
        }
    elif var_name == "lt_in":
        # Location types, inessive
        tabl = {
            "Alus": "aluksessa",
            "Borough": "aluehallintoyksikössä",
            "Building": "rakennuksessa tai torpassa",   #"rakennuksessa",
            "City": "paikassa",                         # "kaupungissa",
            "Country": "maassa",
            "District": "läänissä",
            "Farm": "tilalla",
            "Hamlet": "talossa",
            "Hautausmaa": "hautausmaalla",
            "Kappeliseurakunta": "kappeliseurakunnassa",
            "Kartano": "kartanossa",
            "Kuntakeskus": "kuntakeskuksessa",
            "Linnoitus": "linnoituksessa",
            "Locality": "kulmakuntannassa",
            "Organisaatio": "organisaatiossa",
            "Parish": "seurakunnassa",
            "Region": "alueella",
            "State": "valtiossa",
            "Tontti": "tontilla",
            "Village": "kylässä",
            "srk": "seurakunnassa"
        }
        try:    
            return tabl[term]
        except:
            return term + ":ssa"

    try:
        return tabl[term]
    except:
        return term + '?'


""" ----------------------------- Käynnistys ------------------------------- """

if __name__ == '__main__':
    if True:
        # Ajo paikallisesti
        logging.basicConfig(level=logging.DEBUG)
        print ("stk-run.__main__ ajetaan DEGUB-moodissa")
        app.run(debug='DEBUG')
    else:
        # Julkinen sovellus
        logging.basicConfig(level=logging.INFO)
        app.run(host='0.0.0.0', port=8000)

