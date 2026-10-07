from django.db import migrations


def forwards(apps, schema_editor):
    """school_admin → principal"""
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='school_admin').update(role='principal')


def backwards(apps, schema_editor):
    """principal → school_admin (rollback)"""
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='principal').update(role='school_admin')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]