import pytest
from unittest.mock import MagicMock
from freezegun import freeze_time

from itsdangerous.exc import SignatureExpired, BadSignature

from baserow.core.models import Group
from baserow.core.registries import plugin_registry
from baserow.contrib.database.models import (
    Database, Table, GridView, TextField, BooleanField
)
from baserow.core.user.exceptions import UserAlreadyExist, UserNotFound
from baserow.core.user.handler import UserHandler

@pytest.mark.django_db
def test_get_user(data_fixture):
    user_1 = data_fixture.create_user(email='user1@localhost')

    handler = UserHandler()

    with pytest.raises(ValueError):
        handler.get_user()

    with pytest.raises(UserNotFound):
        handler.get_user(user_id=-1)

    with pytest.raises(UserNotFound):
        handler.get_user(email='user3@localhost')

    assert handler.get_user(user_id=user_1.id).id == user_1.id
    assert handler.get_user(email=user_1.email).id == user_1.id


@pytest.mark.django_db
def test_create_user():
    plugin_mock = MagicMock()
    plugin_registry.registry['mock'] = plugin_mock

    user_handler = UserHandler()

    user = user_handler.create_user('Test1', 'test@test.nl', 'password')
    assert user.pk
    assert user.first_name == 'Test1'
    assert user.email == 'test@test.nl'
    assert user.username == 'test@test.nl'

    assert Group.objects.all().count() == 1
    group = Group.objects.all().first()
    assert group.users.filter(id=user.id).count() == 1
    assert group.name == "Test1's group"

    assert Database.objects.all().count() == 1
    assert Table.objects.all().count() == 2
    assert GridView.objects.all().count() == 2
    assert TextField.objects.all().count() == 3
    assert BooleanField.objects.all().count() == 2

    tables = Table.objects.all().order_by('id')

    model_1 = tables[0].get_model()
    assert model_1.objects.all().count() == 4

    model_2 = tables[1].get_model()
    assert model_2.objects.all().count() == 3

    plugin_mock.user_created.assert_called_with(user, group)

    with pytest.raises(UserAlreadyExist):
        user_handler.create_user('Test1', 'test@test.nl', 'password')


@pytest.mark.django_db
def test_send_reset_password_email(data_fixture, mailoutbox):
    user = data_fixture.create_user(email='test@localhost')
    handler = UserHandler()

    signer = handler.get_reset_password_signer()
    handler.send_reset_password_email(user, 'http://localhost/reset-password')

    assert len(mailoutbox) == 1
    email = mailoutbox[0]

    assert email.subject == 'Reset password'
    assert email.from_email == 'no-reply@localhost'
    assert 'test@localhost' in email.to

    html_body = email.alternatives[0][0]
    search_url = 'http://localhost/reset-password/'
    start_url_index = html_body.index(search_url)

    assert start_url_index != -1

    end_url_index = html_body.index('"', start_url_index)
    token = html_body[start_url_index + len(search_url):end_url_index]

    user_id = signer.loads(token)
    assert user_id == user.id


@pytest.mark.django_db
def test_reset_password(data_fixture):
    user = data_fixture.create_user(email='test@localhost')
    handler = UserHandler()

    signer = handler.get_reset_password_signer()

    with pytest.raises(BadSignature):
        handler.reset_password('test', 'test')
        assert not user.check_password('test')

    with freeze_time('2020-01-01 12:00'):
        token = signer.dumps(9999)

    with freeze_time('2020-01-02 12:00'):
        with pytest.raises(UserNotFound):
            handler.reset_password(token, 'test')
            assert not user.check_password('test')

    with freeze_time('2020-01-01 12:00'):
        token = signer.dumps(user.id)

    with freeze_time('2020-01-04 12:00'):
        with pytest.raises(SignatureExpired):
            handler.reset_password(token, 'test')
            assert not user.check_password('test')

    with freeze_time('2020-01-02 12:00'):
        user = handler.reset_password(token, 'test')
        assert user.check_password('test')
