'''Boxes for defining PyTorch models.'''
from . import ops
from .ops import Parameter as P

ENV = 'PyTorch model'
def reg(name, inputs=[], outputs=None, params=[]):
  if outputs is None:
    outputs = inputs
  return ops.register_passive_op(
    ENV, name,
    inputs=[ops.Input(name=name, position='bottom', type='tensor') for name in inputs],
    outputs=[ops.Output(name=name, position='top', type='tensor') for name in outputs],
    params=params)
reg('Input: features', outputs=['x'])
reg('Input: graph edges', outputs=['edges'])
reg('Input: label', outputs=['y'])
reg('Input: positive sample', outputs=['x_pos'])
reg('Input: negative sample', outputs=['x_neg'])

reg('Attention', inputs=['q', 'k', 'v'], outputs=['x'])
reg('LayerNorm', inputs=['x'])
reg('Dropout', inputs=['x'], params=[P.basic('p', 0.5)])
reg('Linear', inputs=['x'], params=[P.basic('output_dim', 'same')])
reg('Graph conv', inputs=['x', 'edges'], outputs=['x'],
    params=[P.options('type', ['GCNConv', 'GATConv', 'GATv2Conv', 'SAGEConv'])])
reg('Activation', inputs=['x'],
    params=[P.options('type', ['ReLU', 'LeakyReLU', 'Tanh', 'Mish'])])
reg('Supervised loss', inputs=['x', 'y'], outputs=['loss'])
reg('Triplet loss', inputs=['x', 'x_pos', 'x_neg'], outputs=['loss'])
reg('Optimizer', inputs=['loss'], outputs=[],
    params=[
      P.options('type', ['AdamW', 'Adafactor', 'Adagrad', 'SGD', 'Lion', 'Paged AdamW', 'Galore AdamW']),
      P.basic('lr', 0.001)])

ops.register_area(ENV, 'Repeat', params=[ops.Parameter.basic('times', 1, int)])
