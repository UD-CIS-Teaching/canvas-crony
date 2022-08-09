from __future__ import annotations
from typing import TypedDict
import requests
import time
import json
from datetime import datetime
import requests_cache
from settings import Settings

CANVAS_DATE_STRING = "%Y-%m-%dT%H:%M:%SZ"


def from_canvas_date(d1):
    return datetime.strptime(d1, CANVAS_DATE_STRING)


def to_canvas_date(d1):
    return d1.strftime(CANVAS_DATE_STRING)


def days_between(d1, d2=None):
    d1 = datetime.strptime(d1, CANVAS_DATE_STRING)
    if d2 is None:
        d2 = datetime.utcnow()
    else:
        d2 = datetime.strptime(d2, CANVAS_DATE_STRING)
    return abs((d2 - d1).days)


def decode_response_or_error(response, from_url):
    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        raise Exception(f"{response}\n{from_url}")


def check_response_errors(response, from_url):
    if response.status_code == 503:
        raise Exception("503 error, service not available yet! Try again later!" + str(response.status_code))
    elif response.status_code == 404:
        response_json = decode_response_or_error(response, from_url)
        raise Exception(
            f"404 error, resource does not exist for\n{from_url}\nFull error was:\n" + str(response_json))
    elif not str(response.status_code).startswith('2'):
        response_json = decode_response_or_error(response, from_url)
        raise Exception(
            f"Possible error code ({response.status_code}) for:\n{from_url}\nFull error was:\n" + str(
                response_json))


class CanvasData(TypedDict):
    pass



class CanvasRequest:
    def __init__(self, settings: Settings, cache: bool):
        self.canvas_url = settings['canvas_url'] + "/"
        self.canvas_api_url = self.canvas_url + "api/v1/"
        self.canvas_token = settings['canvas_token']
        if cache:
            self.session = requests_cache.CachedSession('cron_cache')
        else:
            self.session = requests.Session()

    def _canvas_request(self, verb, command, course_id, data=None, all=True, params=None, result_type=list, use_api=True) -> list[CanvasData]:
        # Initialize data and params if they were not provided
        if data is None:
            data = {}
        if params is None:
            params = {}
        # Build up the URL
        if use_api:
            next_url = self.canvas_api_url
        else:
            next_url = self.canvas_url
        if course_id is not None:
            if isinstance(course_id, dict):
                course_id = course_id['id']
            next_url += f'courses/{course_id}/'
        next_url += command
        data['access_token'] = self.canvas_token
        # Handle getting all the results
        if all:
            data['per_page'] = 100
            final_result = []
            while True:
                response = verb(next_url, data=data, params=params)
                check_response_errors(response, next_url)
                if result_type == list:
                    final_result += decode_response_or_error(response, next_url)
                elif result_type == dict:
                    final_result.append(decode_response_or_error(response, next_url))
                else:
                    final_result = response
                if 'next' in response.links:
                    next_url = response.links['next']['url']
                else:
                    return final_result
        # Only get one result
        else:
            response = verb(next_url, data=data, params=params)
            check_response_errors(response, next_url)
            if result_type in (list, None):
                return decode_response_or_error(response, next_url)
            elif result_type == dict:
                return [decode_response_or_error(response, next_url)]

    def get(self, command, course='default', data=None, all=False, params=None, result_type=list, use_api=True):
        return self._canvas_request(self.session.get, command, course, data, all, params, result_type=result_type, use_api=use_api)

    def post(self, command, course='default', data=None, all=False, params=None, result_type=list, use_api=True):
        return self._canvas_request(self.session.post, command, course, data, all, params, result_type=result_type, use_api=use_api)

    def put(self, command, course='default', data=None, all=False, params=None, result_type=list, use_api=True):
        return self._canvas_request(self.session.put, command, course, data, all, params, result_type=result_type, use_api=use_api)

    def delete(self, command, course='default', data=None, all=False, params=None, result_type=None, use_api=True):
        return self._canvas_request(self.session.delete, command, course, data, all, params, result_type=result_type, use_api=use_api)

    def progress_loop(self, progress_id, DELAY=3):
        while True:
            result, = self._canvas_request(self.session.get, f'progress/{progress_id}', None, None, False, None, dict, True)
            if result['workflow_state'] == 'completed':
                return True
            elif result['workflow_state'] == 'failed':
                return False
            else:
                # TODO: Replace with TQDM, proper logging
                print(result['workflow_state'], result['message'],
                      str(int(round(result['completion'] * 10)) / 10) + "%")
                time.sleep(DELAY)

    def download_file(self, url, destination):
        data = {'access_token': self.canvas_token}
        r = self.session.get(url, data=data)
        f = open(destination, 'wb')
        for chunk in r.iter_content(chunk_size=512 * 1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
        f.close()
        return destination
