class Limiter:
    def limit(self, rate):
        def decorator(func):
            return func
        return decorator

limiter = Limiter()

def apply_rate_limits(app):
    return limiter

def limit_writeback(func):
    return func

def limit_extract(func):
    return func

def limit_read(func):
    return func
