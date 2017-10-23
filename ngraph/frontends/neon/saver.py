#!/usr/bin/env python
# ----------------------------------------------------------------------------
# Copyright 2017 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
from __future__ import division, print_function, absolute_import
import six
from contextlib import contextmanager
from contextlib import closing

import ngraph as ng
import ngraph.transformers as ngt
#import SaverFile as sf

class WeightVariablesPass(object):
    def __init__(self, Computation, **kwargs):
        self.values = Computation.values
        super(WeightVariablesPass, self).__init__(**kwargs)

    # collect and return a set of all AssignableTensorOp's      
    def do_pass(self):
        nodes = dict()
        frontier = set(self.values)
        visited = set()

        # gather presistent and trainable AssignableTensorOp's
        def add_op(op):
            if isinstance(op, ng.TensorValueOp):
                tensor = op.tensor
                if isinstance(tensor, ng.AssignableTensorOp):
                    if tensor.is_persistent:
                        if tensor.is_constant:
                            pass
                        elif tensor.is_placeholder:
                            pass
                        else:
                            #print(tensor.name)
                            #print(type(tensor.name))
                            #len_before = len(nodes)
                            try:
                                prev_op = nodes[tensor.name]
                            except KeyError:
                                prev_op = tensor
                                nodes[tensor.name] = tensor
                            assert prev_op == tensor
                            #len_after = len(nodes)
                            #if len_before == len_after:
                            #    print("Rejected " + tensor.name)
                            #else:
                            #    print("Added " + tensor.name)

        while len(frontier) > 0:
            op = frontier.pop()
            add_op(op)
            visited.add(op)
            for arg in op.args:
                if arg not in visited:
                    frontier.add(arg)
            for arg in op.all_deps:
                if arg not in visited:
                    frontier.add(arg)
        return nodes


class Saver(object):
    def __init__(self, Name="Weights", Computation=None, Ops=None,**kwargs):
        self.Name = Name
        self.Computation = Computation
        self.Ops = Ops
        # Traverse computation graph and extract persistent tensors and unique op instance name
        weight_pass = WeightVariablesPass(Computation = self.Computation)
        self.saveVariables = weight_pass.do_pass()
        self.count = len(self.saveVariables)
        #print(self.count)
        #for name, op in self.saveVariables.items():
        #    print(name)
        self.tensors = dict()
        # create save computations
        super(Saver, self).__init__(**kwargs)
        
    def save(self, Transformer=None):
        self.tensors = dict()
        #print()
        for name, op in self.saveVariables.items():
            tensor = Transformer.computation(op)().copy()
            self.tensors[name]=tensor
            #print(name)
            #print(tensor)
    
    def restore(self, Transformer=None, Computation=None):
        def find_ops(tensors, values):
            nodes = dict()
            frontier = set(values)
            visited = set()
            # gather presistent and trainable AssignableTensorOp's
            def add_op(op):
                if isinstance(op, ng.TensorValueOp):
                    tensor = op.tensor
                    if isinstance(tensor, ng.AssignableTensorOp):
                        if tensor.is_persistent:
                            if tensor.is_constant:
                                pass
                            elif tensor.is_placeholder:
                                pass
                            else:
                                #print(tensor.name)
                                try:
                                    nodes[tensor] = tensors[tensor.name]
                                except KeyError:
                                    print("Missing key: "+tensor.name)
                                    pass
            while len(frontier) > 0:
                op = frontier.pop()
                add_op(op)
                visited.add(op)
                for arg in op.args:
                    if arg not in visited:
                        frontier.add(arg)
                for arg in op.all_deps:
                    if arg not in visited:
                        frontier.add(arg)
            #print(self.count)
            #len(nodes) == self.count
            return nodes
        nodes = find_ops(self.tensors, Computation.values)
        for op, value in nodes.items():
            #print(op)
            #print(value)
            Transformer.computation(ng.AssignOp(op, value))()
