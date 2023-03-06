from __future__ import annotations
from typing import Literal, get_args
import math

from fpdf import FPDF

from canvas_data import CourseData, User, GradingStatus, Submission, Group, NOT_CRITICAL
from canvas_request import days_between, past_date
from cli_config import CronyConfiguration
from reports.report_types import Report


RECENTLY_THRESHOLD = 3  # days
ANCIENT_THRESHOLD = 7  # days


def make_ungraded_reports(course: CourseData, args: CronyConfiguration) -> list[Report]:
    reports = []
    staff_reports = {}

    # Get each TA mapped to their list of students
    staff_for_student: dict[int, list[User]] = {}
    for group_name, staff in course['cohorts'].items():
        for ta in staff:
            students = course['group_memberships'][group_name]
            for student in students:
                if student['id'] not in staff_for_student:
                    staff_for_student[student['id']] = []
                staff_for_student[student['id']].append(ta)

    # Process each submission, add it to our piles if ungraded
    ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]] = {}
    big_pile: dict[GradingStatus, set[int]] = {g: set() for g in get_args(GradingStatus)}
    for submission in course['submissions'].values():
        assignment = submission['assignment']
        student = submission['user']
        staff = staff_for_student.get(student['id'], [])
        grader = submission['grader']

        # Already machine graded
        if grader and isinstance(grader, int) and submission['workflow_state'] == 'graded':
            continue

        for ta in staff:
            status = classify_submission(submission, course['group_membership_ids'])
            if ta['id'] not in ta_grading_piles:
                ta_grading_piles[ta['id']] = {g: [] for g in get_args(GradingStatus)}
            ta_grading_piles[ta['id']][status].append(submission)
            big_pile[status].add(submission['id'])

    # Make a PDF for each TA
    staff_reports = make_ungraded_reports_staff(course, big_pile, ta_grading_piles, args)
    # Make a PDF for the instructor
    instructor_reports = make_ungraded_reports_instructor(course, big_pile, ta_grading_piles, args)

    reports.extend(staff_reports)
    reports.extend(instructor_reports)
    return reports


def make_ungraded_reports_staff(course: CourseData, big_pile: dict[GradingStatus, set[int]],
                                ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]],
                                args: CronyConfiguration):
    staff_reports = []
    for ta_id, piles in ta_grading_piles.items():
        ta = course['users'][ta_id]
        # PDF
        staff_pdf = FPDF()
        staff_pdf.add_page()
        # Page Header
        staff_pdf.set_font('helvetica', "B", size=22)
        staff_pdf.write(txt=f"Staff Ungraded Report\n")
        staff_pdf.set_font('helvetica', size=18)
        staff_pdf.write(txt=course['course']['name']+"\n")
        staff_pdf.write(txt=ta['name']+"\n")
        staff_pdf.ln()
        # Summarize data
        staff_pdf.set_font('helvetica', size=14)
        table_data = [["", "Total", "Past 3 Days", "Past Week", "Older"]]
        for status, pile in piles.items():
            if pile:
                recent, ancient = check_recency(*pile)
                normal = len(pile) - recent - ancient
                table_data.append(
                    [status.title(), str(len(pile)), str(recent), str(normal), str(ancient)]
                )
                #staff_pdf.write(txt=f"{}: {len(pile)} total"
                #                    f" ({recent} within past 3 days, {normal} within last week, {ancient} older)\n")
        make_table(staff_pdf, table_data)
        staff_pdf.ln()
        # List all the actual links
        staff_pdf.set_font('helvetica', size=14)
        list_actual_links(staff_pdf, piles, course)
        """
        flat_pile = sorted([(days_old(submission), status, submission)
                            for status, pile in piles.items()
                            for submission in pile
                            if status not in NOT_CRITICAL],
                           key=lambda item: (-item[0], item[1]))
        previous_age = None
        if not flat_pile:
            staff_pdf.write(txt="You are all caught up on grading! Great work!")
        for age, status, submission in flat_pile:
            log_age = round(math.log2(age)) if age > 0 else 0
            if previous_age is None or log_age < previous_age:
                previous_age = log_age
                staff_pdf.set_font(size=18)
                staff_pdf.write(txt=f"{age} day{'s' if age > 1 else ''} ago:\n")
                staff_pdf.set_font(size=14)
            assignment = submission['assignment']
            url = course['speed_grader_url'].format(course_id=course['id'], assignment_id=assignment['id'],
                                                    user_id=submission['user']['id'])
            staff_pdf.write(txt="   ")
            staff_pdf.set_font(style="U")
            staff_pdf.write(txt=f"{assignment['name']}: {submission['user']['name']}", link=url)
            staff_pdf.set_font()
            staff_pdf.ln()
        """
        # Wrap it up
        staff_reports.append(Report("ungraded", "{course_name} Grading Report for {user_name}",
                                    ta, staff_pdf, course, args))
    return staff_reports


