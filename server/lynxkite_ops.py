'''Some operations. To be split into separate files when we have more.'''
from . import ops
from collections import deque
import dataclasses
import functools
import matplotlib
import networkx as nx
import pandas as pd
import traceback
import typing

op = ops.op_registration('LynxKite')

@dataclasses.dataclass
class RelationDefinition:
  '''Defines a set of edges.'''
  df: str # The DataFrame that contains the edges.
  source_column: str # The column in the edge DataFrame that contains the source node ID.
  target_column: str # The column in the edge DataFrame that contains the target node ID.
  source_table: str # The DataFrame that contains the source nodes.
  target_table: str # The DataFrame that contains the target nodes.
  source_key: str # The column in the source table that contains the node ID.
  target_key: str # The column in the target table that contains the node ID.

@dataclasses.dataclass
class Bundle:
  '''A collection of DataFrames and other data.

  Can efficiently represent a knowledge graph (homogeneous or heterogeneous) or tabular data.
  It can also carry other data, such as a trained model.
  '''
  dfs: dict[str, pd.DataFrame] = dataclasses.field(default_factory=dict)
  relations: list[RelationDefinition] = dataclasses.field(default_factory=list)
  other: dict[str, typing.Any] = None

  @classmethod
  def from_nx(cls, graph: nx.Graph):
    edges = nx.to_pandas_edgelist(graph)
    d = dict(graph.nodes(data=True))
    nodes = pd.DataFrame(d.values(), index=d.keys())
    nodes['id'] = nodes.index
    return cls(
      dfs={'edges': edges, 'nodes': nodes},
      relations=[
        RelationDefinition(
          df='edges',
          source_column='source',
          target_column='target',
          source_table='nodes',
          target_table='nodes',
          source_key='id',
          target_key='id',
        )
      ]
    )

  def to_nx(self):
    graph = nx.from_pandas_edgelist(self.dfs['edges'])
    nx.set_node_attributes(graph, self.dfs['nodes'].set_index('id').to_dict('index'))
    return graph


def nx_node_attribute_func(name):
  '''Decorator for wrapping a function that adds a NetworkX node attribute.'''
  def decorator(func):
    @functools.wraps(func)
    def wrapper(graph: nx.Graph, **kwargs):
      graph = graph.copy()
      attr = func(graph, **kwargs)
      nx.set_node_attributes(graph, attr, name)
      return graph
    return wrapper
  return decorator


def disambiguate_edges(ws):
    '''If an input plug is connected to multiple edges, keep only the last edge.'''
    seen = set()
    for edge in reversed(ws.edges):
        if (edge.target, edge.targetHandle) in seen:
            ws.edges.remove(edge)
        seen.add((edge.target, edge.targetHandle))


@ops.register_executor('LynxKite')
def execute(ws):
    catalog = ops.CATALOGS['LynxKite']
    # Nodes are responsible for interpreting/executing their child nodes.
    nodes = [n for n in ws.nodes if not n.parentId]
    disambiguate_edges(ws)
    children = {}
    for n in ws.nodes:
        if n.parentId:
            children.setdefault(n.parentId, []).append(n)
    outputs = {}
    failed = 0
    while len(outputs) + failed < len(nodes):
        for node in nodes:
            if node.id in outputs:
                continue
            # TODO: Take the input/output handles into account.
            inputs = [edge.source for edge in ws.edges if edge.target == node.id]
            if all(input in outputs for input in inputs):
                inputs = [outputs[input] for input in inputs]
                data = node.data
                op = catalog[data.title]
                params = {**data.params}
                if op.sub_nodes:
                    sub_nodes = children.get(node.id, [])
                    sub_node_ids = [node.id for node in sub_nodes]
                    sub_edges = [edge for edge in ws.edges if edge.source in sub_node_ids]
                    params['sub_flow'] = {'nodes': sub_nodes, 'edges': sub_edges}
                # Convert inputs.
                for i, (x, p) in enumerate(zip(inputs, op.inputs.values())):
                  if p.type == nx.Graph and isinstance(x, Bundle):
                    inputs[i] = x.to_nx()
                  elif p.type == Bundle and isinstance(x, nx.Graph):
                    inputs[i] = Bundle.from_nx(x)
                try:
                  output = op(*inputs, **params)
                except Exception as e:
                  traceback.print_exc()
                  data.error = str(e)
                  failed += 1
                  continue
                if len(op.inputs) == 1 and op.inputs.get('multi') == '*':
                    # It's a flexible input. Create n+1 handles.
                    data.inputs = {f'input{i}': None for i in range(len(inputs) + 1)}
                data.error = None
                outputs[node.id] = output
                if op.type == 'visualization' or op.type == 'table_view' or op.type == 'image':
                    data.display = output

