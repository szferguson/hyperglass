"""Data models used throughout hyperglass."""

# Standard Library

# Standard Library
import re
import json
import typing as t
from pathlib import Path

# Third Party
from pydantic import HttpUrl, BaseModel, BaseConfig, PrivateAttr
from pydantic.generics import GenericModel

# Project
from hyperglass.log import log
from hyperglass.util import compare_init, snake_to_camel, repr_from_attrs
from hyperglass.types import Series

MultiModelT = t.TypeVar("MultiModelT", bound=BaseModel)


class HyperglassModel(BaseModel):
    """Base model for all hyperglass configuration models."""

    class Config(BaseConfig):
        """Pydantic model configuration."""

        validate_all = True
        extra = "forbid"
        validate_assignment = True
        allow_population_by_field_name = True
        json_encoders = {HttpUrl: lambda v: str(v), Path: str}

        @classmethod
        def alias_generator(cls: "HyperglassModel", field: str) -> str:
            """Remove unsupported characters from field names.

            Converts any "desirable" separators to underscore, then removes all
            characters that are unsupported in Python class variable names.
            Also removes leading numbers underscores.
            """
            _replaced = re.sub(r"[\-|\.|\@|\~|\:\/|\s]", "_", field)
            _scrubbed = "".join(re.findall(r"([a-zA-Z]\w+|\_+)", _replaced))
            snake_field = _scrubbed.lower()
            if snake_field != field:
                log.debug(
                    "Model field '{}.{}' was converted from {} to {}",
                    cls.__module__,
                    snake_field,
                    repr(field),
                    repr(snake_field),
                )
            return snake_to_camel(snake_field)

    def convert_paths(self, value: t.Any):
        """Change path to relative to app_path."""
        # Project
        from hyperglass.settings import Settings

        if isinstance(value, Path):
            if Settings.container:
                return str(
                    Settings.default_app_path.joinpath(
                        *(p for p in value.parts if p not in Settings.app_path.parts)
                    )
                )

        if isinstance(value, str):
            path = Path(value)
            if path.exists() and Settings.container:
                # if path.exists():
                return str(
                    Settings.default_app_path.joinpath(
                        *(p for p in path.parts if p not in Settings.app_path.parts)
                    )
                )

        if isinstance(value, t.Tuple):
            return tuple(self.convert_paths(v) for v in value)
        if isinstance(value, t.List):
            return [self.convert_paths(v) for v in value]
        if isinstance(value, t.Generator):
            return (self.convert_paths(v) for v in value)
        if isinstance(value, t.Dict):
            return {k: self.convert_paths(v) for k, v in value.items()}
        return value

    def _repr_from_attrs(self, attrs: Series[str]) -> str:
        """Alias to `hyperglass.util:repr_from_attrs` in the context of this model."""
        return repr_from_attrs(self, attrs)

    def export_json(self, *args, **kwargs):
        """Return instance as JSON."""

        export_kwargs = {"by_alias": False, "exclude_unset": False}

        for key in kwargs.keys():
            export_kwargs.pop(key, None)

        return self.json(*args, **export_kwargs, **kwargs)

    def export_dict(self, *args, **kwargs):
        """Return instance as dictionary."""

        export_kwargs = {"by_alias": False, "exclude_unset": False}

        for key in kwargs.keys():
            export_kwargs.pop(key, None)

        return self.dict(*args, **export_kwargs, **kwargs)

    def export_yaml(self, *args, **kwargs):
        """Return instance as YAML."""

        # Standard Library
        import json

        # Third Party
        import yaml

        export_kwargs = {
            "by_alias": kwargs.pop("by_alias", False),
            "exclude_unset": kwargs.pop("exclude_unset", False),
        }

        return yaml.safe_dump(json.loads(self.export_json(**export_kwargs)), *args, **kwargs)


