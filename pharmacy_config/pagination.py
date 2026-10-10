from rest_framework.pagination import PageNumberPagination


class LargeResultsSetPagination(PageNumberPagination):
    """Same shape as the default paginator, but the client may ask for a
    bigger page (`?page_size=200`). The mobile app uses this so loading
    every medicine / batch / movement takes a handful of requests instead of
    dozens (each one can be slow when Render's free tier is waking up)."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500
