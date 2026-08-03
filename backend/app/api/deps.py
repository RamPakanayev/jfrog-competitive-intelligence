from fastapi import Request


def get_session_factory(request: Request):
    return request.app.state.session_factory


def get_settings(request: Request):
    return request.app.state.settings


def get_appcfg(request: Request):
    return request.app.state.appcfg


def get_gateway(request: Request):
    return request.app.state.gateway