class HyperglassUniqueModel(HyperglassModel):
    """hyperglass model that is unique by its `id` field."""

    _unique_fields: t.ClassVar[Series[str]] = ()

    def __init_subclass__(cls, *, unique_by: Series[str], **kw: t.Any) -> None:
        """Assign unique fields to class."""
        cls._unique_fields = tuple(unique_by)
        return super().__init_subclass__(**kw)

    def __eq__(self: "HyperglassUniqueModel", other: "HyperglassUniqueModel") -> bool:
        """Other model is equal to this model."""
        if not isinstance(other, self.__class__):
            return False
        if hash(self) == hash(other):
            return True
        return False

    def __ne__(self: "HyperglassUniqueModel", other: "HyperglassUniqueModel") -> bool:
        """Other model is not equal to this model."""
        return not self.__eq__(other)

    def __hash__(self: "HyperglassUniqueModel") -> int:
        """Create a hashed representation of this model's name."""
        fields = dict(zip(self._unique_fields, (getattr(self, f) for f in self._unique_fields)))
        return hash(json.dumps(fields))


class HyperglassModelWithId(HyperglassModel):
    """hyperglass model that is unique by its `id` field."""

    id: str

    def __eq__(self: "HyperglassModelWithId", other: "HyperglassModelWithId") -> bool:
        """Other model is equal to this model."""
        if not isinstance(other, self.__class__):
            return False
        if hasattr(other, "id"):
            return other and self.id == other.id
        return False

    def __ne__(self: "HyperglassModelWithId", other: "HyperglassModelWithId") -> bool:
        """Other model is not equal to this model."""
        return not self.__eq__(other)

    def __hash__(self: "HyperglassModelWithId") -> int:
        """Create a hashed representation of this model's name."""
        return hash(self.id)


