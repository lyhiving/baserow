from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import models

from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.exceptions import UserNotInGroup
from baserow.core.trash.handler import TrashHandler


def test_get_field_ids_from_dict():
    handler = RowHandler()
    fields_dict = {
        1: "Included",
        "field_2": "Included",
        "3": "Included",
        "abc": "Not included",
        "fieldd_3": "Not included",
    }
    assert handler.extract_field_ids_from_dict(fields_dict) == [1, 2, 3]


def test_extract_field_ids_from_string():
    handler = RowHandler()
    assert handler.extract_field_ids_from_string(None) == []
    assert handler.extract_field_ids_from_string("not,something") == []
    assert handler.extract_field_ids_from_string("field_1,field_2") == [1, 2]
    assert handler.extract_field_ids_from_string("field_22,test_8,999") == [22, 8, 999]
    assert handler.extract_field_ids_from_string("is,1,one") == [1]


@pytest.mark.django_db
def test_get_include_exclude_fields(data_fixture):
    table = data_fixture.create_database_table()
    table_2 = data_fixture.create_database_table()
    field_1 = data_fixture.create_text_field(table=table, order=1)
    field_2 = data_fixture.create_text_field(table=table, order=2)
    field_3 = data_fixture.create_text_field(table=table_2, order=3)

    row_handler = RowHandler()

    assert (
        row_handler.get_include_exclude_fields(table, include=None, exclude=None)
        is None
    )

    assert row_handler.get_include_exclude_fields(table, include="", exclude="") is None

    fields = row_handler.get_include_exclude_fields(table, f"field_{field_1.id}")
    assert len(fields) == 1
    assert fields[0].id == field_1.id

    fields = row_handler.get_include_exclude_fields(
        table, f"field_{field_1.id},field_9999,field_{field_2.id}"
    )
    assert len(fields) == 2
    assert fields[0].id == field_1.id
    assert fields[1].id == field_2.id

    fields = row_handler.get_include_exclude_fields(
        table, None, f"field_{field_1.id},field_9999"
    )
    assert len(fields) == 1
    assert fields[0].id == field_2.id

    fields = row_handler.get_include_exclude_fields(
        table, f"field_{field_1.id},field_{field_2}", f"field_{field_1.id}"
    )
    assert len(fields) == 1
    assert fields[0].id == field_2.id

    fields = row_handler.get_include_exclude_fields(table, f"field_{field_3.id}")
    assert len(fields) == 0

    fields = row_handler.get_include_exclude_fields(table, None, f"field_{field_3.id}")
    assert len(fields) == 2


@pytest.mark.django_db
def test_extract_manytomany_values(data_fixture):
    row_handler = RowHandler()

    class TemporaryModel1(models.Model):
        class Meta:
            app_label = "test"

    class TemporaryModel2(models.Model):
        field_1 = models.CharField()
        field_2 = models.ManyToManyField(TemporaryModel1)

        class Meta:
            app_label = "test"

    values = {"field_1": "Value 1", "field_2": ["Value 2"]}

    values, manytomany_values = row_handler.extract_manytomany_values(
        values, TemporaryModel2
    )

    assert len(values.keys()) == 1
    assert "field_1" in values
    assert len(manytomany_values.keys()) == 1
    assert "field_2" in manytomany_values


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.row_created.send")
def test_create_row(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_type="DECIMAL",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()

    with pytest.raises(UserNotInGroup):
        handler.create_row(user=user_2, table=table)

    row_1 = handler.create_row(
        user=user,
        table=table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
            9999: "Must not be added",
        },
    )
    assert getattr(row_1, f"field_{name_field.id}") == "Tesla"
    assert getattr(row_1, f"field_{speed_field.id}") == 240
    assert getattr(row_1, f"field_{price_field.id}") == 59999.99
    assert not getattr(row_1, f"field_9999", None)
    assert row_1.order == 1
    row_1.refresh_from_db()
    assert getattr(row_1, f"field_{name_field.id}") == "Tesla"
    assert getattr(row_1, f"field_{speed_field.id}") == 240
    assert getattr(row_1, f"field_{price_field.id}") == Decimal("59999.99")
    assert not getattr(row_1, f"field_9999", None)
    assert row_1.order == Decimal("1.00000000000000000000")

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["row"].id == row_1.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["before"] is None
    assert send_mock.call_args[1]["model"]._generated_table_model

    row_2 = handler.create_row(user=user, table=table)
    assert getattr(row_2, f"field_{name_field.id}") == "Test"
    assert not getattr(row_2, f"field_{speed_field.id}")
    assert not getattr(row_2, f"field_{price_field.id}")
    row_1.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")

    row_3 = handler.create_row(user=user, table=table, before=row_2)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.99999999999999999999")
    assert send_mock.call_args[1]["before"].id == row_2.id

    row_4 = handler.create_row(user=user, table=table, before=row_2)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.99999999999999999998")
    assert row_4.order == Decimal("1.99999999999999999999")

    row_5 = handler.create_row(user=user, table=table, before=row_3)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.99999999999999999998")
    assert row_4.order == Decimal("1.99999999999999999999")
    assert row_5.order == Decimal("1.99999999999999999997")

    row_6 = handler.create_row(user=user, table=table, before=row_2)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    row_5.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.99999999999999999997")
    assert row_4.order == Decimal("1.99999999999999999998")
    assert row_5.order == Decimal("1.99999999999999999996")
    assert row_6.order == Decimal("1.99999999999999999999")

    row_7 = handler.create_row(user, table=table, before=row_1)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    row_5.refresh_from_db()
    row_6.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.99999999999999999997")
    assert row_4.order == Decimal("1.99999999999999999998")
    assert row_5.order == Decimal("1.99999999999999999996")
    assert row_6.order == Decimal("1.99999999999999999999")
    assert row_7.order == Decimal("0.99999999999999999999")

    with pytest.raises(ValidationError):
        handler.create_row(user=user, table=table, values={price_field.id: -10.22})

    model = table.get_model()

    rows = model.objects.all()
    assert len(rows) == 7
    assert rows[0].id == row_7.id
    assert rows[1].id == row_1.id
    assert rows[2].id == row_5.id
    assert rows[3].id == row_3.id
    assert rows[4].id == row_4.id
    assert rows[5].id == row_6.id
    assert rows[6].id == row_2.id

    row_2.delete()
    row_8 = handler.create_row(user, table=table)
    assert row_8.order == Decimal("3.00000000000000000000")


