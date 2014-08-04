from StringIO import StringIO
from lxml import etree
import re

from oii.scope import Scope
from oii.utils import coalesce

# foo.bar corresponds to an XPath of /namespace[@name='foo']/namespace[@name='bar']
def find_names(e):
    def descend(e,namespace=[]):
        if e.tag=='namespace':
            sub_ns = namespace + [e.get('name')]
            yield sub_ns, e
            for se in e.findall('namespace'):
                for name, name_e in descend(se,namespace=sub_ns):
                    yield name, name_e
    return dict(('.'.join(n),ne) for n, ne in descend(e.getroot()))

# substitute patterns like ${varname} for their values given
# bindings = a dict of varname->value
# e.g., interpolate('${x}_${blaz}',{'x':'7','bork':'z','blaz':'quux'}) -> '7_quux'
def interpolate(template,scope):
   s = StringIO()
   pattern = re.compile(r'([^\$]*)(\$\{([a-zA-Z0-9_]+)\})')
   end = 0
   for m in re.finditer(pattern,template):
      end = m.end()
      (plain, expr, key) = m.groups()
      s.write(plain)
      try:
         s.write(scope[key])
      except:
         s.write(expr)
   s.write(template[end:])
   return s.getvalue()

# evaluate a block of expressions using recursive descent to generate and filter
# solutions a la Prolog
def evaluate_block(exprs,bindings=Scope(),global_namespace={}):
    # recurrence expression establishes an inner scope and evaluates
    # the remaining expressions (which will yield solutions to the head expression)
    def recur(exprs,bindings=Scope(),inner_bindings={}):
        return evaluate_block(exprs[1:],bindings.enclose(**inner_bindings),global_namespace)
    # terminal case; we have arrived at the end of the block with a solution, so yield it
    if len(exprs)==0:
        yield bindings.flatten()
        return
    # handle the first expression
    expr = exprs[0]
    # The miss expression indicates no match has been found.
    # So refuse to recur, will not yield any solutions
    if expr.tag=='miss':
        pass
    # The hit expression means a match has been found.
    # So yield the current set of bindings.
    # <hit/>
    # or optionally, a subset of them
    # <hit vars="{name1} {name2}"/>
    elif expr.tag=='hit':
        var_name_list = expr.get('vars')
        if var_name_list is not None:
            var_names = re.split('  *',var_name_list)
            yield dict((var_name,val(bindings,var_name)) for var_name in var_names)
        else:
            yield bindings.flatten()
    # Import means descend, once, into another namespace, evaluating it as a block,
    # and recur for each of its solutions
    elif expr.tag=='import':
        for s in evaluate(expr.get('name'),global_namespace):
            for ss in recur(exprs,bindings,s): yield ss
    # The var expression sets variables to interpolated values
    # <var name="{name}">{value}</var>
    # or
    # <var name="{name}">
    #   <val>{value1}</val>
    #   <val>{value2}</val>
    # </var>
    elif expr.tag=='var':
        var_name = expr.get('name')
        sub_val_exprs = expr.findall('val')
        if len(sub_val_exprs) == 0:
            var_val = interpolate(expr.text,bindings)
            for s in recur(exprs,bindings,{var_name:var_val}): yield s
        else:
            for sub_val_expr in sub_val_exprs:
                var_val = interpolate(sub_val_expr.text,bindings)
                for s in recur(exprs,bindings,{var_name:var_val}): yield s
    # The vars expression is the plural of var, for multiple assignment
    # with any regex as a delimiter between variable values.
    # <vars names="{name1} {name2} [delim="{delim}"]>{value1}{delim}{value2}</vars>
    # or
    # <vars names="{name1} {name2} [delim="{delim}"]>
    #   <vals>{value1}{delim}{value2}</vals>
    #   <vals>{value1}{delim}{value2}</vals>
    # </vars>
    elif expr.tag=='vars':
        var_names = re.split('  *',expr.get('names'))
        sub_val_exprs = expr.findall('vals')
        delim = coalesce(expr.get('delim'),'  *')
        if len(sub_val_exprs) == 0:
            var_vals = map(lambda tmpl: interpolate(tmpl,bindings), re.split(delim,expr.text))
            for s in recur(exprs,bindings,dict(zip(var_names,var_vals))): yield s
        else:
            for sub_val_expr in sub_val_exprs:
                var_vals = map(lambda tmpl: interpolate(tmpl,bindings), re.split(delim,sub_val_expr.text))
                for s in recur(exprs,bindings,dict(zip(var_names,var_vals))): yield s
    # all is a conjunction
    elif expr.tag=='all':
        for s in evaluate_block(list(expr),bindings,global_namespace):
            for ss in recur(exprs,bindings,s): yield ss
    # any is a disjunction
    elif expr.tag=='any':
        for sub_expr in list(expr):
            for s in evaluate_block([sub_expr],bindings,global_namespace):
                for ss in recur(exprs,bindings,s): yield ss
    # log prints output
    elif expr.tag=='log':
        print interpolate(expr.text,bindings)
    # match generates solutions for every regex match
    # <match pattern="{regex}" value="{thing to match}" [groups="{name1} {name2}"]/>
    elif expr.tag=='match':
        pattern = coalesce(expr.get('pattern'),r'.*')
        group_name_list, group_names = expr.get('groups'), []
        if group_name_list is not None:
            group_names = re.split('  *',group_name_list)
        value = coalesce(expr.get('value'),'')
        m = re.match(interpolate(pattern,bindings), interpolate(value,bindings))
        if m is not None:
            groups = m.groups()
            inner_bindings = {}
            for index,group in zip(range(len(groups)), groups): # bind numbered variables to groups
                inner_bindings[str(index+1)] = group
            for name,group in zip(group_names, groups): # bind named variables to groups
                inner_bindings[name] = group
            for s in recur(exprs,bindings,inner_bindings): yield s
    # all other tags skip
    else:
        for s in recur(exprs,bindings): yield s
                
def evaluate(name,global_namespace={}):
    expr = global_namespace[name]
    if expr.tag == 'namespace':
        for solution in evaluate_block(list(expr),global_namespace=global_namespace):
            yield solution

def parse(ldr_file):
    xml = etree.parse(ldr_file)
    namespace = find_names(xml)
    return namespace

def resolve(namespace,name):
    for s in evaluate(name,namespace):
        yield s
    
