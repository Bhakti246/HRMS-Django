from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ems", "0007_useraccountprofile")]

    operations = [
        migrations.AddField(model_name="company", name="city", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="company", name="state", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="company", name="country", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="company", name="pincode", field=models.CharField(blank=True, max_length=20)),
    ]
