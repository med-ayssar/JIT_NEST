from xml.sax.handler import DTDHandler
from pynestml.codegeneration.nest_cpp_printer import NestCppPrinter
from jinja2 import Environment, BaseLoader


class JitModelParser:
    modelTemplate = """
    #include <cmath>
    class {{name}} 
    {   
    {%- filter indent(1) %}
        private:
            {%- filter indent(2) %}
                {{state}}
                {{parameters}}
            {%- endfilter %}
        public:
            {%- filter indent(2) %}
                {%- for callable in callables %}
                    {{callable}}
                {%- endfor %}

        inline {{name}} (): {%- if hasParam %}P_(){%- endif %}{%- if hasParam and hasState %},{%- endif %} {%- if hasState %} S_(){%- endif %}  
            {
                {{declarations}}
            }
            {%- endfilter %}
        {%- endfilter %}
    }
    

    

   


    """

    def __init__(self, node):
        self.name = node.get_name()
        self.stateBlocks = node.get_state_blocks()
        self.paramBlocks = node.get_parameter_blocks()
        hasParam = len(self.paramBlocks.declarations) > 0
        hasState = len(self.stateBlocks.declarations) > 0
        self.printer = NestCppPrinter(node)
        self.data = {"name": self.name, "hasParam": hasParam, "hasState": hasState}
        self.setCallables()
        self.setStructs()
        self.setDeclarations()

    def getCppCode(self):
        template = Environment(loader=BaseLoader).from_string(JitModelParser.modelTemplate)
        return template.render(self.data)

    def setCallables(self):
        # get all decalred fuctions
        callables = []
        declared_functions = self.printer.print_functions()
        callables.extend(declared_functions.values())

        # get all Getter/Setter for each block
        callables.append(self.printer.print_getter_setter(["State", "Parameters"]))

        self.data["callables"] = callables

    def setStructs(self):
        stateStruct = self.printer.print_state_struct()
        self.data["state"] = stateStruct

        paramStruct = self.printer.print_parameters_struct()
        self.data["parameters"] = paramStruct

    def setDeclarations(self):
        # decs = []
        # stateDecs = self.printer.print_declarations(self.sateBlocks)
        # decs.extend(stateDecs.values())

        # paramDecs = self.printer.print_declarations(self.paramBlocks)
        # decs.extend(paramDecs.values())
        decs = self.printer.print_default_constructorBody()
        print(decs)
        self.data["declarations"] = decs

    def toCPP(self, outputPath=None):
        cppCode = self.getCppCode()

        if outputPath is None:
            import os
            outputPath = os.path.join(os.getcwd(), f"{self.name}.cpp")

        with open(outputPath, "w+") as cpp:
            cpp.write(cppCode)