from __future__ import annotations

from canvas_data import CourseData
from cli_config import CronyConfiguration
from reports.progress_reports import make_progress_reports
from reports.report_types import ReportSet
from reports.ungraded_reports import make_ungraded_reports
from reports.score_reports import make_score_reports


def make_reports(course: CourseData, args: CronyConfiguration) -> ReportSet:
    reports = ReportSet(course, args)
    reports.extend(make_progress_reports(course, args))
    reports.extend(make_ungraded_reports(course, args))
    reports.extend(make_score_reports(course, args))
    return reports
