'''
Created on 12.8.2018

@author: jm
'''
import logging 
#import os
from flask import send_file
from bp.scene.models import media
logger = logging.getLogger('stkserver')
import time

from flask import render_template, request, redirect, url_for, flash, session as user_session
from flask_security import current_user, login_required #, roles_accepted
#from flask_babelex import _

from . import bp
from bp.scene.scene_reader import get_person_full_data
from bp.scene.scene_reader import get_a_person_for_display_apoc
from models.gen.person_combo import Person_combo
from models.gen.family_combo import Family_combo
from models.gen.place_combo import Place_combo
from models.gen.source import Source

from models.datareader import read_persons_with_events
from models.datareader import get_person_data_by_id # -- vanhempi versio ---
from models.datareader import get_event_participants
from models.datareader import get_place_with_events
from models.datareader import get_source_with_events
from models.owner import OwnerFilter

# Narrative start page
@bp.route('/scene',  methods=['GET', 'POST'])
def scene():
    """ Home page for scene narrative pages ('kertova') for anonymous. """    
    print(f"--- {request}")
    print(f"--- {user_session}")
    #print("-> bp.scene.routes.scene")
    my_filter = OwnerFilter(user_session, current_user, request)
    my_filter.set_scope_from_request(request, 'person_scope')
    print(f"-> bp.scene.routes.scene: home saving '{my_filter.scope[0]}'")
    return render_template('/scene/index_scene.html')


# @bp.route('/scene/persons/restricted')
# def show_persons_restricted(selection=None):
#     """ NOT IN USE Show list of selected Persons, limited information.
#  
#         for non-logged users from login_user.html """
#     if not current_user.is_authenticated:
#         # Tässä aseta sisäänkirjautumattoman käyttäjän rajoittavat parametrit.
#         # Vaihtoehtoisesti kutsu toista metodia.
#         keys = ('all',)
#     persons = read_persons_with_events(keys)
#     print("-> bp.scene.routes.show_persons_restricted")
#     return render_template("/scene/persons.html", persons=persons, 
#                            menuno=1, rule=keys)

# ------------------------- Menu 1: Person search ------------------------------

@bp.route('/scene/persons', methods=['POST', 'GET'])
def show_person_list(selection=None):
    """ Show list of selected Persons for menu(0). """
    t0 = time.time()
    if request.method == 'POST':
        try:
            # Selection from search form
            name = request.form['name']
            rule = request.form['rule']
            keys = (rule, name)
            print(f"-> bp.scene.routes.show_person_list POST {keys}")
            persons = read_persons_with_events(keys)
            return render_template("/scene/persons.html", persons=persons, menuno=0,
                                   name=name, rule=keys, elapsed=time.time()-t0)
        except Exception as e:
            logger.debug("iError {} in show_person_list".format(e))
            flash("Valitse haettava nimi ja tyyppi", category='warning')

    # the code below is executed if the request method
    # was GET or the credentials were invalid
    persons = []
    if selection:
        # Use selection filter
        keys = selection.split('=')
    else:
        keys = ('surname',)
    persons = [] #datareader.read_persons_with_events(keys)
    print(f"-> bp.scene.routes.show_person_list GET {keys}")
    return render_template("/scene/persons.html", persons=persons,
                           menuno=0, rule=keys, elapsed=time.time()-t0)

@bp.route('/scene/persons/ref=<string:refname>')
@bp.route('/scene/persons/ref=<string:refname>/<opt>')
@login_required
def show_persons_by_refname(refname, opt=""):
    """ List persons by refname.
    """
    keys = ('refname', refname)
    if current_user.is_authenticated:
        user=current_user.username
    else:
        user=None
    ref = ('ref' in opt)
    order = 0
    persons = read_persons_with_events(keys, user=user, take_refnames=ref, order=order)
    print("-> bp.scene.routes.show_persons_by_refname")
    return render_template("/scene/persons.html", persons=persons, menuno=1, 
                           order=order, rule=keys)

