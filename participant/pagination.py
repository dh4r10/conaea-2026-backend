# pagination.py (nueva archivo en tu app)
from rest_framework.pagination import PageNumberPagination

class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'  # permite ?page_size=20
    max_page_size = 100