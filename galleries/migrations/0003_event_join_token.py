
import uuid

from django.db import migrations, models


def generate_event_tokens(apps, schema_editor):
    Event = apps.get_model("galleries", "Event")

    for event in Event.objects.filter(join_token__isnull=True).iterator():
        event.join_token = uuid.uuid4()
        event.save(update_fields=["join_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("galleries", "0002_savedphotomatch"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="join_token",
            field=models.UUIDField(
                null=True,
                blank=True,
                editable=False,
            ),
        ),
        migrations.RunPython(
            generate_event_tokens,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="event",
            name="join_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
