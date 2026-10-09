from gunicorn.glogging import Logger


HEALTHCHECK_PATHS = {"/healthz", "/healthz/full"}


class HealthcheckFilterLogger(Logger):
    def access(self, resp, req, environ, request_time):
        if environ.get("PATH_INFO") in HEALTHCHECK_PATHS:
            return

        super().access(resp, req, environ, request_time)


logger_class = HealthcheckFilterLogger
