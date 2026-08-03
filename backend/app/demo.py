def maybe_enter_demo_mode(session_factory, gateway, settings) -> bool:
    if settings.demo_mode == "on":
        return True
    if settings.demo_mode == "off":
        return False
    return not gateway.available()
