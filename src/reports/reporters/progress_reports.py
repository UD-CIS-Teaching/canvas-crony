from __future__ import annotations

from canvas_data import CourseData
from cli_config import CronyConfiguration
from reports.report_types import Report


def make_progress_reports(course: CourseData, args: CronyConfiguration) -> list[Report]:
    reports = []
    staff_reports = {}
    instructor_reports = {}
    student_reports = {}
    for student in course['students']:
        pass
    return reports


