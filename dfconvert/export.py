from collections import defaultdict
import json
import redbaron
import os
from dfconvert.topological import topological

DEFAULT_ID_LENGTH = 6

def export_dfpynb(d, in_fname=None, out_fname=None, md_above=True):
    last_code_id = None
    non_code_map = defaultdict(list)
    code_cells = {}
    deps = defaultdict(list)

    if md_above:
        # reverse the cells
        d["cells"].reverse()

    for count, cell in enumerate(d['cells']):
        if cell['cell_type'] != "code":
            # keep non-code cells above or below code cell
            non_code_map[last_code_id].append(cell)
        else:
            exec_count = hex(cell['execution_count'])[2:].zfill(DEFAULT_ID_LENGTH)
            last_code_id = exec_count
            csource = cell['source']
            if isinstance(csource, str):
                csource = csource.rstrip().split('\n')
            magics_lines = {}
            code_lines = {}
            for idx, line in enumerate(csource):
                # this was to prevent index errors
                if not (len(line)):
                    continue
                # keep magics lines out of rb
                if line.startswith('%') or line.startswith('!'):
                    magics_lines[idx] = line + '\n'
                else:
                    code_lines[idx] = line.rstrip()

            red = redbaron.RedBaron("\n".join([v for (_, v) in sorted(code_lines.items())]))
            for node in red.find_all("atomtrailers"):
                if (node[0].type == 'name' and node[0].value == 'Out' and
                    node[1].type == 'getitem'):
                    ref_id = node[1].value.value[1:-1]
                    deps[exec_count].append(ref_id)
                    if len(node) > 2:
                        node[0].replace("Out_{}".format(ref_id))
                        node.remove(node[1])
                    else:
                        node.replace("Out_{}".format(ref_id))
            if len(red.node_list) > 0:
                red.node_list[-1].replace('Out_{} = {}'.format(exec_count,
                                                               red.node_list[-1]))
                red.node_list[-1].insert_after("Out_{}".format(exec_count))
                code_lines[max(code_lines)+1] = None # value doesn't matter

            # potential extra line from last output expression
            out_code_lines = dict(zip(sorted(code_lines.keys()),
                                      [x + '\n' for x in red.dumps().split('\n')]))
            # put back magic cells
            lines = [(out_code_lines[i] if i in out_code_lines else magics_lines[i])
                     for i in range(max([max(out_code_lines, default=-1),
                                         max(magics_lines, default=-1)])+1)]
            cell['source'] = ["### Out_{} ###\n".format(exec_count),] + lines

            # clean up extra newline
            if len(cell['source']) > 0:
                cell['source'][-1] = cell['source'][-1][:-1]

            code_cells[exec_count] = cell

    cells = []
    cells.extend(non_code_map[None])
    for cid in reversed(topological(deps)):
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