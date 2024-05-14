from __future__ import annotations

from typing import Optional

from canvas_data import clean_user, RawCourseData, CourseData, Submission, Assignment
from canvas_request import CanvasRequest
from settings import Settings


class CanvasApi(CanvasRequest):
    def __init__(self, settings: Settings, cache: bool):
        self.settings = settings
        super().__init__(self.settings, cache)

    def rehydrate_course(self, raw_course_data: RawCourseData) -> CourseData:
        cloned = raw_course_data.copy()
        course_id = cloned['id']
        # Actual course data
        cloned['course'], = self.get('', course=course_id, result_type=dict)
        # User lookup data
        users = self.get('users', all=True, course=course_id, data={
            'enrollment_state[]': ['active', 'invited', 'rejected', 'completed', 'inactive'],
            'include[]': ['enrollments']
        })
        users = [u for u in [clean_user(u) for u in users] if u]
        user_by_email = {u['email']: u for u in users}
        cloned['users'] = user_by_id = {u['id']: u for u in users}
        # Students
        cloned['students'] = {u['id']: u for u in users
                              for e in u['enrollments'] if e['type'] == 'StudentEnrollment'}
        # Group data
        cloned['groups'] = groups = self.get('groups', all=True, course=course_id)
        # Cohorts
        if 'cohorts' in raw_course_data:
            # Note: Assuming cohorts are unique across groupsets
            cloned['cohorts'] = cohorts = {cohort_name: [user_by_email[email.lower()] for email in emails]
                                           for cohort_name, emails in cloned['cohorts'].items()}
        else:
            cloned['cohorts'] = cohorts = {}
        cloned['staff'] = {user['id']: user for cohort_name, users in cohorts.items() for user in users}
        # Instructors
        if 'instructors' in raw_course_data:
            cloned['instructors'] = instructors = [user_by_email[email.lower()] for email in cloned['instructors']]
        else:
            cloned['instructors'] = instructors = []
        # Student Group Memberships
        cloned['group_memberships'] = {}
        cloned['group_membership_ids'] = {}
        for group in groups:
            group_membership = self.get(f'groups/{group["id"]}/users', course=None, all=True)
            cloned['group_memberships'][group['name']] = [user_by_id[u['id']] for u in group_membership]
            cloned['group_memberships'][group['id']] = {u['id'] for u in group_membership}
        # Assignment Groups
        assignment_groups = self.get('assignment_groups', all=True, course=course_id)
        cloned['assignment_groups'] = {g['id']: g for g in assignment_groups}
        # Assignments
        assignments = self.get('assignments', all=True, course=course_id, data={
            "include[]": ["all_dates", "overrides"]
        })
        cloned['assignments'] = {assignment['id']: self.hydrate_assignment(assignment, cloned)
                                 for assignment in assignments}
        # Submissions
        submissions = self.get('students/submissions', all=True, course=course_id, data={
            'student_ids[]': 'all',
            # 'assignment_ids[]': list(cloned['assignments'].keys()),
            'include[]': ['visibility', 'rubric_assessment']
        })
        cloned['submissions'] = {submission['id']: self.hydrate_submission(submission, cloned)
                                 for submission in submissions}
        # Need to drop submissions for students who dropped
        cloned['submissions'] = {sid: s for sid, s in cloned['submissions'].items() if s}
        # Speed grader URL
        cloned[
            'speed_grader_url'] = 'https://udel.instructure.com/courses/{course_id}/gradebook/speed_grader?assignment_id={assignment_id}&student_id={user_id}'
        # All done
        return cloned

    def hydrate_assignment(self, assignment: dict, course: CourseData) -> Assignment:
        assignment['assignment_group'] = course['assignment_groups'][assignment['assignment_group_id']]
        return assignment

    def hydrate_submission(self, submission: dict, course: CourseData) -> Optional[Submission]:
        if submission['user_id'] not in course['users']:
            return None
        submission['assignment'] = course['assignments'][submission['assignment_id']]
        submission['user'] = course['users'][submission['user_id']]
        if submission['grader_id'] is None:
            submission['grader'] = None
        elif submission['grader_id'] <= 0:
            submission['grader'] = submission['grader_id']
        else:
            submission['grader'] = course['users'][submission['grader_id']]
        return submission
