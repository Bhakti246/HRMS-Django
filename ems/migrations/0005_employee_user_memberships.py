from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("ems", "0004_multitenant_foundation"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AlterField(
            model_name="employee",
            name="user",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="employees", to=settings.AUTH_USER_MODEL),
        ),
    ]
