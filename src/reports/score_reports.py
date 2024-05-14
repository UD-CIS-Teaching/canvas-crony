from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args
import math

from fpdf import FPDF

from canvas_data import CourseData, User, GradingStatus, Submission, Group, NOT_CRITICAL
from canvas_request import days_between, past_date
from cli_config import CronyConfiguration
from reports.course_helpers import (
    get_staff_for_student,
    classify_submission,
    check_recency,
    days_old,
    make_grading_piles,
)
from reports.report_tools import make_table
from reports.report_types import Report


RECENTLY_THRESHOLD = 3  # days
ANCIENT_THRESHOLD = 7  # days


def make_score_reports(course: CourseData, args: CronyConfiguration) -> list[Report]:
    reports = []

    # Get each TA mapped to their list of students
    staff_for_student = get_staff_for_student(course)

    # Process each submission, add it to our piles if ungraded
    grader_piles: dict[int, list[Submission]] = {}
    all_graded: list[Submission] = []
    for submission in course["submissions"].values():
        grader = submission["grader"]
        # Only deal with graded
        if submission["workflow_state"] != "graded":
            continue
        # Machine graded
        if grader and isinstance(grader, int):
            continue

        if grader["id"] not in grader_piles:
            grader_piles[grader["id"]] = []
        grader_piles[grader["id"]].append(submission)
        all_graded.append(submission)

    # Make a PDF for each TA
    staff_reports, staff_tables = make_score_reports_staff(
        course, grader_piles, len(all_graded), args
    )
    # Make a PDF for the instructor
    instructor_reports = make_score_reports_instructor(
        course, all_graded, staff_tables, args
    )

    reports.extend(staff_reports)
    reports.extend(instructor_reports)
    return reports


def iqr(scores):
    scores = sorted(scores)
    n = len(scores)
    q1 = scores[math.ceil(n * 0.25)]
    median = scores[math.ceil(n * 0.5)]
    q3 = scores[math.ceil(n * 0.75)]
    # return [str(scores[0]), str(q1), str(median), str(q3), str(scores[-1])]
    return [
        f"{scores[0]:.2f}",
        f"{q1:.2f}",
        f"{median:.2f}",
        f"{q3:.2f}",
        f"{scores[-1]:.2f}",
    ]


def get_normal_stats(scores):
    mean = sum(scores) / len(scores)
    variance = sum((x - mean) ** 2 for x in scores) / len(scores)
    std_dev = math.sqrt(variance)
    return [f"{mean:.2f}", f"{variance:.2f}", f"{std_dev:.2f}"]


@dataclass
class StaffTables:
    extents: list[list[str]]
    iqr: list[list[str]]
    normal_stats: list[list[str]]


