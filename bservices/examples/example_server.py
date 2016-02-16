# coding: utf-8
"""
WSGI Server
    Run:
        python -m bservices.examples.example_server

HTTP Client:
    Add:
        curl http://127.0.0.1:10000/set_data -d '{"data": "test_data"}' -H "Content-Type: application/json"
        >>> {"id": 1}
    Get:
        curl http://127.0.0.1:10000/get_data?id=1
        >>> {"data": "test_data", "id": 1}

Restriction of `bservices.wsgi.Resource`:
    (1) Only support three kinds of Content-Type:
        A. text/plain
        B. application/json
        C. application/xml
    (2) Automatically serialize and deserialize the body of the request,
        but only for application/json, text/plain. If you want to receive and
        handle the XML content, you MUST register the serializer and deserializer
        of XML; or, it will raise a exception.

Controller Action API:
    If using the wrapper of `Resource`, you obey the action rules below.
    Or, you MUST implement the engine to handle the HTTP request.

    The logic of `Resource` is simply.
    1. It gets the controller, the action method, the URL pattern argument
       by the result that `routes` parsed.
    2. deserialize the body, if any.
    3. pass all the arguments to the action method and call it.
    4. handle the result.

    Handle the result the action method returned:
    (1) if a dict, serialize it to JSON.
    (2) if a object of bservices.wsgi.ResponseObject, serialize it by default.
    (3) If any others, hand it to webob.dec.wsgify to handle.

    In the meanwhile, it also handle some convenient functions, such as the
    default status code, see `bservices.wsgi.Resource._process_stack` and
    `bservices.wsgi.response`. Moreover, it support the action mapping and the
    extensions.

    Action API:
        Args:
            (1) MUST have a argument, req, which is a object of
                `bservices.wsgi.Request`.
            (2) Arguments that `routes` parsed will be past to the action method.
            (3) If having a body, the action method MUST supply a argument, body.

        Return:
            (1) a dict object
            (2) a bservices.wsgi.ResponseObject object
            (3) a exception based on webob.exc.HTTPException or
                bservices.exception.ExceptionBase, or
                bservices.exception.ConvertedException.
            (4) a object of webob.exc.HTTPException, or
                bservices.exception.ConvertedException, or their subclass.
            (5) any object compatible with webob.dec.wsgify.__call__, for
                example, None, string(str, bytes, unicode), webob.Response, etc.

            Notice:
                The first two will be serialized.
                see bservices.wsgi.ResponseObject.
"""
import logging
import multiprocessing

import routes
import eventlet
from oslo_config import cfg
from oslo_log import log
from oslo_service import service
from oslo_service.wsgi import Router, Server

from bservices import wsgi, exception
from bservices.examples.db import api

LOG = logging.getLogger()
CONF = cfg.CONF

cli_opts = [
    cfg.StrOpt("listen_ip", default='0.0.0.0'),
    cfg.IntOpt("listen_port", default=10000)
]
CONF.register_cli_opts(cli_opts)


class DataController(wsgi.Controller):
    def get_data(self, req):
        try:
            id = int(req.GET["id"])
        except (KeyError, TypeError, ValueError):
            raise exception.BadRequest()

        ret = api.get_data(id)
        if not ret:
            raise exception.NotFound()
        return ret

    def set_data(self, req, body):
        try:
            data = body["data"]
        except (KeyError, TypeError, ValueError):
            raise exception.BadRequest()

        return api.set_data(data)


class API(Router):
    def __init__(self):
        mapper = routes.Mapper()
        mapper.redirect("", "/")

        resource = wsgi.Resource(DataController())
        mapper.connect("/get_data",
                       controller=resource,
                       action="get_data",
                       conditions={"method": ['GET']})
        mapper.connect("/set_data",
                       controller=resource,
                       action="set_data",
                       conditions={"method": ["POST"]})

        super(API, self).__init__(mapper)


class WSGIServer(Server, service.ServiceBase):
    pass


def main(project="example"):
    log.register_options(CONF)
    # log.set_defaults(default_log_levels=None)
    CONF(project=project)

    log.setup(CONF, project)
    eventlet.monkey_patch(all=True)

    server = WSGIServer(CONF, project, API(), host=CONF.listen_ip, port=CONF.listen_port,
                        use_ssl=False, max_url_len=1024)
    launcher = service.launch(CONF, server, workers=multiprocessing.cpu_count())
    launcher.wait()


if __name__ == '__main__':
    main()
