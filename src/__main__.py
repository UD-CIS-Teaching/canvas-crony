"""

python -m canvas_crony --course 123456
python -m canvas_crony --courses <path>
python -m canvas_crony --all --email
python -m canvas_crony --all --email --only "acbart@udel.edu"
"""
import argparse

from canvas_crony import canvas_crony

parser = argparse.ArgumentParser(description="A tool for summarizing data from Canvas")

parser.add_argument('--course', dest="course", default=None,
                    help="Specify a single individual course to run the tool on.")
parser.add_argument('--courses', dest='courses', default=None,
                    help="Specify an entire folder to check the courses in.")
parser.add_argument("--email", action="store_true",
                    help="Actually send out an email with the attached report.")
parser.add_argument("--only", help="Override who receives the email to only be the given list.")

parser.add_argument("--cache", action="store_true", help="Turn on the cache so that requests are remembered.")
parser.add_argument("--settings", default=None, help="File with the API settings. Defaults to secrets/settings.json")
parser.add_argument("--output", default=None,
                    help="The folder to store the generated PDF files into. Files will be named after the course and "
                         "time.")

args = parser.parse_args()

canvas_crony(vars(args))
