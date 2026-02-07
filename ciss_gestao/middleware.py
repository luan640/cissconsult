import time
from django.db import connection


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        try:
            queries = getattr(connection, 'queries', [])
            sql_time_ms = sum(float(q.get('time', 0)) for q in queries) * 1000
            query_count = len(queries)
        except Exception:
            sql_time_ms = 0.0
            query_count = 0
        print(
            f"[perf] {request.method} {request.path} -> {response.status_code} | "
            f"{elapsed_ms:.1f} ms total | {sql_time_ms:.1f} ms SQL | {query_count} queries"
        )
        return response
