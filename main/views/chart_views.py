from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from main.models import Index, IndexValue, UserProfile
import matplotlib.pyplot as plt
import base64
from io import BytesIO

@login_required
def index_viewer(request, index_id):
    chart = None
    all_indexes = Index.objects.all().order_by("name")
    user_profile = request.user.userprofile
    user_favorites = user_profile.favorite_indexes.all()

    index = get_object_or_404(Index, id=index_id)
    values = IndexValue.objects.filter(index=index).order_by("date")

    if values.exists():
        dates = [v.date for v in values]
        val = [v.value for v in values]

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(dates, val, marker='o')
        ax.set_title(index.name)
        ax.set_xlabel("Date")
        ax.set_ylabel("Valeur")
        ax.grid(True)

        buffer = BytesIO()
        plt.tight_layout()
        fig.autofmt_xdate()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()

        chart = base64.b64encode(image_png).decode("utf-8")
        plt.close(fig)

    return render(
        request,
        "index_viewer.html",
        {
            "all_indexes": all_indexes,
            "chart": chart,
            "selected_index_id": index_id,
            "current_index": index,
            "user_favorites": user_favorites,
        }
    )
