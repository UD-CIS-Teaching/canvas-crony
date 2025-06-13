from __future__ import annotations
import os
from collections import defaultdict
from email.message import EmailMessage
import smtplib
import logging

from reports.report_types import Report, ReportSet
from settings import Settings

logger = logging.getLogger("crony")


def send_emails(
    report_sets: list[ReportSet], only_emails: list[str], settings: Settings
):
    grouped_targets = defaultdict(list)
    for report_set in report_sets:
        for report in report_set.reports:
            email = report.target["email"]
            if only_emails and email not in only_emails:
                continue
            grouped_targets[email].append(report)
    for email, reports in grouped_targets.items():
        send_email(reports, settings)


def send_email(reports: list[Report], settings: Settings) -> bool:
    # Arbitrarily choose first report, they should all have the same header info!
    report = reports[0]
    msg = EmailMessage()
    if len(reports) > 1:
        msg["Subject"] = "Canvas Crony Reports"
    else:
        msg["Subject"] = report.subject.format(
            course_name=report.course["course"]["name"], user_name=report.target["name"]
        )
    msg["From"] = "Canvas Crony Tool <noreply+canvas_crony@udel.edu>"
    msg["To"] = f"{report.target['name']} <{report.target['email']}"
    # definitely don't mess with the .preamble

    if len(reports) > 1:
        msg.set_content(
            "Hi, I am the Canvas Crony! I send you regular updates on some of your courses."
            " I have some reports for you!"
        )
    else:
        msg.set_content(
            "Hi, I am the Canvas Crony! I send you regular updates on some of your courses."
            " I have a report for you!"
        )

    for report in reports:
        with open(report.path, "rb") as fp:
            msg.add_attachment(
                fp.read(),
                maintype=report.maintype,
                subtype=report.subtype,
                filename=report.filename,
            )

    # Notice how smtplib now includes a send_message() method
    mail_server = settings["mail_server"]
    mail_server_port = settings["mail_server_port"]
    try:
        with smtplib.SMTP(mail_server, mail_server_port) as s:
            result = s.send_message(msg)
            if result:
                logger.info(result)
            else:
                logger.info(f"Sent {len(reports)} reports to {msg['To']}")
    except Exception as exception:
        logger.error(f"Error while sending email to {msg['To']}: {exception}")
    return False
