from collections import defaultdict
import json
import os
from dfconvert.constants import DEFAULT_ID_LENGTH,DF_CELL_PREFIX,IPY_CELL_PREFIX
from dfconvert.topological import topological
import ast
#Adds tokens to the ast
import asttokens
import IPython.core
import re
import astor
import sys


transformers = []

def remove_comment(line):
    #Removes comments from export.py
    return line.replace(IPY_CELL_PREFIX,'')


comment_remover = IPython.core.inputtransformer.StatelessInputTransformer(remove_comment)
transformers.append(comment_remover)


def transform_last_node(csource,cast,exec_count):
    if isinstance(exec_count,int):
        exec_count = ("{0:#0{1}x}".format(int(exec_count),8))[2:]
    if len(cast.tree.body) > 0 and isinstance(cast.tree.body[-1], ast.Expr):
        expr_val = cast.tree.body[-1].value
        if isinstance(expr_val, ast.Tuple):
            tuple_eles = []
            named_flag = False
            out_exists = False
            for idx, elt in enumerate(expr_val.elts):
                if isinstance(elt, ast.Name):
                    named_flag = True
                    tuple_eles.append(ast.Name(elt.id, ast.Store))
                else:
                    out_exists = True
                    tuple_eles.append(ast.Name('Out_' + str(exec_count) + '['+str(idx)+']', ast.Store))
            if (named_flag):
                nnode = ast.Assign([ast.Tuple(tuple_eles, ast.Store)], expr_val)
                out_assign = 'Out_'+str(exec_count)+' = []\n' if out_exists else ''
                ast.fix_missing_locations(nnode)
                start,end = cast.tree.body[-1].first_token.startpos, cast.tree.body[-1].last_token.endpos
                csource = csource[:start] + out_assign + astor.to_source(nnode) + csource[end:]
    return csource

def transform_out_refs(csource,cast):
    offset = 0
    #Depth first traversal otherwise offset won't be accurate
    for node in asttokens.util.walk(cast.tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'Out':
            start, end = node.first_token.startpos + offset, node.last_token.endpos + offset
            new_id = re.sub('Out\[[\"|\']?([0-9A-Fa-f]{' + str(DEFAULT_ID_LENGTH) + '})[\"|\']?\]', r'Out_\1',
                            csource[start:end])
            csource = csource[:start] + new_id + csource[end:]
            offset = offset + (len(new_id) - (end - start))
    return csource


def export_dfpynb(d, in_fname=None, out_fname=None, md_above=True,full_transform=False):
    last_code_id = None
    non_code_map = defaultdict(list)
    code_cells = {}
    deps = defaultdict(list)
    out_tags = defaultdict(list)
    refs = {}


    def grab_deps(cast,exec_count):
        for node in ast.walk(cast.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                out_ref = re.search('(?<=Out_)([0-9A-Fa-f]{' + str(DEFAULT_ID_LENGTH) + '})', node.id)
                if out_ref:
                    deps[exec_count].append(out_ref.group(0))
                else:
                    deps[exec_count].append(node.id)
            # Grab magic lines and perform our own parsing
            elif isinstance(node, ast.Call) and isinstance(node.func,
                                                           ast.Attribute) and node.func.attr == 'run_line_magic' and node.args:
                args = node.args
                if args[0].s == 'split_out':
                    for subnode in ast.walk(ast.parse(args[1].s)):
                        if isinstance(subnode, ast.Name):
                            deps[exec_count].append(subnode.id)

    #FIXME: Give access to this somewhere
    #This converts comments and strings as well not just in code identifiers
    if (full_transform):
        def transform(line):
            # Changes Out[aaa] and Out["aaa"] to Out_aaa
            return re.sub('Out\[[\"|\']?([0-9A-Fa-f]{' + str(DEFAULT_ID_LENGTH) + '})[\"|\']?\]', r'Out_\1', line)

        out_transformer = IPython.core.inputtransformer.StatelessInputTransformer(transform)
        transformers.append(out_transformer)

    transformer = IPython.core.inputsplitter.IPythonInputSplitter(physical_line_transforms=transformers)

    if md_above:
        # reverse the cells
        d["cells"].reverse()

    for count, cell in enumerate(d['cells']):
        if cell['cell_type'] != "code":
            # keep non-code cells above or below code cell
            non_code_map[last_code_id].append(cell)
        else:
            # This condition should never happen but incase it does
            # we want to ignore cells without any execution count
            if ('execution_count' in cell):
                exec_count = hex(cell['execution_count'])[2:].zfill(DEFAULT_ID_LENGTH)
                if 'metadata' in cell:
                    cell.metadata.dfkernel_old_id = cell['execution_count']
                last_code_id = exec_count
                csource = cell['source']
                if not isinstance(csource, str):
                    csource = "".join(csource)
                csource = transformer.transform_cell(csource)
                cast = asttokens.ASTTokens(csource, parse=True)


                if not full_transform:
                    csource = transform_out_refs(csource,cast)

                csource = transform_last_node(csource,cast,exec_count)

                #Grab depedencies from cell
                grab_deps(cast,exec_count)

                cell['source'] = DF_CELL_PREFIX + csource.rstrip()

                if ('outputs' in cell):
                    for output in cell['outputs']:
                        if ('metadata' in output and 'output_tag' in output['metadata']):
                            out_tag = output['metadata']['output_tag']
                            out_tags[exec_count].append(out_tag)
                            refs[out_tag] = exec_count
                code_cells[exec_count] = cell
            else:
                continue

    cells = []
    cells.extend(non_code_map[None])

    # Remove all namenodes that aren't output tags
    out_tag_set = sorted({x for v in out_tags.values() for x in v})
    valid_keys = out_tag_set + list(deps)

    for node in deps:
        #Ensure that keys are valid NameNode refs and then
        #Ensure that we don't have circular dependencies where a cell depends on itself
        deps[node] = list(set(deps[node]).intersection(valid_keys).difference(set(out_tags[node])))

    #Convert all tag references into dependency references
    for tag in deps:
        for idx, dep in enumerate(deps[tag]):
            if dep in refs:
                deps[tag][idx] = refs[dep]

    topo_deps = list(topological(deps))
    while topo_deps:
        cid = topo_deps.pop()
        cells.extend(non_code_map[cid])
        cells.append(code_cells[cid])

    d['cells'] = cells

    # change the kernelspec
    # FIXME what if this metadata doesn't exist?
    d["metadata"]["kernelspec"]["display_name"] = "Python 3"
    d["metadata"]["kernelspec"]["name"] = "python3"

    if out_fname is None:
        if in_fname is not None:
            dir_name, base_name = os.path.split(os.path.abspath(in_fname))
            base, ext = os.path.splitext(base_name)
            out_fname = os.path.join(dir_name, base + '_ipy' + ext)

    if out_fname is None:
        json.dump(d, sys.stdout, indent=4)
    else:
        with open(out_fname, 'w') as f:
            json.dump(d, f, indent=4)

    return out_fname

def bundle(handler, model):
    """Converts the existing IPython Notebook file into a Dataflow Kernel File"""
    notebook_filename = model['path']
    notebook_content = model['content']
    handler.finish('File Exported As: {}'.format(export_dfpynb(notebook_content, notebook_filename)))

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python {} <dfnb filename> [out filename]".format(sys.argv[0]))
        sys.exit(1)

    out_fname = None
    if len(sys.argv) > 2:
        out_fname = sys.argv[2]
    with open(sys.argv[1], "r") as f:
        d = json.load(f)
        export_dfpynb(d, sys.argv[1])