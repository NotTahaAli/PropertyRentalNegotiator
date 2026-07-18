from app import crud


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table, row=None):
        self.table = table
        self.row = row
        self.filters = {}

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def execute(self):
        if self.row is not None:
            return FakeResult([{"id": "new-id", **self.row}])
        rows = FakeTable.SEEDED.get(self.table, [])
        matches = [r for r in rows if all(r.get(k) == v for k, v in self.filters.items())]
        return FakeResult(matches)


class FakeTable:
    SEEDED: dict[str, list[dict]] = {}

    def __init__(self, name):
        self.name = name

    def insert(self, row):
        return FakeQuery(self.name, row=row)

    def select(self, _columns):
        return FakeQuery(self.name)


class FakeClient:
    def table(self, name):
        return FakeTable(name)


def test_create_and_get_and_list_roundtrip(monkeypatch):
    FakeTable.SEEDED["specs"] = [{"id": "s1", "vertical": "shop_rental"}]
    monkeypatch.setattr(crud, "get_client", lambda: FakeClient())

    created = crud.create_spec({"vertical": "shop_rental"})
    assert created["vertical"] == "shop_rental"
    assert created["id"] == "new-id"

    fetched = crud.get_spec("s1")
    assert fetched == {"id": "s1", "vertical": "shop_rental"}

    listed = crud.list_specs(vertical="shop_rental")
    assert listed == [{"id": "s1", "vertical": "shop_rental"}]

    assert crud.get_spec("missing") is None
