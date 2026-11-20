from pathlib import Path

from composapy._wire import codec


class _Deserialize:
    """ContractSerializer.Deserialize(text, T) and ContractSerializer.Deserialize[T](text)."""

    def __call__(self, text, T):
        decoded = codec.decode(text)
        if not isinstance(decoded, T):
            raise ValueError(
                f"The text is not a {T.__name__}: it decoded as {type(decoded).__name__}"
            )
        return decoded

    def __getitem__(self, T):
        return lambda text: self(text, T)


class ContractSerializer:
    Deserialize = _Deserialize()

    @staticmethod
    def Serialize(obj):
        return codec.encode(obj)

    @staticmethod
    def SerializeToFile(obj, path):
        Path(path).write_text(codec.encode(obj), encoding="utf-8")
