from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ems", "0005_employee_user_memberships"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="industry",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="company",
            name="website",
            field=models.URLField(blank=True),
        ),
    ]