def make_score_reports_staff(
    course: CourseData,
    grader_piles: dict[int, list[Submission]],
    total_graded: int,
    args: CronyConfiguration,
):
    staff_reports = []
    staff_tables = {}
    for ta_id, graded in grader_piles.items():
        ta = course["users"][ta_id]
        # PDF
        staff_pdf = FPDF()
        staff_pdf.add_page()
        # Page Header
        staff_pdf.set_font("helvetica", "B", size=22)
        staff_pdf.write(txt=f"Staff Score Report\n")
        staff_pdf.set_font("helvetica", size=18)
        staff_pdf.write(txt=course["course"]["name"] + "\n")
        staff_pdf.write(txt=ta["name"] + "\n")
        staff_pdf.ln()
        # Summarize data
        staff_pdf.set_font("helvetica", size=14)

        # Extents (Zeros and Perfects)

        zeroes = [sub for sub in graded if sub["score"] == 0]
        perfects = [
            sub
            for sub in graded
            if sub["score"] == sub["assignment"]["points_possible"]
        ]
        extents_table = [
            ["", "Number", "Percent"],
            [
                "Graded Submissions",
                str(len(graded)),
                f"{len(graded)/total_graded:.2%} (of {total_graded} total)",
            ],
            [
                "Zeroes",
                str(len(zeroes)),
                f"{len(zeroes)/len(graded):.2%} (of {len(graded)})",
            ],
            [
                "Perfects",
                str(len(perfects)),
                f"{len(perfects)/len(graded):.2%} (of {len(graded)})",
            ],
        ]
        make_table(staff_pdf, extents_table)

        all_scores = [
            (
                100 * sub["score"] / sub["assignment"].get("points_possible", 0)
                if sub["assignment"]["points_possible"] and sub["score"]
                else sub["score"] or 0
            )
            for sub in graded
        ]
        nonzero_scores = [
            (sub["score"] / sub["assignment"]["points_possible"])
            for sub in graded
            if sub["score"] and sub["assignment"]["points_possible"]
        ]

        # IQR (with and without zeroes)
        staff_pdf.ln()
        iqr_table = [
            ["", "Min", "25%", "Median", "75%", "Max"],
            ["All Scores", *iqr(all_scores)],
            ["Non-Zero Scores", *iqr(nonzero_scores)],
        ]
        make_table(staff_pdf, iqr_table)

        # Mean, Variance, Std Dev
        staff_pdf.ln()
        normal_stats = [
            ["", "Mean", "Variance", "Std Dev"],
            ["All Scores", *get_normal_stats(all_scores)],
            ["Non-Zero Scores", *get_normal_stats(nonzero_scores)],
        ]
        make_table(staff_pdf, normal_stats)

        staff_tables[ta_id] = StaffTables(extents_table, iqr_table, normal_stats)

        # Grade distribution histogram
        # TODO: Make the histogram and embed it
        # Wrap it up
        staff_reports.append(
            Report(
                "score",
                "{course_name} Score Report for {user_name}",
                ta,
                staff_pdf,
                course,
                args,
            )
        )
    return staff_reports, staff_tables


def make_score_reports_instructor(
    course: CourseData,
    all_graded: list[Submission],
    staff_tables: dict[int, StaffTables],
    args: CronyConfiguration,
):
    instructor_reports = []
    for instructor in course["instructors"]:
        instructor_pdf = FPDF()
        instructor_pdf.add_page()
        # Page Header
        instructor_pdf.set_font("helvetica", "B", size=22)
        instructor_pdf.write(txt=f"Instructor Score Report\n")
        instructor_pdf.set_font("helvetica", size=18)
        instructor_pdf.write(txt=course["course"]["name"] + "\n")
        instructor_pdf.write(txt=instructor["name"] + "\n")
        instructor_pdf.ln()
        # Overall summary
        instructor_pdf.set_font("helvetica", size=12)
        #   TA Sts
        instructor_pdf.write(txt=f"Staff: {len(staff_tables)}\n")
        instructor_pdf.write(txt=f"Groups: {len(course['groups'])}\n")
        instructor_pdf.write(txt=f"Students: {len(course['students'])}\n")
        instructor_pdf.write(txt=f"Assignments: {len(course['assignments'])}\n")
        expected_submissions = len(course["students"]) * len(course["assignments"])
        instructor_pdf.write(
            txt=f"Submissions: {len(course['submissions'])} ({expected_submissions} possible)\n"
        )
        instructor_pdf.write(
            txt=f"Graded: {len(all_graded)} ({len(all_graded)/expected_submissions:.2%})\n"
        )
        instructor_pdf.ln()

        # List out the TA's progress
        for stat_name, stat_field in [
            ("Extents", "extents"),
            ("IQR of Percentage Scores", "iqr"),
            ("Normal Stats of Percentage Scores", "normal_stats"),
        ]:
            instructor_pdf.write(txt=stat_name + ":\n")
            for ta_id, graded in staff_tables.items():
                ta = course["users"][ta_id]
                stat_table = getattr(staff_tables[ta_id], stat_field)
                stat_table[0][0] = ta["name"]
                make_table(instructor_pdf, stat_table)
                instructor_pdf.ln()

        # Wrap it up
        instructor_reports.append(
            Report(
                "score",
                "{course_name} Instructor Score Report for {user_name}",
                instructor,
                instructor_pdf,
                course,
                args,
            )
        )
    return instructor_reports
