from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ems", "0008_company_address_parts")]

    operations = [
        migrations.AddField(model_name="employee", name="personal_email", field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="employee", name="emergency_contact_name", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="employee", name="emergency_contact_phone", field=models.CharField(blank=True, max_length=25)),
    ]
