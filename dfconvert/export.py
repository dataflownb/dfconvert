from collections import defaultdict
import json
import os
from dfconvert.topological import topological
import ast
import IPython.core
import re
import astor

DEFAULT_ID_LENGTH = 6

def transform(line):
    #Changes Out[aaa] and Out["aaa"] to Out_aaa
    return re.sub('Out\[[\"|\']?([0-9A-Fa-f]{'+str(DEFAULT_ID_LENGTH)+'})[\"|\']?\]', r'Out_\1',line)

out_transformer = IPython.core.inputtransformer.StatelessInputTransformer(transform)

transformer = IPython.core.inputsplitter.IPythonInputSplitter(physical_line_transforms=[out_transformer])


def export_dfpynb(d, in_fname=None, out_fname=None, md_above=True):
    last_code_id = None
    non_code_map = defaultdict(list)
    code_cells = {}
    deps = defaultdict(list)
    out_tags = defaultdict(list)
    refs = {}

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
                last_code_id = exec_count
                csource = cell['source']
                if not isinstance(csource, str):
                    csource = "".join(csource)
                csource = transformer.transform_cell(csource)
                cast = ast.parse(csource)
                if len(cast.body) > 0 and isinstance(cast.body[-1], ast.Expr):
                    expr_val = cast.body[-1].value
                    if isinstance(expr_val, ast.Tuple):
                        tuple_eles = []
                        named_flag = False
                        for idx, elt in enumerate(expr_val.elts):
                            if isinstance(elt, ast.Name):
                                named_flag = True
                                tuple_eles.append(ast.Name(elt.id, ast.Store))
                            else:
                                tuple_eles.append(ast.Name('Out_' + str(exec_count) + str(idx), ast.Store))
                        if (named_flag):
                            nnode = ast.Assign([ast.Tuple(tuple_eles,ast.Store)], expr_val)
                            ast.fix_missing_locations(nnode)
                            cast.body[-1] = nnode
                for node in ast.walk(cast):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                        out_ref = re.search('(?<=Out_)([0-9A-Fa-f]{'+str(DEFAULT_ID_LENGTH)+'})', node.id)
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
                cell['source'] = astor.to_source(cast).rstrip()
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

    for k in out_tags:
        for tag in out_tags[k]:
            deps[tag] = deps[k]

    topo_deps = list(reversed(topological(deps)))
    while topo_deps:
        cid = topo_deps.pop()
        if cid in refs:
            for tag in out_tags[refs[cid]]:
                if tag in topo_deps:
                    topo_deps.remove(tag)
            cid = refs[cid]
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