@op("Import Parquet")
def import_parquet(*, filename: str):
  '''Imports a parquet file.'''
  return pd.read_parquet(filename)

@op("Create scale-free graph")
def create_scale_free_graph(*, nodes: int = 10):
  '''Creates a scale-free graph with the given number of nodes.'''
  return nx.scale_free_graph(nodes)

@op("Compute PageRank")
@nx_node_attribute_func('pagerank')
def compute_pagerank(graph: nx.Graph, *, damping=0.85, iterations=100):
  return nx.pagerank(graph, alpha=damping, max_iter=iterations)

@op("Discard loop edges")
def discard_loop_edges(graph: nx.Graph):
  graph = graph.copy()
  graph.remove_edges_from(nx.selfloop_edges(graph))
  return graph

@op("Sample graph")
def sample_graph(graph: nx.Graph, *, nodes: int = 100):
  '''Takes a (preferably connected) subgraph.'''
  sample = set()
  to_expand = deque([0])
  while to_expand and len(sample) < nodes:
    node = to_expand.pop()
    for n in graph.neighbors(node):
      if n not in sample:
        sample.add(n)
        to_expand.append(n)
      if len(sample) == nodes:
        break
  return nx.Graph(graph.subgraph(sample))

def _map_color(value):
  cmap = matplotlib.cm.get_cmap('viridis')
  value = (value - value.min()) / (value.max() - value.min())
  rgba = cmap(value)
  return ['#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255)) for r, g, b in rgba[:, :3]]

@op("Visualize graph", view="visualization")
def visualize_graph(graph: Bundle, *, color_nodes_by: ops.NodeAttribute = None):
  nodes = graph.dfs['nodes'].copy()
  if color_nodes_by:
    nodes['color'] = _map_color(nodes[color_nodes_by])
  nodes = nodes.to_records()
  edges = graph.dfs['edges'].drop_duplicates(['source', 'target'])
  edges = edges.to_records()
  pos = nx.spring_layout(graph.to_nx(), iterations=max(1, int(10000/len(nodes))))
  v = {
    'animationDuration': 500,
    'animationEasingUpdate': 'quinticInOut',
    'series': [
      {
        'type': 'graph',
        'roam': True,
        'lineStyle': {
          'color': 'gray',
          'curveness': 0.3,
        },
        'emphasis': {
          'focus': 'adjacency',
          'lineStyle': {
            'width': 10,
          }
        },
        'data': [
          {
            'id': str(n.id),
            'x': float(pos[n.id][0]), 'y': float(pos[n.id][1]),
            # Adjust node size to cover the same area no matter how many nodes there are.
            'symbolSize': 50 / len(nodes) ** 0.5,
            'itemStyle': {'color': n.color} if color_nodes_by else {},
          }
          for n in nodes],
        'links': [
          {'source': str(r.source), 'target': str(r.target)}
          for r in edges],
      },
    ],
  }
  return v

@op("View tables", view="table_view")
def view_tables(bundle: Bundle):
  v = {
    'dataframes': { name: {
      'columns': [str(c) for c in df.columns],
      'data': df.values.tolist(),
    } for name, df in bundle.dfs.items() },
    'relations': bundle.relations,
    'other': bundle.other,
  }
  return v
