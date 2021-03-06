from django.db import connection

from baserow.contrib.database.fields.models import TextField, NumberField, BooleanField


class FieldFixtures:
    def create_model_field(self, table, field):
        with connection.schema_editor() as schema_editor:
            to_model = table.get_model(field_ids=[field.id])
            model_field = to_model._meta.get_field(field.db_column)
            schema_editor.add_field(to_model, model_field)

    def create_text_field(self, user=None, create_field=True, **kwargs):
        if 'table' not in kwargs:
            kwargs['table'] = self.create_database_table(user=user)

        if 'name' not in kwargs:
            kwargs['name'] = self.fake.name()

        if 'order' not in kwargs:
            kwargs['order'] = 0

        field = TextField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs['table'], field)

        return field

    def create_number_field(self, user=None, create_field=True, **kwargs):
        if 'table' not in kwargs:
            kwargs['table'] = self.create_database_table(user=user)

        if 'name' not in kwargs:
            kwargs['name'] = self.fake.name()

        if 'order' not in kwargs:
            kwargs['order'] = 0

        field = NumberField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs['table'], field)

        return field

    def create_boolean_field(self, user=None, create_field=True, **kwargs):
        if 'table' not in kwargs:
            kwargs['table'] = self.create_database_table(user=user)

        if 'name' not in kwargs:
            kwargs['name'] = self.fake.name()

        if 'order' not in kwargs:
            kwargs['order'] = 0

        field = BooleanField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs['table'], field)

        return field
