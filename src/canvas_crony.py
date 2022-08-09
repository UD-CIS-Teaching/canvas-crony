"""
The information sent out is:
* List of ungraded assignments with links
* Summary data of where students are
* Summary data of where TAs are with their grading

Reports are generated for the following audiences:
* Students: only their own information
* staff: all the students under their purview, and their own information
* instructor: all the students, and all the staff under their purview

Maybe something roles-based?
* Learner gets information about completion
* Grader gets data about ungraded stuff by Learners
* Tracker gets information about Learner's progress
* Manager gets information about Graders progress

And then a given Grader can have a group of Learners, a Manager can have a group of Graders, etc.
The actual mapping should be able to come from a few different places.

At the top level, we AT LEAST need a file(s) with a Canvas course ID.
Probably a file with all the needed course data? Probably a yaml?
Then there could be a CLI mode where it just runs it for all loaded courses that are not disabled.

We also need a secrets file to hold the connection data. Should be able to specify that from the command line too.
"""
from email_service import send_emails
from cli_config import CronyConfiguration
from canvas_data import load_course_data, load_course_folder
from canvas import CanvasApi
from reports import make_reports


def canvas_crony(args: CronyConfiguration):
    canvas = CanvasApi(args['settings'], args['cache'])
    if args['course'] is not None:
        courses = [load_course_data(args['course'])]
    elif args['courses'] is not None:
        courses = load_course_folder(args['courses'])
    else:
        raise ValueError("Need to have either `courses` or `course` provided")
    courses = [canvas.rehydrate_course(course) for course in courses]
    report_sets = [make_reports(course, args) for course in courses]
    if args['email']:
        only_emails = args['only'].split(',') if args['only'] else []
        send_emails(report_sets, only_emails)
    if args['output']:
        for report_set in report_sets:
            report_set.output()
    return report_sets