class MultiModel(GenericModel, t.Generic[MultiModelT]):
    """Extension of HyperglassModel for managing multiple models as a list."""

    model: t.ClassVar[MultiModelT]
    unique_by: t.ClassVar[str]
    model_name: t.ClassVar[str] = "MultiModel"

    __root__: t.List[MultiModelT] = []
    _count: int = PrivateAttr()

    class Config(BaseConfig):
        """Pydantic model configuration."""

        validate_all = True
        extra = "forbid"
        validate_assignment = True

    def __init__(self, *items: t.Union[MultiModelT, t.Dict[str, t.Any]]) -> None:
        """Validate items."""
        for cls_var in ("model", "unique_by"):
            if getattr(self, cls_var, None) is None:
                raise AttributeError(f"MultiModel is missing class variable '{cls_var}'")
        valid = self._valid_items(*items)
        super().__init__(__root__=valid)
        self._count = len(self.__root__)

    def __init_subclass__(cls, **kw: t.Any) -> None:
        """Add class variables from keyword arguments."""
        model = kw.pop("model", None)
        cls.model = model
        cls.unique_by = kw.pop("unique_by", None)
        cls.model_name = getattr(model, "__name__", "MultiModel")
        super().__init_subclass__()

    def __repr__(self) -> str:
        """Represent model."""
        return repr_from_attrs(self, ["_count", "unique_by", "model_name"], strip="_")

    def __iter__(self) -> t.Iterator[MultiModelT]:
        """Iterate items."""
        return iter(self.__root__)

    def __getitem__(self, value: t.Union[int, str]) -> MultiModelT:
        """Get an item by its `unique_by` property."""
        if not isinstance(value, (str, int)):
            raise TypeError(
                "Value of {}.{!s} should be a string or integer. Got {!r} ({!s})".format(
                    self.__class__.__name__, self.unique_by, value, type(value)
                )
            )
        if isinstance(value, int):
            return self.__root__[value]

        for item in self:
            if hasattr(item, self.unique_by) and getattr(item, self.unique_by) == value:
                return item
        raise IndexError(
            "No match found for {!s}.{!s}={!r}".format(
                self.model.__class__.__name__, self.unique_by, value
            ),
        )

    def __add__(self, other: MultiModelT) -> MultiModelT:
        """Merge another MultiModel with this one.

        Note: If you're subclassing `HyperglassMultiModel` and overriding `__init__`, you need to
        override this too.
        """
        valid = all(
            (
                isinstance(other, self.__class__),
                hasattr(other, "model"),
                getattr(other, "model", None) == self.model,
            ),
        )
        if not valid:
            raise TypeError(f"Cannot add {other!r} to {self.__class__.__name__}")
        merged = self._merge_with(*other, unique_by=self.unique_by)

        if compare_init(self.__class__, other.__class__):
            return self.__class__(*merged)
        raise TypeError(
            f"{self.__class__.__name__} and {other.__class__.__name__} have different `__init__` "
            "signatures. You probably need to override `MultiModel.__add__`"
        )

    def __len__(self) -> int:
        """Get number of items."""
        return len(self.__root__)

    @property
    def ids(self) -> t.Tuple[t.Any, ...]:
        """Get values of all items by `unique_by` property."""
        return tuple(sorted(getattr(item, self.unique_by) for item in self))

    @property
    def count(self) -> int:
        """Access item count."""
        return self._count

    @classmethod
    def create(cls, name: str, *, model: MultiModelT, unique_by: str) -> "MultiModel":
        """Create a MultiModel."""
        new = type(name, (cls,), cls.__dict__)
        new.model = model
        new.unique_by = unique_by
        new.model_name = getattr(model, "__name__", "MultiModel")
        return new

    def _valid_items(
        self, *to_validate: t.List[t.Union[MultiModelT, t.Dict[str, t.Any]]]
    ) -> t.List[MultiModelT]:
        items = [
            item
            for item in to_validate
            if any(
                (
                    (isinstance(item, self.model) and hasattr(item, self.unique_by)),
                    (isinstance(item, t.Dict) and self.unique_by in item),
                ),
            )
        ]
        for index, item in enumerate(items):
            if isinstance(item, t.Dict):
                items[index] = self.model(**item)
        return items

    def _merge_with(self, *items, unique_by: t.Optional[str] = None) -> Series[MultiModelT]:
        to_add = self._valid_items(*items)
        if unique_by is not None:
            unique_by_values = {
                getattr(obj, unique_by) for obj in (*self, *to_add) if hasattr(obj, unique_by)
            }
            unique_by_objects = {
                v: o
                for v in unique_by_values
                for o in (*self, *to_add)
                if getattr(o, unique_by) == v
            }
            return tuple(unique_by_objects.values())
        return (*self.__root__, *to_add)

    def filter(self, *properties: str) -> MultiModelT:
        """Get only items with `unique_by` properties matching values in `properties`."""
        return self.__class__(
            *(item for item in self if getattr(item, self.unique_by, None) in properties)
        )

    def matching(self, *unique: str) -> MultiModelT:
        """Get a new instance containing partial matches from `accessors`."""

        def matches(*searches: str) -> t.Generator[MultiModelT, None, None]:
            """Get any matching items by unique_by property.

            For example, if `unique` is `('one', 'two')`, and `Model.<unique_by>` is `'one'`,
            `Model` is yielded.
            """
            for search in searches:
                pattern = re.compile(rf".*{search}.*", re.IGNORECASE)
                for item in self:
                    if pattern.match(getattr(item, self.unique_by)):
                        yield item

        return self.__class__(*matches(*unique))

    def add(self, *items, unique_by: t.Optional[str] = None) -> None:
        """Add an item to the model."""
        new = self._merge_with(*items, unique_by=unique_by)
        self.__root__ = new
        self._count = len(self.__root__)
        for item in new:
            log.debug(
                "Added {} '{!s}' to {}",
                item.__class__.__name__,
                getattr(item, self.unique_by),
                self.__class__.__name__,
            )
