import types

_registry = {}


def register(type_name, cls):
    _registry[type_name] = cls


def class_for(type_name):
    return _registry.get(type_name, ContractObject)


class ContractObject(dict):
    @property
    def type_name(self):
        return self.get("__type")

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        if name.startswith(
            "_"
        ):  # __class__, _local_file, _contract__result_id: about the object, not members
            object.__setattr__(self, name, value)
        else:
            self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError(name) from None


class NetList(list):
    # A list that also has the members of the .NET List<T> a script could call on a contract's collection.

    __slots__ = ()

    @property
    def Count(self):
        return len(self)

    def Contains(self, item):
        return item in self

    def IndexOf(self, item):
        try:
            return self.index(item)
        except ValueError:
            return -1

    def LastIndexOf(self, item):
        for position in range(len(self) - 1, -1, -1):
            if self[position] == item:
                return position
        return -1

    def ToArray(self):
        return list(self)

    def GetRange(self, index, count):
        if index < 0 or count < 0 or index + count > len(self):
            raise IndexError("Offset and length were out of bounds for the list.")
        return NetList(self[index : index + count])

    def Add(self, item):
        self.append(item)

    def AddRange(self, items):
        self.extend(items)

    def Insert(self, index, item):
        if index < 0 or index > len(self):
            raise IndexError("Index must be within the bounds of the List.")
        self.insert(index, item)

    def Remove(self, item):
        try:
            self.remove(item)
        except ValueError:
            return False
        return True

    def RemoveAt(self, index):
        if index < 0 or index >= len(self):
            raise IndexError(
                "Index was out of range. Must be non-negative and less than the size of the collection."
            )
        del self[index]

    def Reverse(self):
        self.reverse()

    def Sort(self):
        self.sort()

    def Clear(self):
        self.clear()


class KeyedList(NetList):
    __slots__ = ()

    @property
    def Indexes(self):
        return types.SimpleNamespace(Keys=[item.Name for item in self])

    def __getitem__(self, key):
        if isinstance(key, str):
            for item in self:
                if item.Name == key:
                    return item
            raise KeyError(key)
        return super().__getitem__(key)

    def Contains(self, item):
        if isinstance(item, str):
            return any(member.Name == item for member in self)
        return super().Contains(item)

    def Add(self, item):
        self.append(item)