@pytest.mark.django_db
def test_get_row(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_type="DECIMAL",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()
    row = handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{name_field.id}": "Tesla",
            f"field_{speed_field.id}": 240,
            f"field_{price_field.id}": Decimal("59999.99"),
        },
    )

    with pytest.raises(UserNotInGroup):
        handler.get_row(user=user_2, table=table, row_id=row.id)

    with pytest.raises(RowDoesNotExist):
        handler.get_row(user=user, table=table, row_id=99999)

    row_tmp = handler.get_row(user=user, table=table, row_id=row.id)

    assert row_tmp.id == row.id
    assert getattr(row_tmp, f"field_{name_field.id}") == "Tesla"
    assert getattr(row_tmp, f"field_{speed_field.id}") == 240
    assert getattr(row_tmp, f"field_{price_field.id}") == Decimal("59999.99")


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.row_updated.send")
def test_update_row(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_type="DECIMAL",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()
    row = handler.create_row(user=user, table=table)

    with pytest.raises(UserNotInGroup):
        handler.update_row(user=user_2, table=table, row_id=row.id, values={})

    with pytest.raises(RowDoesNotExist):
        handler.update_row(user=user, table=table, row_id=99999, values={})

    with pytest.raises(ValidationError):
        handler.update_row(
            user=user, table=table, row_id=row.id, values={price_field.id: -10.99}
        )

    with patch(
        "baserow.contrib.database.rows.signals.before_row_update.send"
    ) as before_send_mock:
        handler.update_row(
            user=user,
            table=table,
            row_id=row.id,
            values={
                name_field.id: "Tesla",
                speed_field.id: 240,
                f"field_{price_field.id}": 59999.99,
            },
        )
    row.refresh_from_db()

    assert getattr(row, f"field_{name_field.id}") == "Tesla"
    assert getattr(row, f"field_{speed_field.id}") == 240
    assert getattr(row, f"field_{price_field.id}") == Decimal("59999.99")

    before_send_mock.assert_called_once()
    assert before_send_mock.call_args[1]["row"].id == row.id
    assert before_send_mock.call_args[1]["user"].id == user.id
    assert before_send_mock.call_args[1]["table"].id == table.id
    assert before_send_mock.call_args[1]["model"]._generated_table_model

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["row"].id == row.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["model"]._generated_table_model
    assert send_mock.call_args[1]["before_return"] == before_send_mock.return_value


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.row_updated.send")
@patch("baserow.contrib.database.rows.signals.before_row_update.send")
def test_move_row(before_send_mock, send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)

    handler = RowHandler()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)
    row_3 = handler.create_row(user=user, table=table)

    with pytest.raises(UserNotInGroup):
        handler.move_row(user=user_2, table=table, row_id=row_1.id)

    with pytest.raises(RowDoesNotExist):
        handler.move_row(user=user, table=table, row_id=99999)

    handler.move_row(user=user, table=table, row_id=row_1.id)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("4.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    before_send_mock.assert_called_once()
    assert before_send_mock.call_args[1]["row"].id == row_1.id
    assert before_send_mock.call_args[1]["user"].id == user.id
    assert before_send_mock.call_args[1]["table"].id == table.id
    assert before_send_mock.call_args[1]["model"]._generated_table_model

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["row"].id == row_1.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["model"]._generated_table_model
    assert send_mock.call_args[1]["before_return"] == before_send_mock.return_value

    handler.move_row(user=user, table=table, row_id=row_1.id, before=row_3)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("2.99999999999999999999")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    row_ids = table.get_model().objects.all()
    assert row_ids[0].id == row_2.id
    assert row_ids[1].id == row_1.id
    assert row_ids[2].id == row_3.id


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.row_deleted.send")
@patch("baserow.contrib.database.rows.signals.before_row_delete.send")
def test_delete_row(before_send_mock, send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    model = table.get_model()
    row = handler.create_row(user=user, table=table)
    handler.create_row(user=user, table=table)

    with pytest.raises(UserNotInGroup):
        handler.delete_row(user=user_2, table=table, row_id=row.id)

    with pytest.raises(RowDoesNotExist):
        handler.delete_row(user=user, table=table, row_id=99999)

    row_id = row.id
    handler.delete_row(user=user, table=table, row_id=row.id)
    assert model.objects.all().count() == 1
    assert model.trash.all().count() == 1
    row.refresh_from_db()
    assert row.trashed

    before_send_mock.assert_called_once()
    assert before_send_mock.call_args[1]["row"]
    assert before_send_mock.call_args[1]["user"].id == user.id
    assert before_send_mock.call_args[1]["table"].id == table.id
    assert before_send_mock.call_args[1]["model"]._generated_table_model

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["row_id"] == row_id
    assert send_mock.call_args[1]["row"]
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["model"]._generated_table_model
    assert send_mock.call_args[1]["before_return"] == before_send_mock.return_value


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.row_created.send")
def test_restore_row(send_mock, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_type="DECIMAL",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()

    row_1 = handler.create_row(
        user=user,
        table=table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
        },
    )

    handler.delete_row(user, table, row_1.id)
    TrashHandler.restore_item(user, "row", row_1.id, parent_trash_item_id=table.id)

    assert len(send_mock.call_args) == 2
    assert send_mock.call_args[1]["row"].id == row_1.id
    assert send_mock.call_args[1]["user"] is None
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["before"] is None
    assert send_mock.call_args[1]["model"]._generated_table_model


@pytest.mark.django_db
def test_get_include_exclude_fields_with_user_field_names(data_fixture):
    table = data_fixture.create_database_table()
    data_fixture.create_text_field(name="first", table=table, order=1)
    data_fixture.create_text_field(name="Test", table=table, order=2)
    data_fixture.create_text_field(name="Test_2", table=table, order=3)
    data_fixture.create_text_field(name="With Space", table=table, order=4)

    row_handler = RowHandler()

    assert (
        row_handler.get_include_exclude_fields(
            table, include=None, exclude=None, user_field_names=True
        )
        is None
    )

    assert (
        row_handler.get_include_exclude_fields(
            table, include="", exclude="", user_field_names=True
        )
        is None
    )

    fields = row_handler.get_include_exclude_fields(
        table, include="Test_2", user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == ["Test_2"]

    fields = row_handler.get_include_exclude_fields(
        table, "first,field_9999,Test", user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == ["first", "Test"]

    fields = row_handler.get_include_exclude_fields(
        table, None, "first,field_9999", user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == [
        "Test",
        "Test_2",
        "With Space",
    ]

    fields = row_handler.get_include_exclude_fields(
        table, "first,Test", "first", user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == ["Test"]

    fields = row_handler.get_include_exclude_fields(
        table, 'first,"With Space",Test', user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == [
        "first",
        "Test",
        "With Space",
    ]


@pytest.mark.django_db
def test_has_row(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_type="DECIMAL",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()
    row = handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{name_field.id}": "Tesla",
            f"field_{speed_field.id}": 240,
            f"field_{price_field.id}": Decimal("59999.99"),
        },
    )

    with pytest.raises(UserNotInGroup):
        handler.has_row(user=user_2, table=table, row_id=row.id)

    with pytest.raises(RowDoesNotExist):
        handler.has_row(user=user, table=table, row_id=99999, raise_error=True)
    assert not handler.has_row(user=user, table=table, row_id=99999, raise_error=False)

    assert handler.has_row(user=user, table=table, row_id=row.id, raise_error=False)
    assert handler.has_row(user=user, table=table, row_id=row.id, raise_error=True)
