from collections import defaultdict
import json
import os
from dfconvert.constants import DEFAULT_ID_LENGTH,DF_CELL_PREFIX, IDENTIFIER_PATTERN, ID_PATTERN
from dfconvert.topological import topological
import ast
#Adds tokens to the ast
import asttokens
import IPython.core
import re
import astor
import sys


cell_template = {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": []
  }



def transform_last_node(csource,cast,exec_count):
    try:
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
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method transform_last_node: %s at %s',str(E), str(exc_tb.tb_lineno))
        return None

def out_assign(csource,cast,exec_count,tags):
    try:
        #This is a special case where an a,3 type assignment happens
        tag_flag = bool([True if exec_count in (tag[:DEFAULT_ID_LENGTH] for tag in tags) else False].count(True))
        if tag_flag:
            if isinstance(cast.tree.body[-1], ast.Assign):
                new_node = ast.Name('Out_' + str(exec_count), ast.Store)
                nnode = cast.tree.body[-1]
                out_targets = nnode.targets.pop()
                nnode.targets.append(new_node)
                ast.fix_missing_locations(nnode)
                start, end = cast.tree.body[-1].first_token.startpos, cast.tree.body[-1].last_token.endpos
                csource = csource[:start] + astor.to_source(nnode) + csource[end:]
            return csource, out_targets
        if len(cast.tree.body) < 1:
            return csource, []
        if isinstance(cast.tree.body[-1],ast.Expr):
            expr_val = cast.tree.body[-1].value
            nnode = ast.Assign([ast.Name('Out_' + str(exec_count), ast.Store)], expr_val)
            ast.fix_missing_locations(nnode)
            start, end = cast.tree.body[-1].first_token.startpos, cast.tree.body[-1].last_token.endpos
            csource = csource[:start] + astor.to_source(nnode) + csource[end:]
        elif isinstance(cast.tree.body[-1],ast.Assign):
            tag_expr = ''
            for tag_id in tags:
                tag_expr += tag_id+'_'+str(exec_count) + ", "
            new_node = ast.Name(tag_expr[:-2], ast.Store)
            nnode = cast.tree.body[-1]
            nnode.targets.append(new_node)
            ast.fix_missing_locations(nnode)
            start, end = cast.tree.body[-1].first_token.startpos, cast.tree.body[-1].last_token.endpos
            csource = csource[:start] + astor.to_source(nnode) + csource[end:]
        return csource, []
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method out_assign: %s at %s',str(E), str(exc_tb.tb_lineno))
        return None, []

def transform_out_refs(csource,cast):
    try:
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
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method transform_out_refs: %s at %s',str(E), str(exc_tb.tb_lineno))
        return None


def clean_cell(csource):
    try:
        new_cell = csource
        #This part is used to replace a$cell_id in particular cell
        pattern = IDENTIFIER_PATTERN + '\$' + ID_PATTERN
        for match in re.finditer(pattern, csource):
            start, end = match.start(), match.end()
            identifier_var, cell_id = csource[start: end].split('$')
            renamed_var = identifier_var + "_" + cell_id
            new_cell = new_cell.replace(csource[start:end], renamed_var)

        #This part is used to replace Out['cell_id'] in particular cell
        csource = new_cell
        pattern2 = 'Out\[[\'\"]' + ID_PATTERN + '[\'\"]\]'
        for match in re.finditer(pattern2, new_cell):
            start, end = match.start(), match.end()
            cell_id = re.findall(ID_PATTERN, new_cell[start:end])[0]
            renamed_var = "Out_"+ cell_id
            csource = csource.replace(new_cell[start:end], renamed_var)

        # This below regex line can be used if we want to remove the cell id after the referenced variable
        # csource = re.sub('\$' + ID_PATTERN, '', cell)
        return csource
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method clean_cell: %s at %s',str(E), str(exc_tb.tb_lineno))
        return None


def count_id_referenced_variables(csource, id_referenced_hmap):
    try:
        pattern = IDENTIFIER_PATTERN + '_' + ID_PATTERN
        for match in re.finditer(pattern, csource):
            renamed_var = csource[match.start():match.end()]
            var_name, var_id = renamed_var[:-(DEFAULT_ID_LENGTH+3)], renamed_var[-(DEFAULT_ID_LENGTH+2):]
            if var_name in id_referenced_hmap.keys():
                id_referenced_hmap[var_name].add(var_id)
            else:
                id_referenced_hmap[var_name] = {var_id}
        return id_referenced_hmap
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method count_id_referenced_variables: %s at %s',str(E), str(exc_tb.tb_lineno))
        return None


def clean_unused_id(code_cells, id_referenced_hmap):
    try:
        pattern = IDENTIFIER_PATTERN + '_' + ID_PATTERN
        for cell_key, cell_val in code_cells.items():
            csource = cell_val[0]['source']
            csource_copy = csource
            for match in re.finditer(pattern, csource):
                identifier_var = csource[match.start(): match.end()][:-(DEFAULT_ID_LENGTH+3)]
                if len(id_referenced_hmap.get(identifier_var, {})) == 1:
                    csource_copy = re.sub("=[ \t]+"+identifier_var + '_' + list(id_referenced_hmap[identifier_var])[0] + "[ \t]+=", "=", csource_copy)
                    csource_copy = re.sub(identifier_var + '_' + list(id_referenced_hmap[identifier_var])[0], identifier_var, csource_copy)
                    csource_ast = ast.parse(csource_copy)
                    csource_ast_targets = csource_ast.body[-1].targets
                    if len(csource_ast_targets) >= 1:
                        pop_index = []
                        for target_i in range(1, len(csource_ast_targets)):
                            remove_multiple_assign = 0
                            if 'elts' in dir(csource_ast_targets[target_i]):
                                for elts_i, elts in enumerate(csource_ast_targets[target_i].elts):
                                    if csource_ast_targets[target_i].elts[elts_i].id != csource_ast.body[-1].targets[target_i-1].elts[elts_i].id:
                                        remove_multiple_assign = 1
                                        break
                                if not remove_multiple_assign:
                                    pop_index.append(target_i-1)
                        for i in sorted(pop_index, reverse=True):
                            csource_ast_targets.pop(i)
                    csource_copy = DF_CELL_PREFIX + str(astor.to_source(csource_ast)).rstrip()

            cell_val[0]['source'] = csource_copy
        return code_cells
    except Exception as E:
        print("Exception for csource: ", csource)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method clean_unused_id: %s at %s',str(E), str(exc_tb.tb_lineno))
        return None



