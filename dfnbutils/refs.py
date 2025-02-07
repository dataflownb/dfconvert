import ast
import re

import tokenize
from io import StringIO
from collections import defaultdict
from operator import attrgetter
import json
from typing import Any
import itertools
import re

class DataflowRef:
    __slots__ = ['start_pos','end_pos','name','cell_id','cell_tag','ref_qualifier','input_tags']

    def __init__(self, start_pos=None, end_pos=None, name=None, cell_id=None, cell_tag=None, ref_qualifier=None, input_tags=None):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.name = name
        self.cell_id = cell_id
        self.cell_tag = cell_tag
        self.ref_qualifier = ref_qualifier
        self.input_tags = input_tags
        
    @classmethod
    def fromstrstr(cls, s):
        return cls(**json.loads(json.loads(s)))

    def strstr(self):
        return json.dumps(json.dumps({
            'name': self.name,
            'cell_id': self.cell_id,
            'cell_tag': self.cell_tag,
            'ref_qualifier': self.ref_qualifier
        }))

    def __str__(self):
        qualifier = self.ref_qualifier if self.ref_qualifier is not None else ''
        
        if self.cell_id == '@default_ref':
            return f'{self.name}'
        
        reversed_input_tags = {id: tag for tag, id in self.input_tags.items()}
        if self.cell_id in reversed_input_tags:
            return f'{self.name}${qualifier}{reversed_input_tags[self.cell_id]}'

        return f'{self.name}${qualifier}{self.cell_id}'

    def __repr__(self):
        return f'DataflowRef({self.start_pos}, {self.end_pos}, {self.name}, {self.cell_id}, {self.cell_tag}, {self.ref_qualifier})'

def identifier_replacer(ref):
    return f"__dfvar__[{ref.strstr()}]"

def ref_replacer(ref):
    # FIXME deal with tags and qualifiers
    return f"_oh['{ref.cell_id}']['{ref.name}']"

def dollar_replacer(ref):
    return str(ref)

def update_refs(refs, dataflow_state, execution_count, input_tags):
    for ref in refs:
        if ref.ref_qualifier == '^' or (not ref.cell_tag and not ref.cell_id):
            # get latest cell_id
            # FIXME is_external_link needs to be updated to find
            # the external link that is not the current uuid...
            if dataflow_state.has_external_link(ref.name, execution_count):
                ref.cell_id = dataflow_state.get_external_link(ref.name, execution_count)
            # print("ASSIGNING CELL_ID:", ref.cell_id)

        if ref.cell_tag is not None:
            if ref.cell_tag not in input_tags:
                if ref.ref_qualifier == '^':
                    ref.cell_tag = None
                else:
                    pass
                    # raise ValueError(f"Cell with tag '{ref.cell_tag}' does not exist")
            else:
                if ref.ref_qualifier == '=' and ref.cell_id and ref.cell_id != input_tags[ref.cell_tag]:
                    pass
                    # raise ValueError(f"Tag '{ref.cell_tag}' no longer references cell '{ref.cell_id}'. Consider removing the = qualifier.")
                else:
                    if ref.cell_id and ref.cell_id != input_tags[ref.cell_tag]:
                        if ref.ref_qualifier == '^':
                            ref.cell_tag = None
                        else:
                            ref.cell_id = input_tags[ref.cell_tag]
        # print("REF OUT:", ref)

def run_replacer(s, refs, replace_f):
    code_arr = s.splitlines()
    for ref in sorted(refs, key=attrgetter('end_pos'), reverse=True):
        # FIXME improve error handling
        assert ref.start_pos[0] == ref.end_pos[0]

        line = code_arr[ref.start_pos[0] - 1]
        code_arr[ref.start_pos[0] - 1] = \
            line[:ref.start_pos[1]] + replace_f(ref) + line[ref.end_pos[1]:]
    return '\n'.join(code_arr)    

