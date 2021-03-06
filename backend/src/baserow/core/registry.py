from django.core.exceptions import ImproperlyConfigured

from baserow.api.v0.utils import get_serializer_class

from .exceptions import InstanceTypeDoesNotExist, InstanceTypeAlreadyRegistered


class Instance(object):
    """
    This abstract class represents a custom instance that can be added to the registry.
    It must be extended so properties and methods can be added.
    """

    type = None
    """A unique string that identifies the instance."""

    def __init__(self):
        if not self.type:
            raise ImproperlyConfigured('The type of an instance must be set.')


class ModelInstanceMixin:
    """
    This mixin introduces a model_class that will be related to the instance. It is to
    be used in combination with a registry that extends the ModelRegisteryMixin.
    """

    model_class = None

    def __init__(self):
        if not self.model_class:
            raise ImproperlyConfigured('The model_class of an instance must be set.')


class CustomFieldsInstanceMixin:
    """
    If an instance can have custom fields per type, they can be defined here.
    """

    allowed_fields = []
    """The field names that are allowed to set when creating and updating"""

    serializer_field_names = []
    """The field names that must be added to the serializer."""

    serializer_field_overrides = {}
    """The fields that must be added to the serializer."""

    def get_serializer_class(self, *args, **kwargs):
        """
        Returns a model serializer class based on this type field names and overrides.

        :return: The generated model serializer class.
        :rtype: ModelSerializer
        """

        model_class = getattr(self, 'model_class')
        if not model_class:
            raise ValueError('Attribute model_class must be set, maybe you forgot to '
                             'extend the ModelInstanceMixin?')

        return get_serializer_class(
            model_class, self.serializer_field_names,
            field_overrides=self.serializer_field_overrides,
            *args, **kwargs
        )

    def get_serializer(self, model_instance, base_class=None):
        """
        Returns an instantiated model serializer based on this type field names and
        overrides. The provided model instance will be used instantiate the serializer.

        :param model_instance: The instance for which the serializer must be generated.
        :type model_instance: Model
        :param base_class: The base serializer class that must be extended. For example
                           common fields could be stored here.
        :type base_class: ModelSerializer
        :return: The instantiated generated model serializer.
        :rtype: ModelSerializer
        """

        model_instance = model_instance.specific
        serializer_class = self.get_serializer_class(base_class=base_class)
        return serializer_class(model_instance, context={'instance_type': self})


class APIUrlsInstanceMixin:
    def get_api_v0_urls(self):
        """
        If needed custom api related urls to the instance can be added here.

        Example:

            def get_api_urls(self):
                from . import api_urls

                return [
                    path('some-url/', include(api_urls, namespace=self.type)),
                ]

            # api_urls.py
            from django.conf.urls import url

            urlpatterns = [
                url(r'some-view^$', SomeView.as_view(), name='some_view'),
            ]

        :return: A list containing the urls.
        :rtype: list
        """

        return []


class Registry(object):
    name = None
    """The unique name that is used when raising exceptions."""

    does_not_exist_exception_class = InstanceTypeDoesNotExist
    """The exception that is raised when an instance doesn't exist."""

    already_registered_exception_class = InstanceTypeAlreadyRegistered
    """The exception that is raised when an instance is already registered."""

    def __init__(self):
        if not self.name:
            raise ImproperlyConfigured('The name must be set on an '
                                       'InstanceModelRegistry to raise proper errors.')

        self.registry = {}

    def get(self, type_name):
        """
        Returns a registered instance of the given type name.

        :param type_name: The unique name of the registered instance.
        :type type_name: str
        :return: The requested instance.
        :rtype: InstanceModelInstance
        """

        if type_name not in self.registry:
            raise self.does_not_exist_exception_class(f'The {self.name} type '
                                                      f'{type_name} does not exist.')

        return self.registry[type_name]

    def get_types(self):
        """
        Returns a list of available type names.

        :return: The list of available types.
        :rtype: List
        """

        return list(self.registry.keys())

    def register(self, instance):
        """
        Registers a new instance in the registry.

        :param instance: The instance that needs to be registered.
        :type instance: Instance
        """

        if not isinstance(instance, Instance):
            raise ValueError(f'The {self.name} must be an instance of '
                             f'Instance.')

        if instance.type in self.registry:
            raise self.already_registered_exception_class(
                f'The {self.name} with type {instance.type} is already registered.')

        self.registry[instance.type] = instance

    def unregister(self, value):
        """
        Removes a registered instance from the registry. An instance or type name can be
        provided as value.

        :param value: The instance or type name.
        :type value: Instance or str
        """

        if isinstance(value, Instance):
            for type_name, instance in self.registry.items():
                if instance == value:
                    value = type_name

        if isinstance(value, str):
            del self.registry[value]
        else:
            raise ValueError(f'The value must either be an {self.name} instance or '
                             f'type name')


class ModelRegistryMixin:
    def get_by_model(self, model_instance):
        """
        Returns a registered instance of the given model class.

        :param model_instance: The value that must be or must be an instance of the
                               model_class.
        :type model_instance: Model or Model()
        :return: The registered instance.
        :rtype: Instance
        """

        for value in self.registry.values():
            if (
                value.model_class == model_instance
                or isinstance(model_instance, value.model_class)
            ):
                return value

        raise self.does_not_exist_exception_class(f'The {self.name} model instance '
                                                  f'{model_instance} does not exist.')


class CustomFieldsRegistryMixin:
    def get_serializer(self, model_instance, base_class=None):
        """
        Based on the provided model_instance and base_class a unique serializer
        containing the correct field type is generated.

        :param model_instance: The instance for which the serializer must be generated.
        :type model_instance: Model
        :param base_class: The base serializer class that must be extended. For example
                           common fields could be stored here.
        :type base_class: ModelSerializer
        :return: The instantiated generated model serializer.
        :rtype: ModelSerializer
        """

        get_by_model = getattr(self, 'get_by_model')
        if not get_by_model:
            raise ValueError('The method get_by_model must exist on the registry in '
                             'order to generate the serializer, maybe you forgot to '
                             'extend the ModelRegistryMixin?')

        instance_type = self.get_by_model(model_instance.specific_class)
        return instance_type.get_serializer(model_instance, base_class=base_class)


class APIUrlsRegistryMixin:
    @property
    def api_urls(self):
        """
        Returns a list of all the api urls that are in the registered instances.

        :return: The api urls of the registered instances.
        :rtype: list
        """

        api_urls = []
        for types in self.registry.values():
            api_urls += types.get_api_v0_urls()
        return api_urls