def list_actual_links(staff_pdf, piles, course: CourseData):
    flat_pile = sorted([(days_old(submission), status, submission)
                        for status, pile in piles.items()
                        for submission in pile
                        if status not in NOT_CRITICAL],
                       key=lambda item: (-item[0], item[1]))
    previous_age = None
    if not flat_pile:
        staff_pdf.write(txt="You are all caught up on grading! Great work!")
    for age, status, submission in flat_pile:
        log_age = round(math.log2(age)) if age > 0 else 0
        if previous_age is None or log_age < previous_age:
            previous_age = log_age
            staff_pdf.set_font(size=18)
            staff_pdf.write(txt=f"{age} day{'s' if age > 1 else ''} ago:\n")
            staff_pdf.set_font(size=14)
        assignment = submission['assignment']
        url = course['speed_grader_url'].format(course_id=course['id'], assignment_id=assignment['id'],
                                                user_id=submission['user']['id'])
        staff_pdf.write(txt="   ")
        staff_pdf.set_font(style="U")
        staff_pdf.write(txt=f"{assignment['name']}: {submission['user']['name']}", link=url)
        staff_pdf.set_font()
        staff_pdf.ln()


def make_table(pdf, data: list[list[str]]):
    line_height = pdf.font_size
    col_widths = [1.5 * pdf.epw / len(data[0])] + [pdf.epw / (1+len(data[0])) for c in data[0]]
    for row in data:
        for datum, col_width in zip(row, col_widths):
            pdf.multi_cell(col_width, line_height, datum, border=1,
                           new_x="RIGHT", new_y="TOP", max_line_height=pdf.font_size)
        pdf.ln(line_height)


def make_ungraded_reports_instructor(course: CourseData, big_pile: dict[GradingStatus, set[int]],
                                     ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]],
                                     args: CronyConfiguration):
    instructor_reports = []
    for instructor in course['instructors']:
        instructor_pdf = FPDF()
        instructor_pdf.add_page()
        # Page Header
        instructor_pdf.set_font('helvetica', "B", size=22)
        instructor_pdf.write(txt=f"Instructor Ungraded Report\n")
        instructor_pdf.set_font('helvetica', size=18)
        instructor_pdf.write(txt=course['course']['name']+"\n")
        instructor_pdf.write(txt=instructor['name'] + "\n")
        instructor_pdf.ln()
        # Overall summary
        instructor_pdf.set_font('helvetica', size=12)
        #   TA Sts
        instructor_pdf.write(txt=f"Staff: {len(ta_grading_piles)}\n")
        instructor_pdf.write(txt=f"Groups: {len(course['groups'])}\n")
        instructor_pdf.write(txt=f"Students: {len(course['students'])}\n")
        instructor_pdf.write(txt=f"Assignments: {len(course['assignments'])}\n")
        expected_submissions = len(course['students']) * len(course['assignments'])
        instructor_pdf.write(txt=f"Submissions: {len(course['submissions'])} ({expected_submissions} possible)\n")
        for status, pile in big_pile.items():
            if pile:
                instructor_pdf.write(txt=f"{status.title()}: {len(pile)}\n")
        instructor_pdf.ln()

        # List out the TA's progress
        for ta_id, piles in ta_grading_piles.items():
            ta = course['users'][ta_id]
            instructor_pdf.write(txt=ta['name'] + ":\n")
            table_data = [["", "Total", "Past 3 Days", "Past Week", "Older"]]
            for status, pile in piles.items():
                if pile:
                    recent, ancient = check_recency(*pile)
                    normal = len(pile) - recent - ancient
                    table_data.append(
                        [status.title(), str(len(pile)), str(recent), str(normal), str(ancient)]
                    )
                    #instructor_pdf.write(txt=f"  {status.title()}: {len(pile)} ({recent} recently, {ancient} more "
                    #                         f"than a week ago)\n")
            make_table(instructor_pdf, table_data)
            instructor_pdf.ln()

        instructor_pdf.set_font('helvetica', "B", size=22)
        instructor_pdf.write(txt="Individual Links:\n")
        for ta_id, piles in ta_grading_piles.items():
            ta = course['users'][ta_id]
            instructor_pdf.set_font('helvetica', "B", size=14)
            instructor_pdf.write(txt=ta['name'] + ":\n")
            instructor_pdf.set_font('helvetica', size=12)
            list_actual_links(instructor_pdf, piles, course)
            instructor_pdf.ln()
        # Wrap it up
        instructor_reports.append(Report("ungraded", "{course_name} Instructor Grading Report for {user_name}",
                                         instructor, instructor_pdf, course, args))
    return instructor_reports


