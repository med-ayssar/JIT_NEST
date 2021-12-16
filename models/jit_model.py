import copy
from jit.interfaces.jit_interface import JitInterface
from jit.models.model_manager import ModelManager
from collections import defaultdict
import numpy as np


class JitModel:
    def __init__(self, name, number, variables, variations=None):
        self.name = name
        self.count = number
        self.default = variables
        self.nest = None
        self.createParams = {}
        self.attributes = {}

    def __len__(self):
        return self.count

    def addNestModule(self, module):
        self.nest = module

    def create(self):
        if self.nest:
            if self.name not in self.nest.Models():
                self.nest.Install(self.libName)
            self.toNodeCollection()
            return True
        return False

    def setCreateParams(self, *args, **kwargs):
        self.createParams["args"] = args
        self.createParams["kwargs"] = kwargs

    def createNodeCollection(self, moduleName):
        if self.nest:
            if bool(self.createParams):
                args = self.createParams["args"]
                kwargs = self.createParams["kwargs"]
                self.nest.Install(moduleName)
                nodeCollection = self.nest.Create(*args, **kwargs)
                return nodeCollection
            else:
                raise Exception(
                    f"The create parameters in {self.__class__.__name__ } must be set before calling nest.Create function")
        else:
            raise Exception(
                f"The create parameters in {self.__class__.__name__ }.nest is NoneType")

    def get(self, ids, items):
        res = {}
        keys = self.default.keys()
        # select only valid items
        items = list(filter(lambda x: x in keys, items))
        for k in items:
            valuesOfK = []
            for i in ids:
                if k in self.attributes:
                    attribute = self.attributes[k]
                    if i in attribute:
                        value = attribute.getValueOfId(i)
                        valuesOfK.append(value)
                    else:
                        valuesOfK.append(self.default[k])
                else:
                    valuesOfK.append(self.default[k])
            res[k] = valuesOfK
        return res

    def set(self, ids, collection):
        for k, v in collection.items():
            if isinstance(v, (tuple, list)):
                if len(v) != len(ids):
                    raise TypeError(f"Expecting {len(ids)} values in {k}, but got {len(v)}")
                if k in self.attributes:
                    self.attributes[k].update(ids, v)
                else:
                    newAttribute = JitAtribute(attributeName=k, ids=ids, values=v)
                    self.attributes[k] = newAttribute
            else:
                values = [v] * len(ids)
                if k in self.attributes:
                    self.attributes[k].update(ids, values)
                else:
                    newAttribute = JitAtribute(attributeName=k, ids=ids, values=values)
                    self.attributes[k] = newAttribute

    def getKeys(self):
        return list(self.default.keys())

    def toString(self):
        return f"{self.__class__.__name__}(name={self.name})"

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return self.toString()


class JitNode:
    def __init__(self, name="None", first=0, last=0):
        self.name = name
        self.first = first
        self.last = last

    def __len__(self):
        return self.last - self.first

    def toString(self):
        return f"model={self.name}, size={self.last - self.first}, first={self.first}"

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return self.toString()

    def __contains__(self, obj):
        if isinstance(obj, int):
            if obj < self.first and obj >= self.last:
                return False
            return True
        raise NotImplemented("Todo handle other cases in JitNode.__contains__")

    def __eq__(self, other):
        if other is not None:
            if other.name == self.name and self.first == other.first and self.last == other.last:
                return True
        return False

    def __hash__(self):
        return hash(f"{self.name}{self.first}{self.last}")

    def __getitem__(self, key):
        if isinstance(key, int):
            if key >= self.__len__():
                raise IndexError("globalPos out of range")
            return self.__getNodesAt([key])
        elif isinstance(key, slice):
            if key.start is None:
                start = 0
            else:
                start = key.start
                if abs(start) > self.__len__():
                    raise IndexError('slice start value outside of the JitNode')
            if key.stop is None:
                stop = self.__len__()
            else:
                stop = key.stop
                if abs(stop) > self.__len__():
                    raise IndexError('slice stop value outside of the JitNode')
            step = 1 if key.step is None else key.step
            if step < 1:
                raise IndexError('slicing step for JitNode must be strictly positive')
            nodesRange = list(range(start, stop, step))
            slicedElement = self.__getNodesAt(nodesRange)
            return slicedElement
        elif isinstance(key, (list, tuple)):
            if len(key) == 0:
                return JitNode()
            # Must check if elements are bool first, because bool inherits from int
            if all(isinstance(x, bool) for x in key):
                if len(key) != len(self):
                    raise IndexError('Bool globalPos array must be the same length as JitNode')
                npKey = np.array(key, dtype=np.bool)
                npKey = np.argwhere(npKey == True)
            # Checking that elements are not instances of bool too, because bool inherits from int
            elif all(isinstance(x, int) and not isinstance(x, bool) for x in key):
                npKey = np.array(key, dtype=np.uint64)
                if len(np.unique(npKey)) != len(npKey):
                    raise ValueError('All node IDs in a JitNode have to be unique')
            else:
                raise TypeError('Indices must be integers or bools')
            # TODO convert all int to np.uint64
            return self.__getNodesAt(key)

    def __getNodesAt(self, items):
        if all(globalPos < self.__len__() for globalPos in items):
            groups = self.__groupByDistance(items)
            nodes = list()
            for group in groups:
                newNode = JitNode(name=self.name, first=group[0], last=group[1])
                nodes.append(newNode)
            return nodes

    def __groupByDistance(self, items):
        res = []
        if len(items) == 1:
            return [(items[0], items[0] + 1)]
        else:
            first = items[0]
            last = first
            for i in range(1, len(items)):
                if items[i] - last == 1:
                    last = items[i]
                else:
                    res.append((first, last + 1))
                    first = items[i]
                    last = items[i]
            res.append((first, last + 1))
        return res

    def get(self, keys):
        modelsToSelect = range(self.first, self.last)
        jitModel = ModelManager.JitModels[self.name]
        dictOfItems = jitModel.get(ids=modelsToSelect, items=keys)
        return dictOfItems

    def set(self, collection, ids=None):
        if ids is None:
            ids = range(self.first, self.last)
        jitModel = ModelManager.JitModels[self.name]
        jitModel.set(ids=ids, collection=collection)

    def getKeys(self):
        jitModel = ModelManager.JitModels[self.name]
        return jitModel.getKeys()

    def tolist(self):
        return list(range(self.first, self.last))


