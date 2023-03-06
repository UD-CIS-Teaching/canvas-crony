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
from __future__ import annotations

import sys
from tqdm import tqdm
import logging
from logging.handlers import RotatingFileHandler

from email_service import send_emails
from cli_config import CronyConfiguration
from canvas_data import load_course_data, load_course_folder
from canvas import CanvasApi
from reports import make_reports
from reports.report_types import ReportSet
from settings import yaml_load

logger = logging.getLogger('crony')


class CanvasCrony:
    progress_bar: tqdm

    def __init__(self):
        self.progress_bar = None

    def init_logger(self, args: CronyConfiguration):
        if args['log']:
            logger.setLevel(logging.DEBUG)
            ch = RotatingFileHandler(filename=args['log'], encoding='utf-8', backupCount=5,
                                     maxBytes=1024**3)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
            logger.info("Starting Canvas Crony")

    def run_safely(self, args: CronyConfiguration) -> list[ReportSet]:
        self.init_logger(args)
        try:
            return self.run(args)
        except Exception as exception:
            logger.error(f"Error during execution: {exception}")


    def run(self, args: CronyConfiguration) -> list[ReportSet]:
        settings = yaml_load(args['settings'])
        self.start_progress_bar(args['progress'])
        logger.info("Downloading Course Data")
        canvas = CanvasApi(settings, args['cache'])
        if args['course'] is not None:
            courses = [load_course_data(args['course'])]
        elif args['courses'] is not None:
            courses = load_course_folder(args['courses'])
        else:
            logger.error("Need to have either `courses` or `course` provided")
            raise ValueError("Need to have either `courses` or `course` provided")
        self.update_progress()
        courses = [canvas.rehydrate_course(course) for course in courses]
        self.update_progress()
        logger.info("Building Reports")
        report_sets = [make_reports(course, args) for course in courses]
        self.update_progress()
        if args['output']:
            for report_set in report_sets:
                report_set.output()
        self.update_progress()
        if args['email']:
            logger.info("Sending emails")
            only_emails = args['only'].split(',') if args['only'] else []
            send_emails(report_sets, only_emails, settings)
        else:
            logger.info("Skipping emails")
        self.update_progress()
        logger.info("All done!")
        return report_sets

    def start_progress_bar(self, progress: bool):
        if progress:
            self.progress_bar = tqdm(total=5, desc="Cronying")

    def update_progress(self, amount=1):
        if self.progress_bar:
            self.progress_bar.update(amount)


def canvas_crony(args: CronyConfiguration) -> list[ReportSet]:
    crony = CanvasCrony()
    return crony.run_safely(args)
