#
# Class for reading stk server logs
#

import re
import os

from flask import flash

################################################################
#
# Format of log messages (see app/__init__.py)
# '%(asctime)s %(name)s %(levelname)s %(user)s %(message)s'
#
ymd_re = r'\d\d\d\d-\d\d-\d\d'
hms_re = r'\d\d:\d\d:\d\d,\d\d\d'

# This shall match each line in log file
log_re = re.compile(f'({ymd_re}) ({hms_re})'
                    f' (\S+) (\S+) (\S+) (.*)')

# We are interested only about entries where %(message)s part looks like this:
arrow_re = re.compile(r"^-> ([^ ]+)(.*)")

# Additional info in %(message)s part look like this:
equals_re = re.compile(r"\b(\S+)=(\S+)\b")

def find_longest(list_of_tuples, what):
    longest = 0
    for tup in list_of_tuples:
        if what == "msg":
            if len(tup[0]) > longest:
                longest = len(tup[0])
            continue
        for u in tup[1].keys():
            if len(u) > longest:
                longest = len(u)
    return longest

def make_filler(totlen, flen):
    return(" "*(totlen % flen)
           + (" "*(flen-1) + ".") * (totlen // flen))


################################################################
#
class Log():
    """Class to handle stk log file(s)."""

    def __init__(self, opts={}):
        self._opts = opts
        self._by_msg = dict()
        self._by_ymd = dict()
        self._files = []        # lis of files already processed


    ################
    #
    def work_with(self, file: str) -> None:
        """Read stkserver log FILE.  Collect counts of messages."""

        """
Toistaiseksi olisi 2 mittaria: modulin nimi=käydyt sivut ja n=käsitellyt
rivit tms.  Raportointia voisi rakentaa käyttäjien käyntimääristä
kuukausittain (käyttäjittäin monenako päivänä, montako eri käyttäjää) ja
suosituimmat sivut ja niiden datavolyymit.

Kuukausittaiset määrät tulee helposti siitä, kun lokit on kuukauden lokeja.

        """

        def update_counters(self, msg, user, ymd, tuples):
            """Update counters for MSG, USER"""

            def update_one(outer, key):
                """Update (or create) the dict OUTER[KEY]"""
                if key not in outer:
                    outer[key] = dict()
                # the inner dict is keyed by USER (found from callers namespace)
                inner = outer[key]
                if user in inner:  inner[user] += 1
                else:              inner[user] = 1

                return

            update_one(self._by_msg, msg)
            update_one(self._by_ymd, ymd)

            # what to do with these?
            for tup in tuples:
                print(f"got {module} {user} {tup[0]}={tup[1]}")
                continue
            return

        if file in self._files:
            flash(f"Already done file {file}") # this should not happen
            return
        self._files.append(file)  # protect against double processing

        users_re = None
        if "users" in self._opts:
            try:
                users_re = re.compile( re.sub(",", "|", self._opts["users"]) )
            except Exception as e:
                flash(f"Bad regexp '{self._opts['users']}': {e}", category='warning')

        for line in open(file, "r").read().splitlines():
            match = log_re.match(line)
            if not match:
                flash(f"strange log line {line}") # this should not happen
                continue
            (ymd, hms, logger, level, user, message) = match.groups()
            if level != 'INFO':
                continue

            if users_re and not users_re.match(user):
                continue

            match = arrow_re.match(message)
            if not match:
                continue

            (module, rest) = match.groups()
            tuples = equals_re.findall(rest)

            update_counters(self, module, user, ymd, tuples)
        return

    ################
    #
    def get_counts(self, style="text"):
        """Get the counts of this Log, maybe per user.

Return value is list of nested tuples: (heading, data-tuple).
        """
        def get_section_counts(outer, heading):
            """Get counts of one section.

Return value is a tuple (HEADING, data-list).
            """
            def get_topn(tuples):
                # use the negative number trick to get numeric sorting
                # reverse & alpa non-reverse (we can't use reverse=True
                # because that woud reverse the alpha sorting too)
                if "bycount" in self._opts:
                    result = sorted(tuples.items(),
                                    key=lambda x:
                                    (-x[1] if type(x[1]) == int else -x[1]["TOTAL"],
                                     x[0]))
                else:
                    result = sorted(tuples.items())
                if "topn" in self._opts:
                    result = result[:self._opts["topn"]]
                return result

            # make the total counts
            for x in outer.values():
                sum = 0
                for count in x.values():
                    sum += count
                x["TOTAL"] = sum

            countx = get_topn(outer)
            len_user = find_longest(countx, "user")
            len_msg = find_longest(countx, "msg")
            destcol = self._opts["width"] - len_user - 6  # room for count + some space
            if destcol > len_msg +10:  destcol = len_msg +10
            if destcol < 8:            destcol = 8
            # print(f"u={len_user} m={len_msg} d={destcol}")
            lines = []
            n = 0
            for message, ulist in countx:
                n += 1
                before = f"{n:2d} " if "topn" in self._opts else ""

                # Truncate too long messages
                if len(message) > destcol - 3 -len(before):
                    message = message[:destcol-3-len(before)] + "·"*3

                # The message and filler to make report look nicer
                part1 = f"{before}{message}"
                filler = make_filler(destcol - len(message) - len(before), 3)

                # add them and count stuff
                if "users" not in self._opts:   #  show not users' counts?
                    if style == "text":
                        lines.append(f"{part1} {filler}  {ulist['TOTAL']:4d}")
                    if style == "table":
                        lines.append([before, message, ulist["TOTAL"]])
                    continue

                # lines after first line are filled with spaces up to destcol
                for user, count in get_topn(ulist):
                    if user == "TOTAL" and len(ulist) < 3:
                        # We have just one user, so don't show the TOTAL
                        continue
                    if style == "text":
                        lines.append(f"{part1} {filler} {user:{len_user}s} {count:4d}")
                        filler = " " * destcol
                    if style == "table":
                        lines.append([before, message, user, count])
                        before = ""
                        message = ""
                    part1 = ""

            return(heading, lines)

        res = []
        res.append(get_section_counts(self._by_msg, "By msg:"))
        res.append(get_section_counts(self._by_ymd, "By date:"))
        files = [ x[x.rindex("/")+1:] for x in self._files ]

        return(", ".join(files), res)