def ground_refs(s, dataflow_state, execution_count, replace_f=ref_replacer, input_tags={}, output_tags={}, cell_refs = {}, reversion = False, display_code = False):
    updates = []

    class DataflowLinker(ast.NodeVisitor):
        def __init__(self):
            super().__init__()
            self.scope = [set()]
            self.updates = []

        def visit_Name(self, node):
            # FIXME what to do with del?
            if isinstance(node.ctx, ast.Store):
                # print("STORE", name.id, file=sys.__stdout__)
                self.scope[-1].add(node.id)
            elif isinstance(node.ctx, ast.Del):
                self.scope[-1].discard(node.id)
            elif isinstance(node.ctx, ast.Load) and all(node.id not in s for s in self.scope):
                output_tags_exists = output_tags.get(node.id)
                is_variable_exported_only_once = output_tags_exists and len(output_tags[node.id]) == 1
                is_variable_ref_exist_in_cell_refs = cell_refs.get(node.id) and len(cell_refs[node.id]) == 1
                
                if not reversion:
                    if dataflow_state.has_external_link(node.id, execution_count):
                        cell_id = dataflow_state.get_external_link(node.id, execution_count)

                        if not (display_code and is_variable_exported_only_once and cell_id in output_tags[node.id]):
                            self._create_dataflow_ref(node, cell_id)

                    elif (is_variable_exported_only_once or is_variable_ref_exist_in_cell_refs):
                        cell_id = list(output_tags[node.id])[0] if output_tags.get(node.id) else list(cell_refs[node.id])[0]
                        self._create_dataflow_ref(node, cell_id)

                else: # reversion case
                    
                    if is_variable_ref_exist_in_cell_refs: 
                        
                        # first exported variable's cell id
                        cell_id = list(cell_refs[node.id])[0]

                        is_variable_deleted = not output_tags_exists
                        is_variable_exported_second_time = output_tags_exists and len(output_tags[node.id]) == 2 and cell_id in output_tags[node.id]
                        is_variable_UUID_changed = output_tags_exists and cell_id not in output_tags[node.id] 

                        if is_variable_exported_second_time or is_variable_deleted or is_variable_UUID_changed:
                            self._create_dataflow_ref(node, cell_id)

            self.generic_visit(node)

        def _create_dataflow_ref(self, node, cell_id):
            ref = DataflowRef(
                start_pos=(node.lineno, node.col_offset),
                end_pos=(node.end_lineno, node.end_col_offset),
                name=node.id,
                cell_id=cell_id
            )
            self.updates.append(ref)

        # need to make sure we visit right side before left!
        def visit_Assign(self, node):
            self.visit(node.value)
            for target in node.targets:
                self.visit(target)

        # FIXME we should rewrite augmented assignments to
        # deal with c += 12 where c is referencing another
        # cell's output
        def visit_AugAssign(self, node):
            self.visit(node.value)
            self.visit(node.target)

        def visit_AnnAssign(self, node):
            if node.value:
                self.visit(node.value)
            self.visit(node.annotation)
            self.visit(node.target)

        def visit_Subscript(self, node):
            if (reversion and isinstance(node.value, ast.Name)
                and node.value.id == '__dfvar__'):
                # print("NODE SLICE VALUE:", node.slice.value)
                ref_data = json.loads(node.slice.value)
                if ref_data.get('name') and all(ref_data['name'] not in s for s in self.scope):
                    if (output_tags.get(ref_data['name']) and len(output_tags[ref_data['name']]) == 1 and
                        ref_data['cell_id'] in output_tags[ref_data['name']]
                        and len(cell_refs[ref_data['name']]) == 1):  # last line added to resolve ambiguity when multiple refs exists
                        ref_data['cell_id']='@default_ref'
                        ref_data['cell_tag'] = None
                        ref = DataflowRef(
                            start_pos=(node.lineno, node.col_offset),
                            end_pos=(node.end_lineno, node.end_col_offset),
                            **ref_data  # Unpack the updated ref_data
                        )
                        self.updates.append(ref)

            self.generic_visit(node)
        
        def process_function(self, node, add_name=True):
            if add_name:
                self.scope[-1].add(node.name)
            func_args = set()
            for a in itertools.chain(node.args.args, node.args.posonlyargs, node.args.kwonlyargs):
                func_args.add(a.arg)
            self.scope.append(func_args)
            retval = self.generic_visit(node)
            self.scope.pop()
            return retval

        def visit_FunctionDef(self, node):
            return self.process_function(node)

        def visit_AsyncFunctionDef(self, node):
            return self.process_function(node)

        def visit_Lambda(self, node):
            return self.process_function(node, add_name=False)

        def visit_ClassDef(self, node):
            self.scope[-1].add(node.name)
            self.scope.append(set())
            retval = self.generic_visit(node)
            self.scope.pop()
            return retval

        def process_import(self, node):
            for alias in node.names:
                if alias.asname:
                    self.scope[-1].add(alias.asname)
                else:
                    self.scope[-1].add(alias.name)
            self.generic_visit(node)

        def visit_Import(self, node):
            self.process_import(node)

        def visit_ImportFrom(self, node):
            self.process_import(node)

        def visit_ExceptHandler(self, node):
            self.scope.append(set())
            if node.name:
                self.scope[-1].add(node.name)
            retval = self.generic_visit(node)
            self.scope.pop()
            return retval

        def process_elt_comp(self, node):
            self.scope.append(set())
            for generator in node.generators:
                self.visit(generator)
            self.visit(node.elt)
            self.scope.pop()

        def visit_ListComp(self, node):
            self.process_elt_comp(node)

        def visit_SetComp(self, node):
            self.process_elt_comp(node)

        def visit_GeneratorExp(self, node):
            self.process_elt_comp(node)

        def visit_DictComp(self, node):
            self.scope.append(set())
            for generator in node.generators:
                self.visit(generator)
            self.visit(node.key)
            self.visit(node.value)
            self.scope.pop()

        def visit_NamedExpr(self, node):
            self.visit(node.value)
            self.visit(node.target)

    tree = ast.parse(s)
    linker = DataflowLinker()
    linker.visit(tree)

    update_refs(linker.updates, dataflow_state, execution_count, input_tags)
    
    return run_replacer(s, linker.updates, replace_f)

