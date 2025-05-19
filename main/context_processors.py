from .models import Index

def index_list(request):
    return {
        'index_list': Index.objects.all()
    }