def export_dfpynb(d, in_fname=None, out_fname=None, md_above=True,full_transform=False,out_mode=False):
    try:
        last_code_id = None
        non_code_map = defaultdict(list)
        code_cells = {}
        deps = defaultdict(list)
        out_tags = defaultdict(list)
        refs = {}
        #Maintain a hashmap for variables of the form var_id
        id_referenced_hmap = {}



        def grab_deps(cast,exec_count):
            try:
                for node in ast.walk(cast.tree):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                        out_ref = re.search('([0-9A-Fa-f]{' + str(DEFAULT_ID_LENGTH+2) + '})', node.id)
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
            except Exception as E:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                print('Exception in method grab_deps inside export_dfpynb: %s at %s',str(E), str(exc_tb.tb_lineno))

        #FIXME: Give access to this somewhere
        #This converts comments and strings as well not just in code identifiers
        if (full_transform):
            def transform(line):
                # Changes Out[aaa] and Out["aaa"] to Out_aaa
                return re.sub('Out\[[\"|\']?([0-9A-Fa-f]{' + str(DEFAULT_ID_LENGTH) + '})[\"|\']?\]', r'Out_\1', line)

            out_transformer = IPython.core.inputtransformer.StatelessInputTransformer(transform)


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
                        exec_count = cell['metadata']['dfnotebook']['id'][:DEFAULT_ID_LENGTH+2]
                        cell.metadata.dfkernel_old_id = cell['execution_count']
                    last_code_id = exec_count
                    #Remove cell id concatenated with identifiers and give it name of the format Out_
                    csource = clean_cell(cell['source'])
                    if not isinstance(csource, str):
                        csource = "".join(csource)

                    csource = IPython.core.inputtransformer2.TransformerManager().transform_cell(csource)

                    cast = asttokens.ASTTokens(csource, parse=True)

                    if not full_transform:
                        csource = transform_out_refs(csource,cast)

                    csource = transform_last_node(csource,cast,exec_count)

                    #Grab depedencies from cell
                    grab_deps(cast,exec_count)


                    #Create list of all out_`s
                    valid_tags = []
                    if ('outputs' in cell):
                        for output in cell['outputs']:
                            if ('metadata' in output and 'output_tag' in output['metadata']):
                                valid_tags.append(output['metadata']['output_tag'])



                    cast = asttokens.ASTTokens(csource, parse=True)

                    #Finish up by assigning all final expressions if they still don't have a value
                    csource,out_targets = out_assign(csource,cast,exec_count,valid_tags)

                    cell['source'] = DF_CELL_PREFIX + csource.rstrip()

                    #Maintain a hashmap for var_id to clean the _id format incase it is not assigned 
                    #multiple times in the notebook.
                    id_referenced_hmap = count_id_referenced_variables(csource, id_referenced_hmap)


                    for out_tag in valid_tags:
                        out_tags[exec_count].append(out_tag)
                        refs[out_tag] = exec_count
                    code_cells[exec_count] = [cell]
                    if out_mode:
                        tree = ast.parse(cell['source'])
                        if out_targets:
                            if isinstance(out_targets, ast.Tuple):
                                for j in out_targets.elts:
                                    new_cell = dict(cell_template)
                                    new_cell['source'] = DF_CELL_PREFIX + str(astor.to_source(j)).rstrip()
                                    code_cells[exec_count].append(new_cell)
                        if tree.body and isinstance(tree.body[-1], ast.Assign) and isinstance(tree.body[-1].targets, list):
                            for count, i in enumerate(tree.body[-1].targets):
                                if len(tree.body[-1].targets) == count+1 and isinstance(i,ast.Name) and len(code_cells[exec_count]) == 1:
                                    new_cell = dict(cell_template)
                                    new_cell['source'] = DF_CELL_PREFIX + str(i.id)
                                    code_cells[exec_count].append(new_cell)
                                if isinstance(i, ast.Tuple):
                                    for j in i.elts:
                                        if isinstance(j, ast.Name):
                                            new_cell = dict(cell_template)
                                            new_cell['source'] = DF_CELL_PREFIX + str(j.id)
                                            code_cells[exec_count].append(new_cell)
                    if exec_count not in deps:
                        deps[exec_count] = []
                else:
                    continue
        code_cells = clean_unused_id(code_cells, id_referenced_hmap)

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
            cells.extend(code_cells[cid])

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
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method export_dfpynb: %s at %s',str(E), str(exc_tb.tb_lineno))
        return None

def bundle(handler, model):
    try:
        """Converts the existing IPython Notebook file into a Dataflow Kernel File"""
        notebook_filename = model['path']
        notebook_content = model['content']
        handler.finish('File Exported As: {}'.format(export_dfpynb(notebook_content, notebook_filename)))
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in method bundle: %s at %s',str(E), str(exc_tb.tb_lineno))

if __name__ == "__main__":
    try:
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
    except Exception as E:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('Exception in main: %s at %s',str(E), str(exc_tb.tb_lineno))