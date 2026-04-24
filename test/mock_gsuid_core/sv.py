class SV:
    def __init__(self, *args, **kwargs):
        pass
    def on_fullmatch(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def on_command(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

class Plugins:
    def __init__(self, *args, **kwargs):
        pass
    @staticmethod
    def on_fullmatch(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
