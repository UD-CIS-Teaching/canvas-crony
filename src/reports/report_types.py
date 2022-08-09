import os

from fpdf import FPDF

from canvas_data import CourseData, User
from cli_config import CronyConfiguration


class Report:
    def __init__(self, name: str, target: User, pdf: FPDF, course: CourseData, args: CronyConfiguration):
        self.course = course
        self.args = args
        self.pdf = pdf
        self.name = name
        self.target = target
        self.path = None

    def output(self):
        course_id = self.course['course']['id']
        filename = f"{self.name}_{course_id}_{self.target['id']}.pdf"
        path = os.path.join(self.args['output'], filename)
        self.pdf.output(path)

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