@bp.route('/scene/persons/all/<string:opt>')
@bp.route('/scene/persons/all/')
#     @login_required
def show_all_persons_list(opt=''):
    """ List all persons for menu(1)    OLD MODEL WITHOUT User selection

        The string opt may include keys 'ref', 'sn', 'pn' in arbitary order
        with no delimiters. You may write 'refsn', 'ref:sn' 'sn-ref' etc.
        TODO Should have restriction by owner's UserProfile 
    """
    t0 = time.time()
    keys = ('all',)
    if current_user.is_authenticated:
        user=current_user.username
    else:
        user=None
    ref = ('ref' in opt)
    if 'fn' in opt: order = 1   # firstname
    elif 'pn' in opt: order = 2 # firstname
    else: order = 0             # surname
    persons = read_persons_with_events(keys, user=user, take_refnames=ref, order=order)
    print("-> bp.scene.routes.show_all_persons_list")
    return render_template("/scene/persons.html", persons=persons, menuno=1, 
                           order=order,rule=keys, elapsed=time.time()-t0)



# -------------------------- Menu 12 Persons by user ---------------------------


@bp.route('/scene/persons_all/')
def show_my_persons():
    """ List all persons for menu(12).

        Both my own and other persons depending on url attribute div
        or session variables.

        The position in persons list is defined by -
           1. by attribute fw, if defined (the forward arrow or from seach field)
           2. by session next_person[1], if defined (the page last visited)
              #TODO: next_person[0] is not in use, yet (backward arrow)
           3. otherwise "" (beginning)
    """
    print(f"--- {request}")
    print(f"--- {user_session}")
    # Set filter by owner and the data selection
    my_filter = OwnerFilter(user_session, current_user, request)
    # Which range of data is shown
    my_filter.set_scope_from_request(request, 'person_scope')
    # About how mamy items to read
    count = int(request.args.get('c', 100))

    #print(f"-> bp.scene.routes.show_my_persons: read persons forward from '{my_filter.scope[0]}'")
    t0 = time.time()
    persons = Person_combo.read_my_persons_list(o_filter=my_filter, limit=count)

    return render_template("/scene/persons_list.html", persons=persons, menuno=12, 
                           owner_filter=my_filter, elapsed=time.time()-t0)



@bp.route('/scene/person/<int:uid>')
@bp.route('/scene/person', methods=['GET'])
#     @login_required
def show_a_person(uid=None):
    """ One Person with all connected nodes - NEW version 3: not using apoc any more.
    
        Korvaamaan metodi show_person_page()
    """
    t0 = time.time()
    uid = request.args.get('uuid', uid)
    if not uid:
        return redirect(url_for('virhesivu', code=1, text="Missing Person key"))

    if current_user.is_authenticated:
        user=current_user.username
    else:
        user=None
    
    if isinstance(uid, int):    # v2 Person page data
        person, objs, marks = get_a_person_for_display_apoc(uid, user)
    else:                       # v3 Person page data
        person, objs, marks = get_person_full_data(uid, user)
    if not person:
        return redirect(url_for('virhesivu', code=1, text="Henkilötietoja ei saatu"))
#     for m in marks:
#         print("Citation mark {}".format(m))
#     for e in person.events:
#         for ni in e.note_ref:
#             print("Event {} Note {}: {}".format(e.uniq_id, ni, objs[ni]))

#     print(person.sex_str())
    print("-> bp.scene.routes.show_a_person")
    from bp.scene.models.media import get_thumbname
    for i in person.media_ref:
        print(get_thumbname(objs[i].uuid))
    return render_template("/scene/person_pg.html", person=person, obj=objs, 
                           marks=marks, menuno=12, elapsed=time.time()-t0)


@bp.route('/scene/person/uuid=<pid>')
@bp.route('/scene/person=<int:pid>')
#     @login_required
def show_person_page(pid):
    """ Full homepage for a Person in database (vanhempi versio).

        The pid may be 1) an uuid or 2) an uniq_id
    """
    t0 = time.time()
    try:
        person, events, photos, citations, families = get_person_data_by_id(pid)
        for f in families:
            print ("{} in Family {} / {}".format(f.role, f.uniq_id, f.id))
            if f.mother:
                print("  Mother: {} / {} s. {}".\
                      format(f.mother.uniq_id, f.mother.id, f.mother.birth_date))
            if f.father:
                print("  Father:  {} / {} s. {}".\
                      format(f.father.uniq_id, f.father.id, f.father.birth_date))
            for c in f.children:
                print("    Child ({}): {} / {} s. {}".\
                      format(c.sex_str(), c.uniq_id, c.id, c.birth_date))
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
    print("-> bp.scene.routes.show_person_page")
    return render_template("/scene/person.html", person=person, events=events, 
                           photos=photos, citations=citations, families=families, 
                           elapsed=time.time()-t0)