def convert_dollar(s, dataflow_state, execution_count, replace_f=ref_replacer, input_tags={}, reversion = False, tag_refs = {}):
    def positions_mesh(end, start):
        return end[0] == start[0] and end[1] == start[1]

    updates = []
    s_stream = StringIO(s)

    dollar_pos = None
    var_name = None
    ref_qualifier = None
    cell_ref = ""
    last_token = None
    just_started = False

    """
    References can look like:
      * df or df$tag or df$f1f1f1 or df$tag$f1f1f1
      * df$^ or df$^f1f1f1 or df$^tag or df$^tag$f1f1f1
      * df$= or df$=f1f1f1 or df$=tag or df$=tag$f1f1f1
      * df$~tag or df$~tag$f1f1f1

    FIXME Do we need tilde?
    """
    for t in tokenize.generate_tokens(s_stream.readline):
        if t.string == '$':
            if dollar_pos is not None and t.end[1] - t.start[1] == 1 and positions_mesh(dollar_pos[1], t.start):
                # second $ sign for tags
                cell_ref += t.string
                dollar_pos = dollar_pos[0], t.end
                just_started = False
            elif last_token is not None and positions_mesh(last_token.end, t.start):
                dollar_pos = last_token.start, t.end
                var_name = last_token.string
                just_started = True
        elif dollar_pos is not None:
            if just_started and t.string in ['^','=','~'] and t.end[1] - t.start[1] == 1 and positions_mesh(dollar_pos[1], t.start):
                ref_qualifier = t.string
                dollar_pos = dollar_pos[0], t.end
                just_started = False
            elif t.type == 2 and positions_mesh(dollar_pos[1], t.start): # NUMBER
                t_string = t.string
                t_end = t.end
                while (
                    not re.match(r"[0-9a-f]+$", t_string)
                    and (t_end[0] > t.start[0] or t_end[1] > t.start[1])
                    and t_end[1] > 0
                ):
                    t_string = t_string[:-1]
                    t_end = (t_end[0], t_end[1] - 1)
                cell_ref += t_string
                dollar_pos = dollar_pos[0], t_end
                just_started = False
            elif t.type == 1 and positions_mesh(dollar_pos[1], t.start): # NAME
                cell_ref += t.string
                dollar_pos = dollar_pos[0], t.end                
                just_started = False
            else: # DONE
                if '$' in cell_ref:
                    cell_tag, cell_id = cell_ref.split('$')
                elif cell_ref in input_tags:
                    cell_tag = cell_ref
                    cell_id = input_tags[cell_ref]
                else:
                    cell_tag = None
                    cell_id = cell_ref

                if reversion and tag_refs:
                    if cell_id in tag_refs and cell_id not in input_tags:
                        cell_id = tag_refs[cell_id] 

                updates.append(DataflowRef(
                    start_pos=dollar_pos[0],
                    end_pos=dollar_pos[1],
                    name=var_name,
                    cell_id=cell_id,
                    cell_tag=cell_tag,
                    ref_qualifier=ref_qualifier)
                )
                dollar_pos = None
                var_name = None
                ref_qualifier = None
                cell_ref = ""
                last_token = None
                just_started = False
                if t.type == 1: # NAME
                    last_token = t
        elif t.type == 1: # NAME
            last_token = t

    # print("UPDATES:", updates)
    update_refs(updates, dataflow_state, execution_count, input_tags)
    return run_replacer(s, updates, replace_f)

def convert_identifier(s, replace_f=ref_replacer, input_tags={}):
    class DataflowReplacer(ast.NodeVisitor):
        def __init__(self):
            self.updates = []
            super().__init__()

        def visit_Subscript(self, node):
            if (isinstance(node.value, ast.Name)
                and node.value.id == '__dfvar__'):
                # print("NODE SLICE VALUE:", node.slice.value)
                ref = DataflowRef(
                    start_pos=(node.lineno, node.col_offset),
                    end_pos=(node.end_lineno, node.end_col_offset),
                    **json.loads(node.slice.value), 
                    input_tags=input_tags
                )
            
                self.updates.append(ref)
            self.generic_visit(node)

    tree = ast.parse(s)
    linker = DataflowReplacer()
    linker.visit(tree)

    return run_replacer(s, linker.updates, replace_f)

def get_references(s):
    class GetReferences(ast.NodeVisitor):
        def visit_Subscript(self, node):
            if (isinstance(node.value, ast.Name)
                and node.value.id == '__dfvar__'):
                node_value = json.loads(node.slice.value)
                if not identifier_refs.get(node_value["cell_id"]):
                    identifier_refs[node_value["cell_id"]] = set()
                identifier_refs[node_value["cell_id"]].add(node_value["name"])
                    
            self.generic_visit(node)

    identifier_refs = {}
    tree = ast.parse(s)
    linker = GetReferences()
    linker.visit(tree)

    return identifier_refs