def classify_submission(submission, groups: dict[int, set[int]]) -> GradingStatus:
    # Skip graded assignments
    if submission['workflow_state'] == 'graded':
        return 'graded'
    # Check attempt status
    attempted = (submission['attempt'] and submission['attempt'] > 1) or submission['grade']
    # Submitted late
    if submission['late']:
        if attempted:
            return 'resubmitted (late)'
        else:
            return 'not yet graded (late)'
    # Not yet submitted
    elif submission['missing'] or not submission['submitted_at']:
        availability = classify_availability(submission, groups)
        if availability == 'locked':
            return 'missed lock date'
        elif availability == 'past due':
            return 'missed due date'
        elif availability == 'open':
            return 'in progress'
        return 'future assignments'
    # Submitted on time, not yet graded
    elif submission['submitted_at']:
        availability = classify_availability(submission, groups)
        if availability == 'locked':
            if attempted:
                return 'resubmitted (ready)'
            else:
                return 'not yet graded (ready)'
        else:
            if attempted:
                return 'resubmitted (early)'
            else:
                return 'not yet graded (early)'
    return 'unknown'


def check_recency(*submissions: Submission) -> tuple[int, int]:
    recent, ancient = 0, 0
    for submission in submissions:
        if not submission['submitted_at']:
            continue
        grade_delay = days_old(submission)
        if grade_delay > ANCIENT_THRESHOLD:
            ancient += 1
        elif grade_delay < RECENTLY_THRESHOLD:
            recent += 1
    return recent, ancient


def days_old(submission: Submission) -> int:
    if not submission['submitted_at']:
        return 0
    return days_between(submission['submitted_at'], submission['graded_at'])


def classify_availability(submission: Submission, groups: dict[int, set[int]]) -> str:
    assignment = submission['assignment']
    if assignment['overrides']:
        submitter_id = submission['user']['id']
        sections = {enrolled['course_section_id'] for enrolled in submission['user']['enrollments']}
        # First check for per-student overrides
        for override in assignment['overrides']:
            if 'student_ids' in override:
                if submitter_id in override['student_ids']:
                    return check_availability(override)
        # Next separately check for any group overrides
        for override in assignment['overrides']:
            if 'group_id' in override:
                if override['group_id'] in groups:
                    if submitter_id in groups[override['group_id']]:
                        return check_availability(override)
        # Then separately check for any course section overrides
        for override in assignment['overrides']:
            if 'course_section_id' in override:
                if override['course_section_id'] in sections:
                    return check_availability(override)
    # Finally fall back on assignment's settings
    return check_availability(assignment)


def check_availability(availability):
    if availability['lock_at'] and past_date(availability['lock_at']):
        return 'locked'
    if availability['due_at'] and past_date(availability['due_at']):
        return 'past due'
    if availability['unlock_at'] and past_date(availability['unlock_at']):
        return 'open'
    return 'future'
