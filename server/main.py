import dataclasses
import fastapi
import pathlib
import pkgutil
from . import ops
from . import workspace

here = pathlib.Path(__file__).parent
for _, name, _ in pkgutil.iter_modules([str(here)]):
    if name.endswith('_ops') and not name.startswith('test_'):
        print(f'Importing {name}')
        __import__(f'server.{name}')

app = fastapi.FastAPI()


@app.get("/api/catalog")
def get_catalog():
    return {
        k: {op.name: op.model_dump() for op in v.values()}
        for k, v in ops.CATALOGS.items()}


class SaveRequest(workspace.BaseConfig):
    path: str
    ws: workspace.Workspace

def save(req: SaveRequest):
    path = DATA_PATH / req.path
    assert path.is_relative_to(DATA_PATH)
    workspace.save(req.ws, path)

@app.post("/api/save")
def save_and_execute(req: SaveRequest):
    save(req)
    workspace.execute(req.ws)
    save(req)
    return req.ws

@app.get("/api/load")
def load(path: str):
    path = DATA_PATH / path
    assert path.is_relative_to(DATA_PATH)
    if not path.exists():
        return workspace.Workspace()
    return workspace.load(path)

DATA_PATH = pathlib.Path.cwd() / 'data'

@dataclasses.dataclass(order=True)
class DirectoryEntry:
    name: str
    type: str

@app.get("/api/dir/list")
def list_dir(path: str):
    path = DATA_PATH / path
    assert path.is_relative_to(DATA_PATH)
    return sorted([
        DirectoryEntry(p.relative_to(DATA_PATH), 'directory' if p.is_dir() else 'workspace')
        for p in path.iterdir()])

@app.post("/api/dir/mkdir")
def make_dir(req: dict):
    path = DATA_PATH / req['path']
    assert path.is_relative_to(DATA_PATH)
    assert not path.exists()
    path.mkdir()
    return list_dir(path.parent)
