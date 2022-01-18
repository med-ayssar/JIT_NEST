from jit.models.model_manager import ModelManager
from jit.models.jit_model import JitModel, JitNode
from jit.utils.thread_manager import JitThread
from jit.models.model_query import ModelQuery
import copy


class CopyModel:
    def __init__(self, old, new, newDefault):
        self.oldModelName = old
        self.newModelName = new
        self.newDefault = newDefault

    def copyModel(self):
        if self.oldModelName in ModelManager.JitModels:
            self.handleJitModel()
        elif self.oldModelName in ModelManager.Nest.Models():
            self.handleBuiltIn()
        else:
            # initiate search for the model
            model_query = ModelQuery(self.oldModelName)
            # create the model handle (nestml or lib)
            self.modelHandle = model_query.getModelHandle()
            if self.modelHandle.is_lib:
                self.handleExternLib()
            else:
                self.handleNestml()

    def handleBuiltIn(self):
        ModelManager.Nest.CopyModel(
            self.oldModelName, self.newModelName, self.newDefault
        )

    def handleJitModel(self):
        oldModel = ModelManager.JitModels[self.oldModelName]
        newModel = JitModel(
            name=self.newModelName, variables=copy.deepcopy(oldModel.default)
        )
        newModel.root = self.oldModelName
        oldModel.alias.append(self.newModelName)
        if self.newDefault:
            newModel.default.update(self.newDefault)
        ModelManager.JitModels[self.newModelName] = newModel

    def handleExternLib(self):
        # add module to path
        self.modelHandle.add_module_to_path()
        # install the module
        ModelManager.Nest.Install(self.modelHandle.moduleName)
        # rest like handleBuitIn
        self.handleBuiltIn()

    def handleNestml(self):
        # extract structural information from the model
        modelDeclatedVars = self.modelHandle.getModelDeclaredVariables()
        # create the JitModel holding the model strucutre
        jitModel = JitModel(name=self.oldModelName, variables=modelDeclatedVars)
        # create the first JitNode referring to the JitModel instance
        ModelManager.JitModels[self.oldModelName] = jitModel
        self.handleJitModel()

        ModelManager.add_module_to_install(
            self.modelHandle.neuron, self.modelHandle.add_module_to_path
        )

        createThread = JitThread(self.oldModelName, self.modelHandle.build)
        ModelManager.Threads.append(createThread)
        # start thread
        createThread.start()


def models(mtype, sel=None):
    jitModels = list(ModelManager.JitModels.keys())
    nestModels = ModelManager.Nest.Models(mtype, sel)
    return jitModels + list(nestModels)


def printNodes():
    toPrint = []
    for ncp in ModelManager.NodeCollectionProxy:
        if ncp.jitNodeCollection:
            name = ncp.jitNodeCollection.nodes[0].name
            ids = ncp.tolist()
            first = ids[0]
            last = ids[-1]
            __insert(toPrint, name, first, last)

        else:
            name = ncp.get("model")
            name = name["model"][0] if isinstance(name, dict) else name
            ids = ncp.tolist()
            first = ids[0]
            last = ids[-1]
            __insert(toPrint, name, first, last)

    toPrint = list(
        map(
            lambda item: f"{item[1]} ... {item[2]}\t{item[0]}"
            if item[2] - item[1] > 1
            else f"{item[1]}\t{item[0]}",
            toPrint,
        )
    )

    toPrint = "\n".join(toPrint)
    print(toPrint)


def __insert(arr, name, first, last):
    if len(arr) > 0:
        lastSeenElement = arr[-1]
        if lastSeenElement[0] == name:
            arr[-1][2] = last
        else:
            arr.append([name, first, last])
    else:
        arr.append([name, first, last])