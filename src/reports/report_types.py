from __future__ import annotations
import os

from fpdf import FPDF

from canvas_data import CourseData, User
from cli_config import CronyConfiguration
from filesystem import clean_filename


class Report:
    def __init__(self, name: str, subject: str, target: User, pdf: FPDF, course: CourseData, args: CronyConfiguration):
        self.course = course
        self.args = args
        self.pdf = pdf
        self.name = name
        self.target = target
        self.subject = subject
        self.path = None
        self.filename = None

    def output(self):
        course_id = self.course['course']['id']
        name = clean_filename(self.target['name'])
        self.filename = f"{self.name}_{course_id}_{name}.pdf"
        self.path = os.path.join(self.args['output'], self.filename)
        self.pdf.output(self.path)


class ReportSet:
    def __init__(self, course: CourseData, args: CronyConfiguration):
        self.course = course
        self.args = args
        self.reports = []

    def extend(self, reports: list[Report]):
        self.reports.extend(reports)

    def output(self):
        # consolidate targets across reports?
        for report in self.reports:
            report.output()
