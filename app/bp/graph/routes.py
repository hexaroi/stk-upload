# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2001-2007  Donald N. Allingham, Martin Hawlisch
# Copyright (C) 2009 Douglas S. Blank
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

## Based on the paper:
##   http://www.cs.utah.edu/~draperg/research/fanchart/draperg_FHT08.pdf
## and the applet:
##   http://www.cs.utah.edu/~draperg/research/fanchart/demo/

## Found by redwood:
## http://www.gramps-project.org/bugs/view.php?id=2611

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
import urllib

from flask import render_template, request, redirect, url_for, flash, session as user_session #, send_from_directory, session, jsonify
from flask import send_file, json
from flask_security import login_required, roles_accepted, current_user
from flask_babelex import _ 

import shareds
import bl.person

from . import bp
## from .models import logreader, utils

## from gramps.gen.plug import Gramplet
from ui.user_context import UserContext
from pe.neo4j.readservice_tx import Neo4jReadServiceTx
from bl.person_reader import PersonReaderTx
from bl.base import Status
from bl.person_name import Name
from bp.gedcom.transforms.model.person_name import PersonName
## from gramps.gen.const import GRAMPS_LOCALE as glocale
## _ = glocale.translation.gettext

MAX_ANCESTOR_LEVELS = 4
MAX_DESCENDANT_LEVELS = 3

readservice = Neo4jReadServiceTx(shareds.driver)

def get_fanchart_data(uuid):
    '''
    Fetch data from the ancestors and descendants of the giving uuid, creating a data
    structure that can be fed to the sunburst chart Javascript component for creating
    a simple two-way fanchart.
    '''
    def gender_color(sex, descendant):
        """
        Given the gender code according to ISO 5218, returns a color for fanchart.
        """
        ancestor_colors = {
            0: 'lightgrey',         # ISO 5218: 0 = Not known
            1: 'lightsteelblue',    # ISO 5218: 1 = Male
            2: 'thistle',           # ISO 5218: 2 = Female
            9: 'lightyellow'        # ISO 5218: 9 = Not applicable
        }
        descendant_colors = {
            0: 'lightgrey',         # ISO 5218: 0 = Not known
            1: 'lightskyblue',      # ISO 5218: 1 = Male
            2: 'lightpink',         # ISO 5218: 2 = Female
            9: 'lightyellow'        # ISO 5218: 9 = Not applicable
        }
        if descendant:
            return descendant_colors.get(sex, 'white') # white if value is not in ISO 5218
        else:
            return ancestor_colors.get(sex, 'white') # white if value is not in ISO 5218

    def get_person_for_id(uuid):
        """
        Database read access. Error handling needs an improvement here!
        """
        result = reader.get_person_data(uuid)
        if Status.has_failed(result):
            flash(f'{result.get("statustext","error")}', 'error')
        return result.get('person')

    def fanchart_from(person, size, descendant):
        """
        Format the data for fan/sunburst chart use.
        """
        all_first_names = person.names[0].firstname.split()
        one_first_name = all_first_names[0] if len(all_first_names) > 0 else ''
        all_surnames = person.names[0].surname.split()
        one_surname = all_surnames[0] if len(all_surnames) > 0 else ''
        
        if person.death_high - person.birth_low >= 110: ## TEMP: FIND OUT HOW TO GET THE YEARS!
            death = ''
        else:
            death = f'{person.death_high}'
        return {
            'name': one_first_name +
                    (f' {one_surname}' if size > 0.2 else '') +
                    (f' {person.birth_low}' if size > 0.4 else ''),
            'color': gender_color(person.sex, descendant),
            'tooltipContent': f'{person.names[0].firstname} {person.names[0].surname}' +
                f' {person.birth_low}-{death}',
            'uuid': person.uuid
        }

    def build_parents(uuid, size, level = 1):
        """
        Recurse to ancestors, building a data structure for fanchart.
        """
        # Fill in basic data from current person
        person = get_person_for_id(uuid)
        node = fanchart_from(person, size, descendant = False)

        if person.families_as_child and level < MAX_ANCESTOR_LEVELS:  # continue recursion?

            dad = person.families_as_child[0].father
            if dad:
                dads = build_parents(dad.uuid, size/2, level + 1)
            else:
                dads = {'color': 'white', 'size': size/2}

            mom = person.families_as_child[0].mother
            if mom:
                moms = build_parents(mom.uuid, size/2, level + 1)
            else:
                moms = {'color': 'white', 'size': size/2}
            node['children'] = [dads, moms]

        else:
            node['size'] = size     # leaf node, others should have no size
            
        return node
    
    def build_children(uuid, size, level = 1):
        """
        Recurse to descendants, building a data structure for fanchart.
        """
        # Fill in basic data from current person
        person = get_person_for_id(uuid)
        node = fanchart_from(person, size, descendant = True)

        if person.families_as_parent and level < MAX_DESCENDANT_LEVELS:  # continue recursion?

            child_count = 0
            for fx in person.families_as_parent:
                child_count += len(fx.children)

            if child_count == 0:
                node['size'] = size     # leaf node, others should have no size
            else:
                node['children'] = []
                person.families_as_parent.sort(reverse = True,
                                               key = lambda x: x.dates.date1.value())
                for fx in person.families_as_parent:
                    fx.children.sort(reverse = True, key = lambda x: x.birth_low)
                    for cx in fx.children:
                        node['children'].append(
                            build_children(cx.uuid, size/child_count, level + 1))

        else:
            node['size'] = size     # leaf node, others should have no size

        return node
    
    # Set up the database access.
    u_context = UserContext(user_session, current_user, request)
    reader = PersonReaderTx(readservice, u_context)

    # Gather all required data in two directions from the central person. Data structure used in both is a
    # recursive dictionary with unlimited children, for the Javascript sunburst chart by Vasco Asturiano
    # (https://vasturiano.github.io/sunburst-chart/)
    ancestors = build_parents(uuid, 1)
    descendants = build_children(uuid, 1)
    
    # Merge the two sunburst chart data trees to form a single two-way fan chart.
    fanchart = ancestors
    if 'children' in descendants.keys():
        if 'children' in ancestors.keys():
            fanchart['children'] = ancestors['children'] + descendants['children']
        else:
            fanchart['children'] = descendants['children']
##            fanchart['children'].insert(1, {'size': 0.5, 'color': 'white'}) # If no ancestors, make empty NE quarter
    else:
        fanchart['children'].insert(2, {'size': 1, 'color': 'white'}) # If no descendants, make empty southern hemisphere
    
    # The sectors are drawn clockwise, starting from North. To get the ancestors to occupy the
    # Northern hemisphere, we need to move the first node on top level list (father) to end of list.
    if 'children' in fanchart.keys():
        fanchart['children'].append(fanchart['children'].pop(0))
    
    return fanchart
    

@bp.route('/graph', methods=['GET'])
@login_required
@roles_accepted('audit')
def graph_home(uuid=None):
    uuid = request.args.get('uuid', None)
    fanchart = get_fanchart_data(uuid)
    return render_template('/graph/layout.html', fanchart_data=json.dumps(fanchart))