class JitNodeCollection(JitInterface):
    def __init__(self, nodes):
        if isinstance(nodes, (list, tuple)):
            if len(nodes) > 0:
                if isinstance(nodes[0], int):
                    pass
                elif isinstance(nodes[0], JitNode):
                    self.nodes = nodes
                else:
                    raise TypeError(f"{self.__class__.__name__} accepts only list of int or JitNode")
        elif isinstance(nodes, JitNode):
            self.nodes = [nodes]
        else:
            raise TypeError(f"{self.__class__.__name__} accepts only list of int or JitNode")

    def __len__(self):
        return sum([len(node) for node in self.nodes])

    def __getitem__(self, key):
        if isinstance(key, int):
            if abs(key) >= self.__len__():
                raise IndexError("globalPos out of range")
            actualKey = key if key >= 0 else self.__len__() - abs(key)
            return JitNodeCollection(self.__globalPosing(actualKey))
        elif isinstance(key, slice):
            if key.start is None:
                start = 0
            else:
                start = key.start
                if abs(start) > self.__len__():
                    raise IndexError('slice start value outside of the JitNodeCollection')
            if key.stop is None:
                stop = self.__len__()
            else:
                if key.stop < 0 and abs(key.stop) < self.__len__():
                    stop = self.__len__() - abs(key.stop)
                else:
                    stop = key.stop
                    if abs(stop) >= self.__len__():
                        raise IndexError("slice stop value outside of the JitNodeCollection")
            step = 1 if key.step is None else key.step
            if step < 1:
                raise IndexError('slicing step for JitNodeCollection must be strictly positive')
            ranges = list(range(start, stop, step))
            newNodes = self.__slicing(ranges)
            slicedElement = JitNodeCollection(newNodes)
            return slicedElement
        elif isinstance(key, (list, tuple)):
            newNodes = newNodes = self.__slicing(key)
            return JitNodeCollection(newNodes)
        else:
            raise Exception("Only list, tuple and int are accepted")

    def __globalPosing(self, globalPos):
        blockStartsAt = 0
        blockEndsAt = -1
        for node in self.nodes:
            blockStartsAt = blockEndsAt + 1
            blockEndsAt = blockStartsAt + len(node) - 1
            if globalPos >= blockStartsAt and globalPos <= blockEndsAt:
                relativeglobalPos = globalPos - blockStartsAt
                return node[relativeglobalPos]
        raise IndexError("list out of range")

    def __slicing(self, items):
        dictOfModelNames = {}
        # map globalPos to model name
        for i in items:
            node, relativeglobalPos = self.getNodeAndRelativePos(i)
            dictOfModelNames[i] = (node, relativeglobalPos)

        # group dict by model name
        groups = defaultdict()
        for key, value in sorted(dictOfModelNames.items()):
            if value[0] in groups:
                groups[value[0]].append(value[1])
            else:
                groups[value[0]] = [value[1]]

        # execute each split on each node
        nodes = list()
        for key, value in groups.items():
            newNodes = key[value]
            nodes.extend(newNodes)
        return nodes

    def getNodeAndRelativePos(self, globalPos):
        blockStartsAt = 0
        blockEndsAt = -1
        for node in self.nodes:
            blockStartsAt = blockEndsAt + 1
            blockEndsAt = blockStartsAt + len(node) - 1
            if globalPos >= blockStartsAt and globalPos <= blockEndsAt:
                relativeglobalPos = globalPos - blockStartsAt
                return node, relativeglobalPos
        raise IndexError("list out of range")

    def __setitem__(self, key, value):
        raise TypeError("JitNodeCollection object does not support item assignment")

    def toString(self):
        classNameLength = len(self.__class__.__name__) + 1
        spaces = " " * classNameLength
        instanceToString = f"{self.__class__.__name__}("
        for globalPos, node in enumerate(self.nodes):
            newLineOrClose = ")" if globalPos == len(self.nodes) - 1 else "\n"
            padding = spaces if globalPos > 0 else ""
            instanceToString += f"{padding}{str(node)}{newLineOrClose}"
        return instanceToString

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return self.toString()

    def createNodeCollection(self, moduleName):
        jitModel = ModelManager.JitModels[self.name]
        nodeCollection = jitModel.createNodeCollection(moduleName)
        return nodeCollection

    def setCreateParams(self, *args, **kwargs):
        pass

    def getChildren(self):
        return self.nodes

    def getNumberOfChildren(self):
        return len(self.nodes)

    def getKeys(self):
        res = list()
        for node in self.nodes:
            res.extend(node.getKeys())
        return set(res)

    def getTuples(self, items):
        return [(node.get(items), len(node), node.name) for node in self.nodes]


    def set(self, params=None, **kwargs):
        if kwargs and params:
            raise TypeError("must either provide params or kwargs, but not both.")
        elif kwargs:
            splitCollection = self.projectDict(kwargs)
            for globalPos, node in enumerate(self.nodes):
                node.set(splitCollection[globalPos])

        else:
            if isinstance(params, dict):
                collection = splitCollection = self.projectDict(params)
                for globalPos, node in enumerate(self.nodes):
                    node.set(collection[globalPos])
            elif isinstance(params, list):
                if len(params) == 0:
                    return
                types = set([type(item) for item in params])
                if len(types) != 1 and types.pop().__class__.__name__ != "dict":
                    raise TypeError("params can only contain a dictionary or list of dictionaries")
                if len(params) != len(self):
                    raise ValueError(
                        f"params is a list of dict and has {len(params)} items, but expected are {len(self)}")

                currentNode = 0
                partialLength = len(self.nodes[currentNode])
                for globalPos, dic in enumerate(params):
                    if globalPos < partialLength:
                        self.nodes[currentNode].set(ids=[globalPos], collection=dic)
                    else:
                        currentNode += 1
                        self.nodes[currentNode].set(ids=[globalPos], collection=dic)
                        partialLength += len(self.nodes[currentNode])

    def tolist(self):
        allIds = []
        for node in self.nodes:
            allIds.extend(node.tolist())
        return allIds


