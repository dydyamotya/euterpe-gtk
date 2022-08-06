# http.py
#
# Copyright 2021 Doychin Atanasov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gi
import sys
gi.require_version('Soup', '2.4')
from gi.repository import Soup


_soup_session = None

def init_session():
    global _soup_session
    if _soup_session is not None:
        return _soup_session

    _soup_session = Soup.Session()
    _soup_session.props.user_agent = "Euterpe-GTK HTTP Client"
    _soup_session.props.max_conns = 6
    return _soup_session


class Request(object):
    '''
        Request is an utility for creating HTTP requests using the
        Soup framework. So that all the processing is done in the
        background and does not hog the main UI thread.

        Note that the request callback will be called once the whole
        response body has been received.
    '''

    def __init__(self, address, callback):
        '''
        callback must be a function with the following arguments

            * status (int) - the HTTP response code
            * body (GLib.Bytes) - the HTTP response body
            * *args - the arguments passed to `get` or `post`
        '''

        self._session = init_session()
        self._address = address
        self._callback = callback
        self._headers = {}
        self._args = []

    def set_header(self, name, value):
        self._headers[name] = value

    def get(self, *args):
        self._args = args
        req = Soup.Message.new("GET", self._address)
        self._do(req)

    def post(self, content_type, body, *args):
        self._args = args
        req = Soup.Message.new("POST", self._address)
        req.set_request(content_type, Soup.MemoryUse.COPY, body)
        self._do(req)

    def _do(self, req):
        try:
            for k, v in self._headers.items():
                req.props.request_headers.append(k, v)
            self._session.queue_message(req, self._request_cb, None)
        except Exception:
            sys.excepthook(*sys.exc_info())
            self._callback(None, None)

    def _request_cb(self, session, message, data):
        status = message.props.status_code
        resp_body = message.props.response_body_data.get_data()
        self._call_callback(status, resp_body)

    def _call_callback(self, status, data):
        try:
            self._callback(status, data, *(self._args))
        except Exception:
            sys.excepthook(*sys.exc_info())

class AsyncRequest(object):
    '''
        Request is an utility for creating HTTP requests using the
        Soup framework. So that all the processing is done in the
        background and does not hog the main UI thread.

        Note that the request callback will be called once the response
        headers have been received. At this stage the body hasn't been
        read yet.
    '''

    def __init__(self, address, cancellable, callback):
        '''
        * address (string) - the HTTP address to which a request will be made
        * cancellable (Gio.Cancellable) - a way to cancel the request in flight
        * callback - a function with the following arguments:
            - status (int) - the HTTP response code
            - body (Gio.InputStream) - the HTTP response body
            - cancel (Gio.Cancellable) - a cancellable which cancels the request
            - *args - the arguments passed to `get`
        '''

        self._session = init_session()
        self._address = address
        self._callback = callback
        self._headers = {}
        self._args = []
        self._cancellable = cancellable

    def set_header(self, name, value):
        self._headers[name] = value

    def get(self, *args):
        self._args = args
        req = Soup.Message.new("GET", self._address)
        self._do(req)

    def _do(self, req):
        try:
            for k, v in self._headers.items():
                req.props.request_headers.append(k, v)
            self._session.send_async(req, self._cancellable, self._request_cb, req)
        except Exception:
            sys.excepthook(*sys.exc_info())
            self._callback(None, None, None)

    def _request_cb(self, session, res, message):
        status = message.status_code
        body_stream = session.send_finish(res)
        self._call_callback(status, body_stream)

    def _call_callback(self, status, data_stream):
        try:
            self._callback(status, data_stream, self._cancellable, *(self._args))
        except Exception:
            sys.excepthook(*sys.exc_info())