@bp.route('/scene/event/<int:uniq_id>')
def show_event(uniq_id):
    """ Table of a (baptism) Event persons.

        Kastetapahtuman tietojen näyttäminen ruudulla
        
        Derived from bp.tools.routes.show_baptism_data()
    """
    event, persons = get_event_participants(uniq_id)
    return render_template("/scene/event.html",
                           event=event, persons=persons)


# ------------------------------ Menu 3: Families --------------------------------

@bp.route('/scene/families')
def show_families():
    """ List of Families for menu(3)
    """
    print(f"--- {request}")
    print(f"--- {user_session}")
    # Set filter by owner and the data selection
    my_filter = OwnerFilter(user_session, current_user, request)
    # Which range of data is shown
    my_filter.set_scope_from_request(request, 'person_scope')
    opt = request.args.get('o', 'father', type=str)
    count = request.args.get('c', 100, type=int)
    t0 = time.time()
        
    # 'families' has Family objects
    families = Family_combo.get_families(o_filter=my_filter, opt=opt, limit=count)

    return render_template("/scene/families.html", families=families, 
                           owner_filter=my_filter, elapsed=time.time()-t0)

@bp.route('/scene/family=<int:fid>')
def show_family_page(fid):
    """ Home page for a Family.

        fid = id(Family)
    """
    try:
#         family = Family_combo()   #, events = get_place_with_events(fid)
#         family.uniq_id = fid
        family = Family_combo.get_family_data(fid)
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))

    return render_template("/scene/family.html", family=family, menuno=3)

@bp.route('/pop/family=<int:fid>')
def show_family_popup(fid):
    """ Small Family pop-up.
    """
    #TODO Gen only fewer pieces of data
    family = Family_combo.get_family_data(fid)
    return render_template("/scene/family_pop.html", family=family)

# ------------------------------ Menu 4: Places --------------------------------

@bp.route('/scene/locations')
def show_places():
    """ List of Places for menu(4)
    """
    t0 = time.time()
    try:
        # 'locations' has Place objects, which include also the lists of
        # nearest upper and lower Places as place[i].upper[] and place[i].lower[]
        locations = Place_combo.get_place_hierarchy()
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
#     for p in locations:
#         print ("# {} ".format(p))
    return render_template("/scene/places.html", locations=locations, 
                           elapsed=time.time()-t0)


@bp.route('/scene/location/uuid=<locid>')
@bp.route('/scene/location=<int:locid>')
def show_place_page(locid):
    """ Home page for a Place, shows events and place hierarchy
        locid = id(Place)
    """
    try:
        # List 'place_list' has Place objects with 'parent' field pointing to
        # upper place in hierarcy. Events
        place, place_list, events = get_place_with_events(locid)
    except KeyError as e:
        import traceback
        traceback.print_exc()
        return redirect(url_for('virhesivu', code=1, text=str(e)))
#     for p in place_list:
#         print ("# {} ".format(p))
#     for u in place.notes:
#         print ("# {} ".format(u))
    return render_template("/scene/place_events.html", locid=locid, place=place, 
                           events=events, locations=place_list)

# ------------------------------ Menu 5: Sources --------------------------------

@bp.route('/scene/sources')
def show_sources():
    """ Lähdeluettelon näyttäminen ruudulla for menu(5)
    """
    try:
        sources = Source.get_source_list()
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
    return render_template("/scene/sources.html", sources=sources)


@bp.route('/scene/source=<int:sourceid>')
def show_source_page(sourceid):
    """ Home page for a Source with referring Event and Person data
    """
    try:
        source, citations = get_source_with_events(sourceid)
    except KeyError as e:
        return redirect(url_for('virhesivu', code=1, text=str(e)))
    return render_template("/scene/source_events.html",
                           source=source, citations=citations)

@bp.route('/scene/media/<fname>')
def fetch_media(fname):
    """ Fetch media file, assumes jpg, fix later...
    """
    uuid = request.args.get("id")
    fullname, mimetype = media.get_fullname(uuid)
    return send_file(fullname, mimetype=mimetype)        

@bp.route('/scene/thumbnail')
def fetch_thumbnail():
    """ Fetch thumbnail
    """
    uuid = request.args.get("id")
    thumbname = media.get_thumbname(uuid)
    print(thumbname)
    mimetype='image/jpg'
    return send_file(thumbname, mimetype=mimetype)


