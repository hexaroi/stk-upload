# Flask routes program for Stk application stat blueprint
#
# Juha Takala 08.05.2020 19:11:31

import logging
logger = logging.getLogger('stkserver')
import time
import re
import os

from flask import flash, render_template, request
from flask_security import roles_accepted, login_required
# from flask_babelex import _

# from ui.user_context import UserContext

import shareds

from . import bp
from .models import logreader

################ helper fuctions ################

################
#
def run_cmd(cmd):
    import subprocess
    # see https://docs.python.org/3.3/library/subprocess.html
    proc = subprocess.Popen(cmd, shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
    )
    (stdout, stderr) = proc.communicate()
    if stderr:
        print(f"{cmd}: {stderr}")
    output = stdout.decode("utf-8") # bytes to string
    lines = [x.rstrip() for x in output.split("\n")]
    return (lines)

################
#
def get_logfiles(log_root, log_file, patterns=""):
    """Get ist of log files matching PATTERNS.

Empty PATTERNS equals LOG_FILES.  Return matching filenames in LOG_ROOT."""
    import glob
    if patterns == "":
        patterns = f"{log_file}*"
    files = []
    for pat in re.split(" ", patterns):
        files += list(filter(os.path.isfile, glob.glob(f"{log_root}/{pat}")))
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return files

################
#
def safe_get_request(what, default):
    res = request.args.get(what, default)
    if res == "":
        return default
    try:
        return int(res)
    except ValueError as e:
        flash(f"Bad number for {what} '{res}': {e}; using default {default}",
              category='warning')
        return default

################
#
def check_regexp_option(what, default=""):
    val = request.args.get(what, default)
    if val == "":
        return ""
    try:
        re.compile( re.sub("[, ]+", "|", val) )
        return "," . join(re.split("[, ]+", val))
    except Exception as e:
        flash(f"Bad regexp for {what} '{val}': {e}",
              category='warning')
    return ""


################################################################
#### @route funtions below

################################################################
#
@bp.route('/stat')
@login_required
@roles_accepted('admin')
def stat_home():
    """Statistics from stk server.
    """
    code_root = shareds.app.config['APP_ROOT']

    def count_files_lines(fpat, lpat=None):
        """Count files matching file pattern FPAT, and lines in them.

        If optional line pattern LPAT given, count only matching lines.
        """
        grep = ""
        if lpat is not None:
            grep = f" | grep '{lpat}'"
        files = run_cmd(f"find {code_root} -name '{fpat}'")
        lines = run_cmd(f"cat {' '.join(files)}{grep} | wc -l")
        return (len(files), int(lines[0]))

    t0 = time.time()
    (code_files, code_lines) = count_files_lines("*.py")
    (html_files, html_lines) = count_files_lines("*.html")
    (route_files, route_lines) = count_files_lines("routes.py", lpat=r"^@.*route")
    commits = run_cmd("git log | grep commit | wc -l")
    commits1m = run_cmd(f"git log --after '1 month ago' | grep commit | wc -l")
    elapsed = time.time() - t0
    logger.info(f"-> bp.stat e={elapsed:.4f}")
    return render_template("/stat/stat.html",
                           code_files = code_files,
                           code_lines = code_lines,
                           html_files = html_files,
                           html_lines = html_lines,
                           route_files = route_files,
                           route_lines = route_lines,
                           commits = int(commits[0]),
                           commits1m = int(commits1m[0]),
                           elapsed = elapsed,
    )

################################################################
#
@bp.route('/stat/appstat', methods = ['GET', 'POST'])
@login_required
@roles_accepted('admin')
def stat_app():
    """Statistics about stk application usage.
    """

    t0 = time.time()
    msg     = check_regexp_option("msg")
    users   = check_regexp_option("users")
    maxlev  = safe_get_request("maxlev", 2)
    topn    = safe_get_request("topn", 42)
    bycount = request.args.get("bycount", None)
    cumul   = request.args.get("cumul", None)
    logs    = request.args.get("logs", "")

    # opts from template, they go to logreader and back to template as
    # defaults values
    opts = {
        "topn"   : topn,
        "msg"    : msg,
        "users"  : users,
        "maxlev" : maxlev,
        "logs"   : logs,        # used before logreader to filter logfiles
        "bycount": bycount,
        "cumul"  : cumul,
    }
    # print(f"{opts}")
    logdir = shareds.app.config['STK_LOGDIR']
    logfiles = get_logfiles(logdir,
                            shareds.app.config['STK_LOGFILE'],
                            patterns = logs)
    # res [] will collect results from all logreader invocations, one set
    # from each call
    res = []
    for f in logfiles:
        # Create a logreader for each logfile
        #  that can do "By_msg" and "By_date" and "By_user" statistics
        logrdr = logreader.StkServerlog(
            "Top_level",
            by_what = [("By_msg",  logreader.StkServerlog.save_bymsg),
                       ("By_date", logreader.StkServerlog.save_bydate),
                       ("By_user", logreader.StkServerlog.save_byuser),
            ],
            opts    = opts, )
        logrdr.work_with(f)
        res.append(logrdr.get_report()) # that will be one filesection

    elapsed = time.time() - t0
    logger.info(f"-> bp.stat.app e={elapsed:.4f}")
    return render_template("/stat/appstat.html",
                           res     = res,
                           opts    = opts,
                           elapsed = elapsed )


# ################################################################
# #
# @bp.route('/stat/uploadstat', methods = ['GET', 'POST'])
# @login_required
# @roles_accepted('admin')
# def stat_upload():
#     """Statistics about material uploading.
#     """

#     t0 = time.time()

#     users   = check_regexp_option("users")
#     msg     = check_regexp_option("msg")     # ...took the place of width in UI
#     # width   = safe_get_request("width", 70) # no way to set this in UI...
#     topn    = safe_get_request("topn", 42)
#     bycount = request.args.get("bycount", None)
#     style   = request.args.get("style", "text")
#     logs    = request.args.get("logs", "")

#     opts = {
#         "topn"   : topn,
#         # "width"  : width,
#         "style"  : style,
#     }
#     # Absense/precense of these in opts matters:
#     if bycount is not None: opts["bycount"] = 1
#     for k,v in { "msg"  : msg,
#                  "users": users }.items():
#         if v != "":
#             opts[k] = v

#     lines = []
#     log = logreader.StkUploadlog(opts)
#     logdir = "/home/juha/projs/Taapeli/stk-upload/uploads/*"
#     for f in get_logfiles(logdir, "*.log", logs):
#         log.work_with(f)
#     lines.append(log.get_counts(style=style))

#     elapsed = time.time() - t0
#     logger.info(f"-> bp.stat.app e={elapsed:.4f}")
#     return render_template("/stat/uploadstat.html",
#                            topn    = topn,
#                            # width   = width,
#                            bycount = bycount,
#                            logdir  = logdir,
#                            logs    = logs,
#                            style   = style,
#                            users   = users,
#                            msg     = msg,
#                            lines   = lines,
#                            elapsed = elapsed )