class JitAtribute:
    def __init__(self, attributeName, ids, values):
        self.attributeName = attributeName
        if len(ids) != len(values):
            raise ValueError(f"ids:{len(ids)} != values: {len(values)}: both ids and values must be of the same size")
        if isinstance(ids, range):
            self.modelIds = list(ids)
        elif isinstance(ids, list):
            self.modelIds = ids
        else:
            raise TypeError(f"{self.__class__.__name__} accepts only range or list types for ids")
        self.values = values

    def __contains__(self, other):
        if isinstance(other, str):
            return self.attributeName == other
        if isinstance(other, int):
            return other in self.modelIds
        return False

    def getValueOfId(self, modeId):
        if modeId in self:
            globalPos = self.modelIds.globalPos(modeId)
            value = self.values[globalPos]
            if value.__class__.__name__ == "Parameter":
                value = value.GetValue()
                self.values[globalPos] = value
            return value
        raise ValueError(f"the model id {modeId} is not in {str(self)}")

    def toString(self):
        return f"{self.__class__.__name__}(attribute={self.attributeName})"

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return self.toString()

    def update(self, ids, values):
        if len(ids) != len(values):
            raise ValueError(f"ids:{len(ids)} != values: {len(values)}: both ids and values must be of the same size")

        for pos, localId in enumerate(ids):
            if localId in self:
                index = self.modelIds.index(localId)
                self.values[index] = values[pos]
            else:
                self.modelIds.append(localId)
                self.values.append(values[pos])