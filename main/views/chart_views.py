from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.views.decorators import staff_member_required
import pandas as pd
from datetime import datetime
from main.models import Index, IndexValue
import matplotlib.pyplot as plt
import base64
from io import BytesIO




@login_required
def index_viewer(request, index_id):
    chart = None
    all_indexes = Index.objects.all().order_by("name")

    try:
        index = Index.objects.get(id=index_id)
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

    except Index.DoesNotExist:
        chart = None

    return render(
        request, "index_viewer.html", {
            "all_indexes": all_indexes,
            "chart": chart,
            "selected_index_id": index_id
        })
